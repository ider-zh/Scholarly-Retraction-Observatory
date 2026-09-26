package main

import (
	"compress/gzip"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"sync"
	"syscall"
	"time"
)

type AnnualCount struct {
	Age                    int32 `json:"age_year"`
	NF                     int64 `json:"NF"`
	NB                     int64 `json:"NB"`
	NR                     int64 `json:"NR"`
	Citations              int64 `json:"citation_count"`
	Related                int64 `json:"future_related_count"`
	CitationConsistent     bool  `json:"citation_count_consistent"`
	CitationDelta          int64 `json:"citation_partition_delta"`
	NeighborhoodConsistent bool  `json:"neighborhood_count_consistent"`
	NeighborhoodDelta      int64 `json:"neighborhood_partition_delta"`
	Partial                bool  `json:"is_partial_calendar_year"`
}

type FocalCount struct {
	GraphNodeIndex         uint32        `json:"graph_node_index"`
	ElapsedSeconds         float64       `json:"elapsed_seconds"`
	VisitedIncomingEdges   uint64        `json:"visited_incoming_edges"`
	DistinctCandidateWorks int64         `json:"distinct_candidate_works"`
	WorkID                 string        `json:"work_id"`
	NumericID              uint64        `json:"work_id_numeric"`
	Year                   *int32        `json:"publication_year"`
	RawReferences          *int64        `json:"reference_count_raw"`
	ResolvedReferences     int64         `json:"reference_count_resolved_unique"`
	ValidReferences        *int64        `json:"reference_count_valid"`
	HasReferences          *bool         `json:"has_references"`
	ReferenceListUnknown   bool          `json:"reference_list_unknown"`
	Indegree               int64         `json:"graph_indegree_all"`
	CitedBy                *int64        `json:"openalex_cited_by_count"`
	CitedByDelta           *int64        `json:"openalex_graph_citation_count_delta"`
	SameYear               *int64        `json:"incoming_same_year_count"`
	EarlierYear            *int64        `json:"incoming_earlier_year_count"`
	UnknownYear            *int64        `json:"incoming_unknown_year_count"`
	FutureYear             *int64        `json:"incoming_after_snapshot_year_count"`
	Audit                  any           `json:"reference_quality_counts"`
	Status                 string        `json:"computation_status"`
	ObservedStart          *int32        `json:"observed_age_start"`
	ObservedEnd            *int32        `json:"observed_age_end"`
	ObservedEndDate        string        `json:"observed_end_date"`
	Annual                 []AnnualCount `json:"annual_counts"`
}

func optionalCount(value int64) *int64 {
	if value < 0 {
		return nil
	}
	return &value
}

type CountScratch struct {
	nodeCount int
	marks     []uint32
	epoch     uint32
}

func NewCountScratch(nodeCount int) *CountScratch {
	return &CountScratch{nodeCount: nodeCount}
}

func (scratch *CountScratch) begin() {
	if scratch.marks == nil {
		scratch.marks = make([]uint32, scratch.nodeCount)
	}
	if scratch.epoch == ^uint32(0)>>2 {
		clear(scratch.marks)
		scratch.epoch = 0
	}
	scratch.epoch++
}

func (scratch *CountScratch) add(citing uint32, mask uint8) uint8 {
	previous := scratch.marks[citing]
	oldMask := uint8(0)
	if previous>>2 == scratch.epoch {
		oldMask = uint8(previous & 3)
	}
	scratch.marks[citing] = scratch.epoch<<2 | uint32(oldMask|mask)
	return oldMask
}

func CountFocal(graph *Graph, focal uint32, snapshot time.Time) (result FocalCount) {
	return CountFocalWithScratch(graph, focal, snapshot, nil)
}

