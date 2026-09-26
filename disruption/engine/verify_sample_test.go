package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestVerifySparseBenchmarkBeforeFull(t *testing.T) {
	graph, directory, options := fullFixture(t)
	output := t.TempDir()
	if err := CountGraph(graph, directory, output, []uint32{0, 1, 2, 3, 4}, options.CountOptions); err != nil {
		t.Fatal(err)
	}
	manifest := filepath.Join(output, "manifest.json")
	if err := VerifyBenchmark(graph, directory, manifest); err != nil {
		t.Fatal(err)
	}
	graph.RawReferenceCounts[0]++
	if err := VerifyBenchmark(graph, directory, manifest); err == nil {
		t.Fatal("different underlying statistics accepted")
	}
	graph.RawReferenceCounts[0]--
	if err := os.WriteFile(filepath.Join(output, "annual-00000000.jsonl.gz"), []byte("bad"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := VerifyBenchmark(graph, directory, manifest); err == nil {
		t.Fatal("corrupt sparse benchmark accepted")
	}
}
