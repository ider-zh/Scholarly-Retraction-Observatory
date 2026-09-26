package main

import (
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func graphFixture(t *testing.T) string {
	t.Helper()
	directory := t.TempDir()
	ids := []uint64{10, 20, 30, 40, 50}
	years := []int32{2020, 2018, 2020, 2022, 0}
	references := [][]uint64{{20, 20, 10, 10, 999, 999, 0, 30, 40, 50}, {}, {10}, {10, 20}, nil}
	var nodes, edges bytes.Buffer
	for index, id := range ids {
		length := int64(len(references[index]))
		if index == 4 {
			length = -1
		}
		for _, value := range []any{id, years[index], uint32(0), int64(-1), length} {
			if err := binary.Write(&nodes, binary.LittleEndian, value); err != nil {
				t.Fatal(err)
			}
		}
		if err := binary.Write(&edges, binary.LittleEndian, id); err != nil {
			t.Fatal(err)
		}
		if err := binary.Write(&edges, binary.LittleEndian, length); err != nil {
			t.Fatal(err)
		}
		if err := binary.Write(&edges, binary.LittleEndian, references[index]); err != nil {
			t.Fatal(err)
		}
	}
	write := func(name string, data []byte) string {
		var compressed bytes.Buffer
		writer := gzip.NewWriter(&compressed)
		if _, err := writer.Write(data); err != nil {
			t.Fatal(err)
		}
		if err := writer.Close(); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(directory, name), compressed.Bytes(), 0644); err != nil {
			t.Fatal(err)
		}
		digest := sha256.Sum256(compressed.Bytes())
		return hex.EncodeToString(digest[:])
	}
	manifest := bridgeManifest{SchemaVersion: "graph-bridge-v1", Status: "complete", SnapshotDate: "2026-06-26", FoundationConfigSHA256: "fixture", Shards: []bridgeShard{{Nodes: "nodes.gz", References: "references.gz", Rows: 5, NodesSHA256: write("nodes.gz", nodes.Bytes()), ReferencesSHA256: write("references.gz", edges.Bytes())}}}
	encoded, err := json.Marshal(manifest)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(directory, "manifest.json")
	if err := os.WriteFile(path, encoded, 0644); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestGraphCanonicalAuditAndRoundTrip(t *testing.T) {
	manifest := graphFixture(t)
	graph, err := BuildGraph(manifest)
	if err != nil {
		t.Fatal(err)
	}
	if actual, expected := graph.Offsets, []uint64{0, 4, 4, 5, 7, 7}; !reflect.DeepEqual(actual, expected) {
		t.Fatalf("offsets: %v", actual)
	}
	if actual, expected := graph.Targets, []uint32{1, 2, 3, 4, 0, 0, 1}; !reflect.DeepEqual(actual, expected) {
		t.Fatalf("targets: %v", actual)
	}
	if actual, expected := graph.IncomingOffsets, []uint64{0, 2, 4, 5, 6, 7}; !reflect.DeepEqual(actual, expected) {
		t.Fatalf("incoming offsets: %v", actual)
	}
	if actual, expected := graph.Incoming, []uint32{2, 3, 0, 3, 0, 0, 0}; !reflect.DeepEqual(actual, expected) {
		t.Fatalf("incoming: %v", actual)
	}
	if graph.Audit[0] != (Audit{Invalid: 1, Duplicate: 3, Dangling: 2, SelfLoop: 2, SameYear: 1, FutureYear: 1, UnknownYear: 1}) {
		t.Fatalf("audit: %+v", graph.Audit[0])
	}
	if graph.RawReferenceCounts[4] != -1 || graph.Years[4] != 0 {
		t.Fatal("missing metadata lost")
	}
	output := filepath.Join(t.TempDir(), "graph")
	if err := SaveGraph(graph, output, manifest); err != nil {
		t.Fatal(err)
	}
	loaded, err := LoadGraph(output)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(graph, loaded) {
		t.Fatal("graph round trip differs")
	}
	if err := SaveGraph(graph, output, manifest); err == nil {
		t.Fatal("overwrite accepted")
	}
	if err := os.WriteFile(filepath.Join(output, "targets.bin.gz"), []byte("broken"), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadGraph(output); err == nil {
		t.Fatal("corrupt graph accepted")
	}
}

func TestGraphRejectsPartialAndHashMismatch(t *testing.T) {
	for _, mutation := range []string{"partial", "hash", "path", "rows", "date", "total"} {
		t.Run(mutation, func(t *testing.T) {
			path := graphFixture(t)
			data, err := os.ReadFile(path)
			if err != nil {
				t.Fatal(err)
			}
			var manifest bridgeManifest
			if err := json.Unmarshal(data, &manifest); err != nil {
				t.Fatal(err)
			}
			switch mutation {
			case "partial":
				manifest.Status = "partial"
			case "hash":
				manifest.Shards[0].NodesSHA256 = string(bytes.Repeat([]byte("0"), 64))
			case "path":
				manifest.Shards[0].Nodes = "../outside.gz"
			case "rows":
				manifest.Shards[0].Rows++
			case "date":
				manifest.SnapshotDate = "2026-02-30"
			case "total":
				total := uint64(8)
				manifest.Rows = &total
			}
			encoded, err := json.Marshal(manifest)
			if err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(path, encoded, 0644); err != nil {
				t.Fatal(err)
			}
			if _, err := BuildGraph(path); err == nil {
				t.Fatalf("accepted %s bridge", mutation)
			}
		})
	}
}

func TestGraphParallelShards(t *testing.T) {
	path := graphFixture(t)
	original, err := BuildGraph(path)
	if err != nil {
		t.Fatal(err)
	}
	directory := filepath.Dir(path)
	read := func(name string) []byte {
		file, err := os.Open(filepath.Join(directory, name))
		if err != nil {
			t.Fatal(err)
		}
		defer file.Close()
		reader, err := gzip.NewReader(file)
		if err != nil {
			t.Fatal(err)
		}
		defer reader.Close()
		data, err := io.ReadAll(reader)
		if err != nil {
			t.Fatal(err)
		}
		return data
	}
	write := func(name string, data []byte) string {
		var compressed bytes.Buffer
		writer := gzip.NewWriter(&compressed)
		if _, err := writer.Write(data); err != nil {
			t.Fatal(err)
		}
		if err := writer.Close(); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(directory, name), compressed.Bytes(), 0644); err != nil {
			t.Fatal(err)
		}
		digest := sha256.Sum256(compressed.Bytes())
		return hex.EncodeToString(digest[:])
	}
	nodes, references := read("nodes.gz"), read("references.gz")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var manifest bridgeManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		t.Fatal(err)
	}
	manifest.Shards = []bridgeShard{
		{Nodes: "nodes-a.gz", References: "refs-a.gz", Rows: 2, NodesSHA256: write("nodes-a.gz", nodes[:64]), ReferencesSHA256: write("refs-a.gz", references[:112])},
		{Nodes: "nodes-b.gz", References: "refs-b.gz", Rows: 3, NodesSHA256: write("nodes-b.gz", nodes[64:]), ReferencesSHA256: write("refs-b.gz", references[112:])},
	}
	encoded, err := json.Marshal(manifest)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, encoded, 0644); err != nil {
		t.Fatal(err)
	}
	parallel, err := BuildGraph(path)
	if err != nil {
		t.Fatal(err)
	}
	original.BridgeManifestSHA256 = parallel.BridgeManifestSHA256
	if !reflect.DeepEqual(original, parallel) {
		t.Fatal("parallel shards changed graph")
	}
}
