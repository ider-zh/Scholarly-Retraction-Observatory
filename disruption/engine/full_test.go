package main

import (
	"compress/gzip"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func fullFixture(t *testing.T) (*Graph, string, FullCountOptions) {
	t.Helper()
	input := graphFixture(t)
	graph, err := BuildGraph(input)
	if err != nil {
		t.Fatal(err)
	}
	directory := filepath.Join(t.TempDir(), "graph")
	if err = SaveGraph(graph, directory, input); err != nil {
		t.Fatal(err)
	}
	return graph, directory, FullCountOptions{CountOptions: CountOptions{Workers: 2, PartitionSize: 3, MaximumOutputBytes: 10000000}, BatchSize: 2}
}

func readFullRows(t *testing.T, directory string) []FocalCount {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(directory, "manifest.json"))
	if err != nil {
		t.Fatal(err)
	}
	var manifest CountManifest
	if err = json.Unmarshal(data, &manifest); err != nil {
		t.Fatal(err)
	}
	if !manifest.Complete {
		t.Fatal("manifest incomplete")
	}
	var results []FocalCount
	for _, partition := range manifest.Partitions {
		file, err := os.Open(filepath.Join(directory, partition.File))
		if err != nil {
			t.Fatal(err)
		}
		reader, err := gzip.NewReader(file)
		if err != nil {
			t.Fatal(err)
		}
		decoder := json.NewDecoder(reader)
		for {
			var row FocalCount
			err = decoder.Decode(&row)
			if err == io.EOF {
				break
			}
			if err != nil {
				t.Fatal(err)
			}
			row.ElapsedSeconds = 0
			results = append(results, row)
		}
		reader.Close()
		file.Close()
	}
	return results
}

func TestFullCountsMatchLegacyAndResume(t *testing.T) {
	graph, directory, options := fullFixture(t)
	output := t.TempDir()
	if err := FullCountGraph(graph, directory, output, options); err != nil {
		t.Fatal(err)
	}
	legacy := t.TempDir()
	if err := CountGraph(graph, directory, legacy, []uint32{0, 1, 2, 3, 4}, options.CountOptions); err != nil {
		t.Fatal(err)
	}
	want := readFullRows(t, legacy)
	if got := readFullRows(t, output); !reflect.DeepEqual(got, want) {
		t.Fatalf("full rows mismatch: %+v vs %+v", got, want)
	}
	first := filepath.Join(output, "annual-00000000.jsonl.gz")
	before, err := os.ReadFile(first)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.Remove(filepath.Join(output, "manifest.json")); err != nil {
		t.Fatal(err)
	}
	if err = os.Remove(filepath.Join(output, "checkpoints", "00000001.json")); err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(output, "annual-00000001.jsonl.gz.tmp"), []byte("interrupted"), 0644); err != nil {
		t.Fatal(err)
	}
	options.Workers = 1
	options.BatchSize = 1
	if err = FullCountGraph(graph, directory, output, options); err != nil {
		t.Fatal(err)
	}
	after, err := os.ReadFile(first)
	if err != nil || !reflect.DeepEqual(before, after) {
		t.Fatal("verified completed partition was rewritten")
	}
	if got := readFullRows(t, output); !reflect.DeepEqual(got, want) {
		t.Fatal("resume changed statistics")
	}
	if err = FullCountGraph(graph, directory, output, options); err != nil {
		t.Fatal(err)
	}
}

func TestFullRejectsCorruptionAndConfigurationChanges(t *testing.T) {
	for _, kind := range []string{"bytes", "coverage", "configuration", "final"} {
		t.Run(kind, func(t *testing.T) {
			graph, directory, options := fullFixture(t)
			output := t.TempDir()
			if err := FullCountGraph(graph, directory, output, options); err != nil {
				t.Fatal(err)
			}
			switch kind {
			case "bytes":
				if err := os.WriteFile(filepath.Join(output, "annual-00000000.jsonl.gz"), []byte("corrupt"), 0644); err != nil {
					t.Fatal(err)
				}
			case "coverage":
				path := filepath.Join(output, "checkpoints", "00000000.json")
				data, err := os.ReadFile(path)
				if err != nil {
					t.Fatal(err)
				}
				var checkpoint fullCheckpoint
				if err = json.Unmarshal(data, &checkpoint); err != nil {
					t.Fatal(err)
				}
				checkpoint.End++
				if err = writeCountManifest(path, checkpoint); err != nil {
					t.Fatal(err)
				}
			case "configuration":
				options.PartitionSize++
			case "final":
				path := filepath.Join(output, "manifest.json")
				data, err := os.ReadFile(path)
				if err != nil {
					t.Fatal(err)
				}
				var manifest CountManifest
				if err = json.Unmarshal(data, &manifest); err != nil {
					t.Fatal(err)
				}
				manifest.RequestedFocals++
				if err = writeCountManifest(path, manifest); err != nil {
					t.Fatal(err)
				}
			}
			if err := FullCountGraph(graph, directory, output, options); err == nil {
				t.Fatal("invalid completed run accepted")
			}
		})
	}
}

func TestFullDiskBudgetAndOptions(t *testing.T) {
	graph, directory, options := fullFixture(t)
	options.MaximumOutputBytes = 1
	if err := FullCountGraph(graph, directory, t.TempDir(), options); err == nil {
		t.Fatal("disk budget ignored")
	}
	options.BatchSize = options.PartitionSize + 1
	if err := FullCountGraph(graph, directory, t.TempDir(), options); err == nil {
		t.Fatal("invalid batch accepted")
	}
}
