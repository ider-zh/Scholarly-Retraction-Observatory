package main

import (
	"encoding/json"
	"math/rand"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"
)

func TestWriteCountManifestAtomicReplacement(t *testing.T) {
	path := filepath.Join(t.TempDir(), "manifest.json")
	for _, complete := range []bool{false, true} {
		if err := writeCountManifest(path, map[string]bool{"complete": complete}); err != nil {
			t.Fatal(err)
		}
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		var manifest map[string]bool
		if err = json.Unmarshal(data, &manifest); err != nil || manifest["complete"] != complete {
			t.Fatalf("unexpected published manifest: %s, error: %v", data, err)
		}
		if _, err = os.Stat(path + ".tmp"); !os.IsNotExist(err) {
			t.Fatalf("temporary manifest still exists: %v", err)
		}
	}
	if err := writeCountManifest(path, make(chan bool)); err == nil {
		t.Fatal("nonserializable manifest accepted")
	}
	data, err := os.ReadFile(path)
	if err != nil || string(data) != "{\n  \"complete\": true\n}" {
		t.Fatalf("failed update changed published manifest: %s, error: %v", data, err)
	}
}

func TestCountsAgainstIndependentDenseOracle(t *testing.T) {
	random := rand.New(rand.NewSource(27))
	const size = 30
	graph := &Graph{IDs: make([]uint64, size), Years: make([]int32, size), CitedBy: make([]int64, size), RawReferenceCounts: make([]int64, size), Audit: make([]Audit, size), Offsets: []uint64{0}, IncomingOffsets: []uint64{0}, SnapshotDate: "2026-06-26"}
	adjacency := make([][]bool, size)
	incoming := make([][]uint32, size)
	for source := 0; source < size; source++ {
		graph.IDs[source] = uint64(1000 - source)
		graph.Years[source] = int32(2017 + random.Intn(12))
		if source%9 == 0 {
			graph.Years[source] = 0
		}
		adjacency[source] = make([]bool, size)
		for target := 0; target < size; target++ {
			if source != target && random.Intn(4) == 0 {
				adjacency[source][target] = true
				graph.Targets = append(graph.Targets, uint32(target))
				incoming[target] = append(incoming[target], uint32(source))
				graph.RawReferenceCounts[source]++
			}
		}
		graph.Offsets = append(graph.Offsets, uint64(len(graph.Targets)))
	}
	for _, sources := range incoming {
		graph.Incoming = append(graph.Incoming, sources...)
		graph.IncomingOffsets = append(graph.IncomingOffsets, uint64(len(graph.Incoming)))
	}
	snapshot, _ := time.Parse("2006-01-02", graph.SnapshotDate)
	for focal := 0; focal < size; focal++ {
		result := CountFocal(graph, uint32(focal), snapshot)
		if graph.Years[focal] <= 0 || graph.Years[focal] > 2026 {
			continue
		}
		want := map[int32][3]int64{}
		for citing := 0; citing < size; citing++ {
			if citing == focal || graph.Years[citing] < graph.Years[focal] || graph.Years[citing] > 2026 {
				continue
			}
			shared := false
			for reference := 0; reference < size; reference++ {
				if adjacency[focal][reference] && graph.Years[reference] > 0 && graph.Years[reference] < graph.Years[focal] && adjacency[citing][reference] {
					shared = true
				}
			}
			if !adjacency[citing][focal] && !shared {
				continue
			}
			age := graph.Years[citing] - graph.Years[focal]
			values := want[age]
			if adjacency[citing][focal] && shared {
				values[1]++
			} else if shared {
				values[2]++
			} else {
				values[0]++
			}
			want[age] = values
		}
		got := map[int32][3]int64{}
		for _, annual := range result.Annual {
			got[annual.Age] = [3]int64{annual.NF, annual.NB, annual.NR}
		}
		if !reflect.DeepEqual(got, want) {
			t.Fatalf("focal %d got %v want %v", focal, got, want)
		}
	}
}

