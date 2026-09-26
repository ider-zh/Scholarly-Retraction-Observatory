package main

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"time"
)

func statisticalRecord(record FocalCount) (map[string]any, error) {
	encoded, err := json.Marshal(record)
	if err != nil {
		return nil, err
	}
	var values map[string]any
	decoder := json.NewDecoder(bytes.NewReader(encoded))
	decoder.UseNumber()
	if err := decoder.Decode(&values); err != nil {
		return nil, err
	}
	delete(values, "elapsed_seconds")
	delete(values, "visited_incoming_edges")
	delete(values, "distinct_candidate_works")
	return values, nil
}

func VerifyBenchmark(graph *Graph, graphDir, manifestPath string) error {
	data, err := os.ReadFile(manifestPath)
	if err != nil {
		return err
	}
	var manifest CountManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return err
	}
	graphHash, err := fileDigest(filepath.Join(graphDir, "manifest.json"))
	if err != nil {
		return err
	}
	if !manifest.Complete || manifest.GraphManifestSHA256 != graphHash || manifest.SnapshotDate != graph.SnapshotDate || manifest.GraphWorks != len(graph.IDs) {
		return fmt.Errorf("benchmark provenance or completion does not match graph")
	}
	snapshot, err := time.Parse("2006-01-02", graph.SnapshotDate)
	if err != nil {
		return err
	}
	scratch := NewCountScratch(len(graph.IDs))
	verified := 0
	for _, partition := range manifest.Partitions {
		path, err := localGraphPath(filepath.Dir(manifestPath), partition.File)
		if err != nil {
			return err
		}
		actualHash, err := fileDigest(path)
		if err != nil || actualHash != partition.SHA256 {
			return fmt.Errorf("benchmark checksum mismatch: %s", path)
		}
		file, err := os.Open(path)
		if err != nil {
			return err
		}
		compressed, err := gzip.NewReader(file)
		if err != nil {
			file.Close()
			return err
		}
		decoder := json.NewDecoder(compressed)
		decoder.UseNumber()
		rows := 0
		for {
			var expected FocalCount
			if err := decoder.Decode(&expected); err == io.EOF {
				break
			} else if err != nil {
				compressed.Close()
				file.Close()
				return err
			}
			if uint64(expected.GraphNodeIndex) >= uint64(len(graph.IDs)) || graph.IDs[expected.GraphNodeIndex] != expected.NumericID {
				compressed.Close()
				file.Close()
				return fmt.Errorf("benchmark focal does not match graph")
			}
			actual := CountFocalWithScratch(graph, uint32(expected.GraphNodeIndex), snapshot, scratch)
			left, leftErr := statisticalRecord(expected)
			right, rightErr := statisticalRecord(actual)
			if leftErr != nil || rightErr != nil || !reflect.DeepEqual(left, right) {
				compressed.Close()
				file.Close()
				return fmt.Errorf("optimized counting differs from sparse benchmark for %s", expected.WorkID)
			}
			rows++
			verified++
		}
		compressed.Close()
		file.Close()
		if rows != partition.Rows {
			return fmt.Errorf("benchmark row count mismatch")
		}
	}
	if verified != manifest.RequestedFocals || verified == 0 {
		return fmt.Errorf("benchmark coverage mismatch")
	}
	fmt.Fprintf(os.Stderr, "optimized engine matches %d complete-neighborhood sparse benchmark focals\n", verified)
	return nil
}
