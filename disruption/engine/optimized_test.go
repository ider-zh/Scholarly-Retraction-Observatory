package main

import (
	"math/rand"
	"reflect"
	"sort"
	"sync"
	"testing"
	"time"
)

func optimizationGraph(size int) *Graph {
	random := rand.New(rand.NewSource(8103))
	graph := &Graph{IDs: make([]uint64, size), Years: make([]int32, size), CitedBy: make([]int64, size), RawReferenceCounts: make([]int64, size), Audit: make([]Audit, size), Offsets: []uint64{0}, IncomingOffsets: []uint64{0}, SnapshotDate: "2026-06-26"}
	incoming := make([][]uint32, size)
	for source := 0; source < size; source++ {
		graph.IDs[source] = uint64(source + 1)
		graph.Years[source] = int32(1970 + random.Intn(60))
		if source%31 == 0 {
			graph.Years[source] = 0
		}
		targets := map[uint32]bool{}
		if source%5 != 0 {
			for edge := 0; edge < 24; edge++ {
				target := uint32(random.Intn(size))
				if edge < 4 {
					target = uint32(random.Intn(min(size, 20)))
				}
				if target != uint32(source) {
					targets[target] = true
				}
			}
		}
		ordered := make([]uint32, 0, len(targets))
		for target := range targets {
			ordered = append(ordered, target)
		}
		sort.Slice(ordered, func(left, right int) bool { return ordered[left] < ordered[right] })
		for _, target := range ordered {
			graph.Targets = append(graph.Targets, target)
			incoming[target] = append(incoming[target], uint32(source))
		}
		graph.RawReferenceCounts[source] = int64(len(ordered))
		graph.Offsets = append(graph.Offsets, uint64(len(graph.Targets)))
	}
	for _, sources := range incoming {
		graph.Incoming = append(graph.Incoming, sources...)
		graph.IncomingOffsets = append(graph.IncomingOffsets, uint64(len(graph.Incoming)))
	}
	return graph
}

func TestScratchMatchesSparseReuseAndWrap(t *testing.T) {
	graph := optimizationGraph(600)
	snapshot, _ := time.Parse("2006-01-02", graph.SnapshotDate)
	scratch := NewCountScratch(len(graph.IDs))
	for pass := 0; pass < 3; pass++ {
		if pass == 1 {
			scratch.epoch = ^uint32(0)>>2 - 1
		}
		for focal := len(graph.IDs) - 1; focal >= 0; focal-- {
			want := CountFocal(graph, uint32(focal), snapshot)
			got := CountFocalWithScratch(graph, uint32(focal), snapshot, scratch)
			want.ElapsedSeconds, got.ElapsedSeconds = 0, 0
			if !reflect.DeepEqual(got, want) {
				t.Fatalf("pass %d focal %d mismatch: got %+v want %+v", pass, focal, got, want)
			}
		}
	}
}

func TestScratchAgainstIndependentSetOracle(t *testing.T) {
	graph := optimizationGraph(240)
	snapshot, _ := time.Parse("2006-01-02", graph.SnapshotDate)
	scratch := NewCountScratch(len(graph.IDs))
	references := make([]map[uint32]bool, len(graph.IDs))
	for source := range graph.IDs {
		references[source] = map[uint32]bool{}
		for _, target := range graph.Targets[graph.Offsets[source]:graph.Offsets[source+1]] {
			references[source][target] = true
		}
	}
	for focal, focalYear := range graph.Years {
		if focalYear <= 0 || focalYear > int32(snapshot.Year()) {
			continue
		}
		want := map[int32][5]int64{}
		for citing, citingYear := range graph.Years {
			if citing == focal || citingYear < focalYear || citingYear > int32(snapshot.Year()) {
				continue
			}
			shared := false
			for reference := range references[focal] {
				if graph.Years[reference] > 0 && graph.Years[reference] < focalYear && references[citing][reference] {
					shared = true
					break
				}
			}
			direct := references[citing][uint32(focal)]
			if !direct && !shared {
				continue
			}
			age := citingYear - focalYear
			bucket := want[age]
			if direct {
				bucket[3]++
			}
			bucket[4]++
			switch {
			case direct && shared:
				bucket[1]++
			case direct:
				bucket[0]++
			default:
				bucket[2]++
			}
			want[age] = bucket
		}
		got := map[int32][5]int64{}
		for _, bucket := range CountFocalWithScratch(graph, uint32(focal), snapshot, scratch).Annual {
			got[bucket.Age] = [5]int64{bucket.NF, bucket.NB, bucket.NR, bucket.Citations, bucket.Related}
		}
		if !reflect.DeepEqual(got, want) {
			t.Fatalf("focal %d got %v want %v", focal, got, want)
		}
	}
}

func TestScratchNoReferencesDoesNotAllocate(t *testing.T) {
	graph := optimizationGraph(100)
	snapshot, _ := time.Parse("2006-01-02", graph.SnapshotDate)
	scratch := NewCountScratch(len(graph.IDs))
	for focal := 0; focal < len(graph.IDs); focal += 5 {
		CountFocalWithScratch(graph, uint32(focal), snapshot, scratch)
	}
	if scratch.marks != nil || scratch.epoch != 0 {
		t.Fatal("reference-free focal allocated or consumed a dense scratch generation")
	}
}

func TestScratchConcurrentReaders(t *testing.T) {
	graph := optimizationGraph(300)
	snapshot, _ := time.Parse("2006-01-02", graph.SnapshotDate)
	var workers sync.WaitGroup
	for worker := 0; worker < 4; worker++ {
		workers.Add(1)
		go func() {
			defer workers.Done()
			scratch := NewCountScratch(len(graph.IDs))
			for focal := range graph.IDs {
				got := CountFocalWithScratch(graph, uint32(focal), snapshot, scratch)
				want := CountFocal(graph, uint32(focal), snapshot)
				got.ElapsedSeconds, want.ElapsedSeconds = 0, 0
				if !reflect.DeepEqual(got, want) {
					t.Errorf("concurrent focal %d differs", focal)
					return
				}
			}
		}()
	}
	workers.Wait()
}

func BenchmarkCountCandidateStrategies(b *testing.B) {
	graph := optimizationGraph(20000)
	snapshot, _ := time.Parse("2006-01-02", graph.SnapshotDate)
	for _, dense := range []bool{false, true} {
		name := "sparse"
		var scratch *CountScratch
		if dense {
			name = "dense"
			scratch = NewCountScratch(len(graph.IDs))
			scratch.begin()
		}
		b.Run(name, func(b *testing.B) {
			b.ReportAllocs()
			for iteration := 0; iteration < b.N; iteration++ {
				CountFocalWithScratch(graph, uint32(iteration%len(graph.IDs)), snapshot, scratch)
			}
		})
	}
}
