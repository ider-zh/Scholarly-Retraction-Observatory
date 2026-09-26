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
	"reflect"
	"sync"
	"syscall"
	"time"
)

type FullCountOptions struct {
	CountOptions
	BatchSize int `json:"batch_size"`
}

type fullJob struct {
	Manifest  CountManifest `json:"manifest"`
	BatchSize int           `json:"batch_size"`
}

type fullCheckpoint struct {
	ConfigSHA256 string         `json:"config_sha256"`
	Start        int            `json:"start"`
	End          int            `json:"end"`
	Partition    CountPartition `json:"partition"`
}

func fullDiskGuard(output string, options FullCountOptions, owned int64) error {
	var stat syscall.Statfs_t
	if err := syscall.Statfs(output, &stat); err != nil {
		return err
	}
	if uint64(stat.Bavail)*uint64(stat.Bsize) < options.MinimumFreeBytes {
		return fmt.Errorf("minimum free disk budget reached")
	}
	if options.MaximumOutputBytes > 0 && owned >= options.MaximumOutputBytes {
		return fmt.Errorf("output disk budget reached")
	}
	return nil
}

func fullFileSize(path string) int64 {
	info, err := os.Stat(path)
	if err != nil {
		return 0
	}
	return info.Size()
}

func FullCountGraph(graph *Graph, graphDir, output string, options FullCountOptions) error {
	if options.Workers < 1 || options.Workers > 40 || options.PartitionSize < 1 || options.BatchSize < 1 || options.BatchSize > options.PartitionSize {
		return fmt.Errorf("workers must be 1..40; batch and partition sizes positive with batch <= partition")
	}
	snapshot, err := time.Parse("2006-01-02", graph.SnapshotDate)
	if err != nil {
		return err
	}
	if err = os.MkdirAll(output, 0755); err != nil {
		return err
	}
	lock, err := os.OpenFile(filepath.Join(output, "full.lock"), os.O_CREATE|os.O_RDWR, 0644)
	if err != nil {
		return err
	}
	defer lock.Close()
	if err = syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		return fmt.Errorf("full count already locked: %w", err)
	}
	defer syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
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
	var idBytes [8]byte
	for _, id := range graph.IDs {
		binary.LittleEndian.PutUint64(idBytes[:], id)
		focalHash.Write(idBytes[:])
	}
	manifest := CountManifest{SchemaVersion: "disruption-annual-v1", CalculationVersion: "go-exact-full-v1", GraphManifestSHA256: graphHash, EngineSHA256: engineHash, SnapshotDate: graph.SnapshotDate, GeneratedAt: time.Now().UTC().Format(time.RFC3339), Scope: "all_graph_works", GraphWorks: len(graph.IDs), RequestedFocals: len(graph.IDs), FocalIDsSHA256: hex.EncodeToString(focalHash.Sum(nil)), SparseZeroRule: "Only complete focal rows within observed_age_start..observed_age_end permit absent annual bins to mean zero.", SparseZeroSemantics: "complete_observable_bins", Options: options.CountOptions, Partitions: []CountPartition{}}
	configBytes, _ := json.Marshal([]any{manifest.SchemaVersion, manifest.CalculationVersion, graphHash, engineHash, manifest.FocalIDsSHA256, graph.SnapshotDate, options.PartitionSize})
	configHash := sha256.Sum256(configBytes)
	manifest.ConfigSHA256 = hex.EncodeToString(configHash[:])
	jobPath := filepath.Join(output, "job.json")
	if data, readErr := os.ReadFile(jobPath); readErr == nil {
		var previous fullJob
		if err = json.Unmarshal(data, &previous); err != nil {
			return err
		}
		manifest.GeneratedAt = previous.Manifest.GeneratedAt
		manifest.Options = previous.Manifest.Options
		if previous.Manifest.Options.PartitionSize != options.PartitionSize || !reflect.DeepEqual(previous.Manifest, manifest) {
			return fmt.Errorf("full count configuration changed or job metadata invalid; use new output directory")
		}
	} else if !os.IsNotExist(readErr) {
		return readErr
	} else {
		entries, err := os.ReadDir(output)
		if err != nil {
			return err
		}
		for _, entry := range entries {
			if entry.Name() != "full.lock" && entry.Name() != "job.json.tmp" {
				return fmt.Errorf("new full count output is not empty: %s", entry.Name())
			}
		}
		if err = writeCountManifest(jobPath, fullJob{manifest, options.BatchSize}); err != nil {
			return err
		}
	}
	if err = writeCountManifest(filepath.Join(output, "invocation.json"), map[string]any{"started_at": time.Now().UTC().Format(time.RFC3339), "config_sha256": manifest.ConfigSHA256, "options": options}); err != nil {
		return err
	}
	checkpointDir := filepath.Join(output, "checkpoints")
	if err = os.MkdirAll(checkpointDir, 0755); err != nil {
		return err
	}
	partitionCount := (len(graph.IDs) + options.PartitionSize - 1) / options.PartitionSize
	completed := make(map[int]CountPartition)
	entries, err := os.ReadDir(checkpointDir)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if filepath.Ext(entry.Name()) == ".tmp" {
			continue
		}
		data, err := os.ReadFile(filepath.Join(checkpointDir, entry.Name()))
		if err != nil {
			return err
		}
		var checkpoint fullCheckpoint
		if err = json.Unmarshal(data, &checkpoint); err != nil {
			return err
		}
		index := checkpoint.Start / options.PartitionSize
		end := min(checkpoint.Start+options.PartitionSize, len(graph.IDs))
		if checkpoint.ConfigSHA256 != manifest.ConfigSHA256 || checkpoint.Start < 0 || checkpoint.Start%options.PartitionSize != 0 || index >= partitionCount || checkpoint.End != end || checkpoint.Partition.Rows != end-checkpoint.Start || entry.Name() != fmt.Sprintf("%08d.json", index) || checkpoint.Partition.File != fmt.Sprintf("annual-%08d.jsonl.gz", index) {
			return fmt.Errorf("invalid checkpoint coverage %s", entry.Name())
		}
		actual, err := fileDigest(filepath.Join(output, checkpoint.Partition.File))
		if err != nil || actual != checkpoint.Partition.SHA256 {
			return fmt.Errorf("invalid completed partition %s", checkpoint.Partition.File)
		}
		completed[index] = checkpoint.Partition
	}
	manifestPath := filepath.Join(output, "manifest.json")
	if data, readErr := os.ReadFile(manifestPath); readErr == nil {
		var published CountManifest
		if err = json.Unmarshal(data, &published); err != nil {
			return err
		}
		if !published.Complete || published.ConfigSHA256 != manifest.ConfigSHA256 || len(completed) != partitionCount {
			return fmt.Errorf("invalid final full manifest")
		}
		for index := 0; index < partitionCount; index++ {
			manifest.Partitions = append(manifest.Partitions, completed[index])
		}
		manifest.Complete = true
		if !reflect.DeepEqual(published, manifest) {
			return fmt.Errorf("final full manifest does not match checkpoints")
		}
		return nil
	} else if !os.IsNotExist(readErr) {
		return readErr
	}
	var owned int64
	if err = filepath.Walk(output, func(path string, info os.FileInfo, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if !info.IsDir() {
			owned += info.Size()
		}
		return nil
	}); err != nil {
		return err
	}
	type batchJob struct {
		focal   uint32
		offset  int
		results []FocalCount
		done    *sync.WaitGroup
	}
	jobs := make(chan batchJob, options.Workers)
	var workers sync.WaitGroup
	for worker := 0; worker < options.Workers; worker++ {
		workers.Add(1)
		go func() {
			defer workers.Done()
			scratch := NewCountScratch(len(graph.IDs))
			for job := range jobs {
				job.results[job.offset] = CountFocalWithScratch(graph, job.focal, snapshot, scratch)
				job.done.Done()
			}
		}()
	}
	defer func() { close(jobs); workers.Wait() }()
	lastProgress := time.Now()
	for index := 0; index < partitionCount; index++ {
		if _, exists := completed[index]; exists {
			continue
		}
		if err = fullDiskGuard(output, options, owned); err != nil {
			return err
		}
		start := index * options.PartitionSize
		end := min(start+options.PartitionSize, len(graph.IDs))
		partition := CountPartition{File: fmt.Sprintf("annual-%08d.jsonl.gz", index), Rows: end - start}
		path := filepath.Join(output, partition.File)
		oldBytes := fullFileSize(path) + fullFileSize(path+".tmp")
		file, err := os.Create(path + ".tmp")
		if err != nil {
			return err
		}
		hash := sha256.New()
		compressed, err := gzip.NewWriterLevel(io.MultiWriter(file, hash), gzip.BestSpeed)
		if err != nil {
			file.Close()
			return err
		}
		encoder := json.NewEncoder(compressed)
		writeErr := func() error {
			for batchStart := start; batchStart < end; batchStart += options.BatchSize {
				results := make([]FocalCount, min(options.BatchSize, end-batchStart))
				var done sync.WaitGroup
				done.Add(len(results))
				for offset := range results {
					jobs <- batchJob{uint32(batchStart + offset), offset, results, &done}
				}
				done.Wait()
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
					if err := encoder.Encode(result); err != nil {
						return err
					}
				}
				if err := compressed.Flush(); err != nil {
					return err
				}
				if err := fullDiskGuard(output, options, owned-oldBytes+fullFileSize(path)+fullFileSize(path+".tmp")); err != nil {
					return err
				}
				if time.Since(lastProgress) >= 30*time.Second {
					progressPath := filepath.Join(output, "progress.json")
					previousBytes := fullFileSize(progressPath)
					if err := writeCountManifest(progressPath, map[string]any{"config_sha256": manifest.ConfigSHA256, "updated_at": time.Now().UTC().Format(time.RFC3339), "completed_partitions": len(completed), "total_partitions": partitionCount, "active_partition": index, "active_partition_rows_processed": batchStart + len(results) - start, "active_partition_rows_total": end - start, "active_partition_durable": false}); err != nil {
						return err
					}
					owned += fullFileSize(progressPath) - previousBytes
					lastProgress = time.Now()
				}
			}
			return nil
		}()
		closeErr := compressed.Close()
		if writeErr != nil {
			file.Close()
			return writeErr
		}
		if closeErr != nil {
			file.Close()
			return closeErr
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
		directory, err := os.Open(output)
		if err != nil {
			return err
		}
		err = directory.Sync()
		directory.Close()
		if err != nil {
			return err
		}
		partition.SHA256 = hex.EncodeToString(hash.Sum(nil))
		checkpointPath := filepath.Join(checkpointDir, fmt.Sprintf("%08d.json", index))
		oldCheckpointBytes := fullFileSize(checkpointPath) + fullFileSize(checkpointPath+".tmp")
		if err = writeCountManifest(checkpointPath, fullCheckpoint{manifest.ConfigSHA256, start, end, partition}); err != nil {
			return err
		}
		owned += fullFileSize(path) - oldBytes + fullFileSize(checkpointPath) - oldCheckpointBytes
		completed[index] = partition
		fmt.Fprintf(os.Stderr, "full count checkpoint %d / %d; %d focal rows in partition\n", len(completed), partitionCount, partition.Rows)
	}
	for index := 0; index < partitionCount; index++ {
		manifest.Partitions = append(manifest.Partitions, completed[index])
	}
	manifest.Complete = true
	return writeCountManifest(manifestPath, manifest)
}