func TestCountPartitionsResumeAndIntegrity(t *testing.T) {
	graph := countingFixture()
	graphDirectory := t.TempDir()
	if err := os.WriteFile(filepath.Join(graphDirectory, "manifest.json"), []byte(`{"fixture":true}`), 0644); err != nil {
		t.Fatal(err)
	}
	output := t.TempDir()
	options := CountOptions{Workers: 2, PartitionSize: 2}
	focals := []uint32{11, 0, 3}
	if err := CountGraph(graph, graphDirectory, output, focals, options); err != nil {
		t.Fatal(err)
	}
	manifestBefore, _ := os.ReadFile(filepath.Join(output, "manifest.json"))
	if err := CountGraph(graph, graphDirectory, output, focals, options); err != nil {
		t.Fatal(err)
	}
	manifestAfter, _ := os.ReadFile(filepath.Join(output, "manifest.json"))
	if !reflect.DeepEqual(manifestBefore, manifestAfter) {
		t.Fatal("resume changed completed manifest")
	}
	if err := os.WriteFile(filepath.Join(output, "annual-00000000.jsonl.gz"), []byte("corrupt"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := CountGraph(graph, graphDirectory, output, focals, options); err == nil {
		t.Fatal("corrupt completed partition accepted")
	}
}

func TestCountRejectsDuplicateFocals(t *testing.T) {
	graph := countingFixture()
	if err := CountGraph(graph, t.TempDir(), t.TempDir(), []uint32{0, 0}, CountOptions{Workers: 1, PartitionSize: 1}); err == nil {
		t.Fatal("duplicate focal accepted")
	}
}

func countingFixture() *Graph {
	years := []int32{2020, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2019, 0}
	adjacency := [][]uint32{{1, 2}, {}, {}, {0}, {0}, {0, 1, 2}, {1, 2}, {0}, {0, 1}, {2}, {0}, {0}}
	graph := &Graph{Years: years, SnapshotDate: "2026-06-26", Offsets: []uint64{0}, IncomingOffsets: []uint64{0}, IDs: make([]uint64, len(years)), CitedBy: make([]int64, len(years)), RawReferenceCounts: make([]int64, len(years)), Audit: make([]Audit, len(years))}
	incoming := make([][]uint32, len(years))
	for index, targets := range adjacency {
		graph.IDs[index] = uint64(index + 1)
		graph.RawReferenceCounts[index] = int64(len(targets))
		graph.Targets = append(graph.Targets, targets...)
		graph.Offsets = append(graph.Offsets, uint64(len(graph.Targets)))
		for _, target := range targets {
			incoming[target] = append(incoming[target], uint32(index))
		}
	}
	for _, sources := range incoming {
		graph.Incoming = append(graph.Incoming, sources...)
		graph.IncomingOffsets = append(graph.IncomingOffsets, uint64(len(graph.Incoming)))
	}
	return graph
}

func TestAnnualTwoPolicies(t *testing.T) {
	graph := countingFixture()
	snapshot, _ := time.Parse("2006-01-02", graph.SnapshotDate)
	result := CountFocal(graph, 0, snapshot)
	if result.Indegree != 7 || *result.ValidReferences != 2 || *result.SameYear != 1 || *result.EarlierYear != 1 || *result.UnknownYear != 1 {
		t.Fatalf("unexpected focal metadata: %+v", result)
	}
	for _, test := range []struct {
		start, end int32
		want       [3]int64
	}{{1, 3, [3]int64{1, 1, 1}}, {0, 2, [3]int64{2, 1, 0}}, {1, 5, [3]int64{2, 2, 1}}, {0, 4, [3]int64{3, 1, 1}}, {1, 6, [3]int64{2, 2, 2}}, {0, 6, [3]int64{3, 2, 2}}} {
		var got [3]int64
		for _, row := range result.Annual {
			if row.Age >= test.start && row.Age <= test.end {
				got[0] += row.NF
				got[1] += row.NB
				got[2] += row.NR
			}
			if !row.CitationConsistent || !row.NeighborhoodConsistent {
				t.Fatal("inconsistent counts")
			}
		}
		if got != test.want {
			t.Errorf("window %d..%d got %v want %v", test.start, test.end, got, test.want)
		}
	}
	if !result.Annual[len(result.Annual)-1].Partial {
		t.Fatal("snapshot year must be partial")
	}
}

func TestUnknownYearIsNotZero(t *testing.T) {
	graph := countingFixture()
	snapshot, _ := time.Parse("2006-01-02", graph.SnapshotDate)
	result := CountFocal(graph, 11, snapshot)
	if result.Year != nil || result.ValidReferences != nil || result.ObservedEnd != nil || result.Status == "complete" || len(result.Annual) != 0 {
		t.Fatalf("unknown year misrepresented: %+v", result)
	}
}

func TestSparseCompleteAndNoReferences(t *testing.T) {
	graph := countingFixture()
	snapshot, _ := time.Parse("2006-01-02", graph.SnapshotDate)
	result := CountFocal(graph, 3, snapshot)
	if *result.ValidReferences != 0 || result.Status != "complete" || !reflect.DeepEqual(result.Annual, []AnnualCount{}) {
		t.Fatalf("unexpected sparse focal %+v", result)
	}
}

func TestFutureFocalHasNoObservableRange(t *testing.T) {
	graph := countingFixture()
	graph.Years[3] = 2027
	snapshot, _ := time.Parse("2006-01-02", graph.SnapshotDate)
	result := CountFocal(graph, 3, snapshot)
	if result.Status != "outside_observation_range" || result.ObservedEnd != nil {
		t.Fatalf("unexpected future focal %+v", result)
	}
}

func TestCLIRejectsImplicitAll(t *testing.T) {
	if err := run([]string{"count", "--graph", "missing", "--output", "missing"}); err == nil {
		t.Fatal("implicit full scan allowed")
	}
}