func CountFocalWithScratch(graph *Graph, focal uint32, snapshot time.Time, scratch *CountScratch) (result FocalCount) {
	started := time.Now()
	defer func() { result.ElapsedSeconds = time.Since(started).Seconds() }()
	year := graph.Years[focal]
	result = FocalCount{WorkID: fmt.Sprintf("https://openalex.org/W%d", graph.IDs[focal]), NumericID: graph.IDs[focal], RawReferences: optionalCount(graph.RawReferenceCounts[focal]), ResolvedReferences: int64(graph.Offsets[focal+1] - graph.Offsets[focal]), Indegree: int64(graph.IncomingOffsets[focal+1] - graph.IncomingOffsets[focal]), CitedBy: optionalCount(graph.CitedBy[focal]), Audit: graph.Audit[focal], Status: "unavailable_publication_year", ObservedEndDate: snapshot.Format("2006-01-02"), Annual: []AnnualCount{}}
	result.GraphNodeIndex = focal
	if result.CitedBy != nil {
		delta := result.Indegree - *result.CitedBy
		result.CitedByDelta = &delta
	}
	result.ReferenceListUnknown = result.RawReferences == nil
	if year <= 0 {
		return result
	}
	result.Year = &year
	validReferences := int64(0)
	for _, reference := range graph.Targets[graph.Offsets[focal]:graph.Offsets[focal+1]] {
		if graph.Years[reference] > 0 && graph.Years[reference] < year {
			validReferences++
		}
	}
	result.ValidReferences = &validReferences
	hasReferences := validReferences > 0
	result.HasReferences = &hasReferences
	same, earlier, unknown, future := int64(0), int64(0), int64(0), int64(0)
	result.SameYear = &same
	result.EarlierYear = &earlier
	result.UnknownYear = &unknown
	result.FutureYear = &future
	snapshotYear := int32(snapshot.Year())
	buckets := map[int32]*AnnualCount{}
	getBucket := func(age int32) *AnnualCount {
		bucket := buckets[age]
		if bucket == nil {
			bucket = &AnnualCount{Age: age, Partial: year+age == snapshotYear && (snapshot.Month() != 12 || snapshot.Day() != 31)}
			buckets[age] = bucket
		}
		return bucket
	}
	var candidates map[uint32]uint8
	if validReferences > 0 && year <= snapshotYear {
		if scratch != nil {
			if scratch.nodeCount != len(graph.IDs) {
				panic("count scratch node count does not match graph")
			}
			scratch.begin()
		} else {
			candidates = make(map[uint32]uint8)
		}
	}
	addCandidate := func(citing uint32, mask uint8) {
		oldMask := uint8(0)
		if validReferences > 0 {
			if scratch != nil {
				oldMask = scratch.add(citing, mask)
			} else {
				oldMask = candidates[citing]
				candidates[citing] = oldMask | mask
			}
		}
		if oldMask&mask != 0 {
			return
		}
		bucket := getBucket(graph.Years[citing] - year)
		if oldMask == 0 {
			result.DistinctCandidateWorks++
			bucket.Related++
			if mask == 1 {
				bucket.NF++
			} else {
				bucket.NR++
			}
		} else {
			bucket.NB++
			if oldMask == 1 {
				bucket.NF--
			} else {
				bucket.NR--
			}
		}
	}
	result.VisitedIncomingEdges = uint64(result.Indegree)
	for _, citing := range graph.Incoming[graph.IncomingOffsets[focal]:graph.IncomingOffsets[focal+1]] {
		citingYear := graph.Years[citing]
		if citingYear <= 0 {
			unknown++
			continue
		}
		if citingYear == year {
			same++
		}
		if citingYear < year {
			earlier++
		}
		if citingYear > snapshotYear {
			future++
		}
		if citing == focal || citingYear < year || citingYear > snapshotYear {
			continue
		}
		getBucket(citingYear-year).Citations++
		addCandidate(citing, 1)
	}
	if year > snapshotYear {
		result.Status = "outside_observation_range"
		return result
	}
	for _, reference := range graph.Targets[graph.Offsets[focal]:graph.Offsets[focal+1]] {
		if graph.Years[reference] <= 0 || graph.Years[reference] >= year {
			continue
		}
		result.VisitedIncomingEdges += graph.IncomingOffsets[reference+1] - graph.IncomingOffsets[reference]
		for _, citing := range graph.Incoming[graph.IncomingOffsets[reference]:graph.IncomingOffsets[reference+1]] {
			if citing == focal || graph.Years[citing] < year || graph.Years[citing] > snapshotYear {
				continue
			}
			addCandidate(citing, 2)
		}
	}
	for _, bucket := range buckets {
		bucket.CitationDelta = bucket.Citations - bucket.NF - bucket.NB
		bucket.NeighborhoodDelta = bucket.Related - bucket.NF - bucket.NB - bucket.NR
		bucket.CitationConsistent = bucket.CitationDelta == 0
		bucket.NeighborhoodConsistent = bucket.NeighborhoodDelta == 0
		result.Annual = append(result.Annual, *bucket)
	}
	sort.Slice(result.Annual, func(left, right int) bool { return result.Annual[left].Age < result.Annual[right].Age })
	start, end := int32(0), snapshotYear-year
	result.ObservedStart = &start
	result.ObservedEnd = &end
	result.Status = "complete"
	return result
}

