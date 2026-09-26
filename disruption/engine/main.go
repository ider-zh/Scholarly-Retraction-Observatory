package main

import (
	"bufio"
	"container/heap"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type benchmarkCandidate struct {
	Focal uint32 `json:"focal_index"`
	Score uint64 `json:"score"`
}
type candidateHeap []benchmarkCandidate

func (values candidateHeap) Len() int { return len(values) }
func (values candidateHeap) Less(left, right int) bool {
	if values[left].Score == values[right].Score {
		return values[left].Focal > values[right].Focal
	}
	return values[left].Score < values[right].Score
}
func (values candidateHeap) Swap(left, right int) {
	values[left], values[right] = values[right], values[left]
}
func (values *candidateHeap) Push(value any) { *values = append(*values, value.(benchmarkCandidate)) }
func (values *candidateHeap) Pop() any {
	previous := *values
	last := previous[len(previous)-1]
	*values = previous[:len(previous)-1]
	return last
}

func benchmarkFocals(graph *Graph, size int) ([]uint32, map[string][]benchmarkCandidate) {
	strata := map[string][]benchmarkCandidate{}
	indegree, references, neighborhoods := &candidateHeap{}, &candidateHeap{}, &candidateHeap{}
	add := func(values *candidateHeap, candidate benchmarkCandidate) {
		if values.Len() < size {
			heap.Push(values, candidate)
		} else if candidate.Score > (*values)[0].Score {
			(*values)[0] = candidate
			heap.Fix(values, 0)
		}
	}
	for index := range graph.IDs {
		focal := uint32(index)
		add(indegree, benchmarkCandidate{focal, graph.IncomingOffsets[focal+1] - graph.IncomingOffsets[focal]})
		add(references, benchmarkCandidate{focal, graph.Offsets[focal+1] - graph.Offsets[focal]})
		var exposure uint64
		for _, reference := range graph.Targets[graph.Offsets[focal]:graph.Offsets[focal+1]] {
			if graph.Years[reference] > 0 && graph.Years[reference] < graph.Years[focal] {
				exposure += graph.IncomingOffsets[reference+1] - graph.IncomingOffsets[reference]
			}
		}
		add(neighborhoods, benchmarkCandidate{focal, exposure})
	}
	strata["highest_indegree"] = []benchmarkCandidate(*indegree)
	strata["highest_resolved_reference_count"] = []benchmarkCandidate(*references)
	strata["highest_effective_reference_incoming_exposure"] = []benchmarkCandidate(*neighborhoods)
	for index := 0; index < size && index < len(graph.IDs); index++ {
		focal := uint32(uint64(index) * uint64(len(graph.IDs)) / uint64(size))
		strata["evenly_spaced_graph_nodes"] = append(strata["evenly_spaced_graph_nodes"], benchmarkCandidate{focal, 0})
	}
	selected := map[uint32]bool{}
	for name, values := range strata {
		sort.Slice(values, func(left, right int) bool {
			return values[left].Score > values[right].Score || (values[left].Score == values[right].Score && values[left].Focal < values[right].Focal)
		})
		strata[name] = values
		for _, candidate := range values {
			selected[candidate.Focal] = true
		}
	}
	focals := make([]uint32, 0, len(selected))
	for focal := range selected {
		focals = append(focals, focal)
	}
	sort.Slice(focals, func(left, right int) bool { return focals[left] < focals[right] })
	return focals, strata
}

func run(arguments []string) error {
	if len(arguments) == 0 {
		return fmt.Errorf("usage: disruption-engine build|count|full [options]")
	}
	switch arguments[0] {
	case "full":
		flags := flag.NewFlagSet("full", flag.ContinueOnError)
		graphDir := flags.String("graph", "", "compressed graph directory")
		output := flags.String("output", "", "dedicated full annual count directory")
		verifyBenchmark := flags.String("verify-benchmark", "", "completed legacy annual benchmark manifest to independently verify before full counting")
		workers := flags.Int("workers", 40, "shared graph worker count (1..40)")
		partition := flags.Int("partition-size", 100000, "focals per checkpoint")
		batch := flags.Int("batch-size", 1000, "maximum in-memory output rows")
		minimumFree := flags.Uint64("minimum-free-bytes", 1000000000000, "minimum filesystem free bytes")
		maximumOutput := flags.Int64("maximum-output-bytes", 4000000000000, "maximum owned output bytes")
		if err := flags.Parse(arguments[1:]); err != nil {
			return err
		}
		if *graphDir == "" || *output == "" {
			return fmt.Errorf("--graph and --output are required")
		}
		graph, err := LoadGraph(*graphDir)
		if err != nil {
			return err
		}
		if *verifyBenchmark != "" {
			if err = VerifyBenchmark(graph, *graphDir, *verifyBenchmark); err != nil {
				return err
			}
		}
		return FullCountGraph(graph, *graphDir, *output, FullCountOptions{CountOptions: CountOptions{Workers: *workers, PartitionSize: *partition, MinimumFreeBytes: *minimumFree, MaximumOutputBytes: *maximumOutput}, BatchSize: *batch})
	case "build":
		flags := flag.NewFlagSet("build", flag.ContinueOnError)
		input := flags.String("input", "", "completed graph bridge manifest")
		output := flags.String("output", "", "new compressed graph directory")
		if err := flags.Parse(arguments[1:]); err != nil {
			return err
		}
		if *input == "" || *output == "" {
			return fmt.Errorf("--input and --output are required")
		}
		graph, err := BuildGraph(*input)
		if err != nil {
			return err
		}
		return SaveGraph(graph, *output, *input)
	case "count":
		flags := flag.NewFlagSet("count", flag.ContinueOnError)
		graphDir := flags.String("graph", "", "compressed graph directory")
		output := flags.String("output", "", "versioned output directory")
		workers := flags.Int("workers", 40, "shared graph worker count (1..40)")
		partition := flags.Int("partition-size", 1000, "focals per atomic compressed partition")
		start := flags.Int("start", 0, "first graph node index")
		limit := flags.Int("limit", 0, "bounded focal count")
		all := flags.Bool("all", false, "explicitly request every focal Work")
		idsFile := flags.String("focal-ids", "", "one numeric or URL OpenAlex Work ID per line")
		benchmarkSize := flags.Int("benchmark-size", 0, "select this many per high-indegree/reference/neighborhood and evenly-spaced stratum; scans canonical edges once")
		minimumFree := flags.Uint64("minimum-free-bytes", 1000000000000, "minimum filesystem free bytes; use 0 only for small fixtures")
		maximumOutput := flags.Int64("maximum-output-bytes", 4000000000000, "maximum owned output bytes")
		if err := flags.Parse(arguments[1:]); err != nil {
			return err
		}
		if *graphDir == "" || *output == "" {
			return fmt.Errorf("--graph and --output are required")
		}
		if *start < 0 || *limit < 0 || *benchmarkSize < 0 {
			return fmt.Errorf("start and limit must be nonnegative")
		}
		if *benchmarkSize > 0 && (*all || *limit != 0 || *start != 0 || *idsFile != "") {
			return fmt.Errorf("--benchmark-size cannot combine with other focal selectors")
		}
		if *all && (*limit != 0 || *start != 0 || *idsFile != "") {
			return fmt.Errorf("--all cannot combine with subset selectors")
		}
		if *idsFile != "" && (*limit != 0 || *start != 0) {
			return fmt.Errorf("--focal-ids cannot combine with --start/--limit")
		}
		if !*all && *limit == 0 && *idsFile == "" && *benchmarkSize == 0 {
			return fmt.Errorf("choose --limit, --focal-ids, or explicit --all; no automatic full production scan")
		}
		graph, err := LoadGraph(*graphDir)
		if err != nil {
			return err
		}
		focals := []uint32{}
		if *benchmarkSize > 0 {
			var strata map[string][]benchmarkCandidate
			focals, strata = benchmarkFocals(graph, *benchmarkSize)
			if err = os.MkdirAll(*output, 0755); err != nil {
				return err
			}
			if err = writeCountManifest(filepath.Join(*output, "benchmark-selection.json"), map[string]any{"strata": strata, "graph_directory": *graphDir, "snapshot_date": graph.SnapshotDate, "note": "Full canonical graph used; selected focals are a stress sample, not a representative estimator. Neighborhood exposure sums paths only for workload selection, never for NR."}); err != nil {
				return err
			}
		} else if *idsFile != "" {
			file, err := os.Open(*idsFile)
			if err != nil {
				return err
			}
			defer file.Close()
			scanner := bufio.NewScanner(file)
			requested := map[uint64]bool{}
			for scanner.Scan() {
				value := strings.TrimSpace(scanner.Text())
				if value == "" {
					continue
				}
				value = strings.TrimPrefix(value, "https://openalex.org/")
				value = strings.TrimPrefix(value, "W")
				id, err := strconv.ParseUint(value, 10, 64)
				if err != nil {
					return fmt.Errorf("invalid focal ID: %s", value)
				}
				if requested[id] {
					return fmt.Errorf("duplicate focal Work W%d", id)
				}
				requested[id] = true
			}
			if err = scanner.Err(); err != nil {
				return err
			}
			for index, id := range graph.IDs {
				if requested[id] {
					focals = append(focals, uint32(index))
					delete(requested, id)
				}
			}
			for id := range requested {
				return fmt.Errorf("focal Work W%d not in graph", id)
			}
		} else {
			end := len(graph.IDs)
			if !*all && *limit < end-*start {
				end = *start + *limit
			}
			if *start > len(graph.IDs) {
				return fmt.Errorf("start exceeds node count")
			}
			for index := *start; index < end; index++ {
				focals = append(focals, uint32(index))
			}
		}
		return CountGraph(graph, *graphDir, *output, focals, CountOptions{Workers: *workers, PartitionSize: *partition, MinimumFreeBytes: *minimumFree, MaximumOutputBytes: *maximumOutput})
	default:
		return fmt.Errorf("unknown command %s", arguments[0])
	}
}

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