type CountOptions struct {
	Workers            int    `json:"workers"`
	PartitionSize      int    `json:"partition_size"`
	MinimumFreeBytes   uint64 `json:"minimum_free_bytes"`
	MaximumOutputBytes int64  `json:"maximum_output_bytes"`
}

type CountPartition struct {
	File        string `json:"file"`
	SHA256      string `json:"sha256"`
	Rows        int    `json:"rows"`
	Unavailable int    `json:"unavailable_rows"`
	Warnings    int    `json:"warning_rows"`
}

type CountManifest struct {
	SchemaVersion       string           `json:"schema_version"`
	CalculationVersion  string           `json:"calculation_version"`
	ConfigSHA256        string           `json:"config_sha256"`
	GraphManifestSHA256 string           `json:"graph_manifest_sha256"`
	EngineSHA256        string           `json:"engine_sha256"`
	SnapshotDate        string           `json:"openalex_snapshot_date"`
	GeneratedAt         string           `json:"generated_at"`
	Scope               string           `json:"scope"`
	GraphWorks          int              `json:"graph_work_count"`
	RequestedFocals     int              `json:"requested_focal_count"`
	FocalIDsSHA256      string           `json:"focal_ids_sha256"`
	SparseZeroRule      string           `json:"sparse_zero_rule"`
	SparseZeroSemantics string           `json:"sparse_zero_semantics"`
	Options             CountOptions     `json:"options"`
	Complete            bool             `json:"complete"`
	Partitions          []CountPartition `json:"partitions"`
}

func fileDigest(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hash := sha256.New()
	if _, err = io.Copy(hash, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

func writeCountManifest(path string, value any) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	temporary := path + ".tmp"
	file, err := os.OpenFile(temporary, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0644)
	if err != nil {
		return err
	}
	if _, err = file.Write(data); err != nil {
		file.Close()
		return err
	}
	if err = file.Sync(); err != nil {
		file.Close()
		return err
	}
	if err = file.Close(); err != nil {
		return err
	}
	if err = os.Rename(temporary, path); err != nil {
		return err
	}
	directory, err := os.Open(filepath.Dir(path))
	if err != nil {
		return err
	}
	defer directory.Close()
	return directory.Sync()
}

func checkDisk(output string, options CountOptions) error {
	var stat syscall.Statfs_t
	if err := syscall.Statfs(output, &stat); err != nil {
		return err
	}
	if uint64(stat.Bavail)*uint64(stat.Bsize) < options.MinimumFreeBytes {
		return fmt.Errorf("minimum free disk budget reached")
	}
	var bytes int64
	err := filepath.Walk(output, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() {
			bytes += info.Size()
		}
		return nil
	})
	if err != nil {
		return err
	}
	if options.MaximumOutputBytes > 0 && bytes >= options.MaximumOutputBytes {
		return fmt.Errorf("output disk budget reached")
	}
	return nil
}

func CountGraph(graph *Graph, graphDir, output string, focals []uint32, options CountOptions) error {
	if options.Workers < 1 || options.Workers > 40 || options.PartitionSize < 1 {
		return fmt.Errorf("workers must be 1..40 and partition size positive")
	}
	snapshot, err := time.Parse("2006-01-02", graph.SnapshotDate)
	if err != nil {
		return fmt.Errorf("invalid graph snapshot date: %w", err)
	}
	sort.Slice(focals, func(left, right int) bool { return focals[left] < focals[right] })
	for index, focal := range focals {
		if int(focal) >= len(graph.IDs) || (index > 0 && focals[index-1] == focal) {
			return fmt.Errorf("invalid or duplicate focal index %d", focal)
		}
	}
	if err = os.MkdirAll(output, 0755); err != nil {
		return err
	}
	graphHash, err := fileDigest(filepath.Join(graphDir, "manifest.json"))
	if err != nil {
		return err
	}
	executable, err := os.Executable()
	if err != nil {
		return err
	}
	engineHash, err := fileDigest(executable)
	if err != nil {
		return err
	}
	focalHash := sha256.New()
	var focalBytes [8]byte
	for _, focal := range focals {
		binary.LittleEndian.PutUint64(focalBytes[:], graph.IDs[focal])
		focalHash.Write(focalBytes[:])
	}
	manifest := CountManifest{SchemaVersion: "disruption-annual-v1", CalculationVersion: "go-exact-annual-v1", GraphManifestSHA256: graphHash, EngineSHA256: engineHash, SnapshotDate: graph.SnapshotDate, GeneratedAt: time.Now().UTC().Format(time.RFC3339), Scope: "selected_focals_full_graph_neighborhood", GraphWorks: len(graph.IDs), RequestedFocals: len(focals), FocalIDsSHA256: hex.EncodeToString(focalHash.Sum(nil)), SparseZeroRule: "Only complete focal rows within observed_age_start..observed_age_end permit absent annual bins to mean zero.", SparseZeroSemantics: "complete_observable_bins", Options: options, Partitions: []CountPartition{}}
	if len(focals) == len(graph.IDs) {
		manifest.Scope = "all_graph_works"
	}
	configData, _ := json.Marshal([]any{manifest.SchemaVersion, manifest.CalculationVersion, graphHash, engineHash, manifest.FocalIDsSHA256, options})
	configHash := sha256.Sum256(configData)
	manifest.ConfigSHA256 = hex.EncodeToString(configHash[:])
	manifestPath := filepath.Join(output, "manifest.json")
	if data, readErr := os.ReadFile(manifestPath); readErr == nil {
		var previous CountManifest
		if err = json.Unmarshal(data, &previous); err != nil {
			return err
		}
		if previous.ConfigSHA256 != manifest.ConfigSHA256 {
			return fmt.Errorf("count configuration changed; use a new output directory")
		}
		manifest = previous
		if len(manifest.Partitions) > (len(focals)+options.PartitionSize-1)/options.PartitionSize {
			return fmt.Errorf("partition coverage exceeds focal selection")
		}
		for index, partition := range manifest.Partitions {
			expectedRows := options.PartitionSize
			if remaining := len(focals) - index*options.PartitionSize; remaining < expectedRows {
				expectedRows = remaining
			}
			if partition.File != fmt.Sprintf("annual-%08d.jsonl.gz", index) || partition.Rows != expectedRows {
				return fmt.Errorf("invalid partition coverage %s", partition.File)
			}
			actual, err := fileDigest(filepath.Join(output, partition.File))
			if err != nil || actual != partition.SHA256 {
				return fmt.Errorf("invalid completed partition %s", partition.File)
			}
		}
		if manifest.Complete && len(manifest.Partitions) != (len(focals)+options.PartitionSize-1)/options.PartitionSize {
			return fmt.Errorf("completed manifest has incomplete focal coverage")
		}
	} else if !os.IsNotExist(readErr) {
		return readErr
	}
	if err = writeCountManifest(manifestPath, manifest); err != nil {
		return err
	}
	for start := len(manifest.Partitions) * options.PartitionSize; start < len(focals); start += options.PartitionSize {
		if err = checkDisk(output, options); err != nil {
			return err
		}
		end := start + options.PartitionSize
		if end > len(focals) {
			end = len(focals)
		}
		results := make([]FocalCount, end-start)
		jobs := make(chan int)
		var workers sync.WaitGroup
		for worker := 0; worker < options.Workers; worker++ {
			workers.Add(1)
			go func() {
				defer workers.Done()
				for offset := range jobs {
					results[offset] = CountFocal(graph, focals[start+offset], snapshot)
				}
			}()
		}
		for offset := range results {
			jobs <- offset
		}
		close(jobs)
		workers.Wait()
		partition := CountPartition{File: fmt.Sprintf("annual-%08d.jsonl.gz", start/options.PartitionSize), Rows: len(results)}
		path := filepath.Join(output, partition.File)
		file, err := os.Create(path + ".tmp")
		if err != nil {
			return err
		}
		compressed := gzip.NewWriter(file)
		encoder := json.NewEncoder(compressed)
		for _, result := range results {
			if result.Status != "complete" {
				partition.Unavailable++
			}
			for _, annual := range result.Annual {
				if !annual.CitationConsistent || !annual.NeighborhoodConsistent {
					partition.Warnings++
					break
				}
			}
			if err = encoder.Encode(result); err != nil {
				compressed.Close()
				file.Close()
				return err
			}
		}
		if err = compressed.Close(); err != nil {
			file.Close()
			return err
		}
		if err = file.Sync(); err != nil {
			file.Close()
			return err
		}
		if err = file.Close(); err != nil {
			return err
		}
		if err = os.Rename(path+".tmp", path); err != nil {
			return err
		}
		partition.SHA256, err = fileDigest(path)
		if err != nil {
			return err
		}
		manifest.Partitions = append(manifest.Partitions, partition)
		if err = writeCountManifest(manifestPath, manifest); err != nil {
			return err
		}
		fmt.Fprintf(os.Stderr, "completed %d / %d focal works\n", end, len(focals))
	}
	manifest.Complete = true
	return writeCountManifest(manifestPath, manifest)
}
