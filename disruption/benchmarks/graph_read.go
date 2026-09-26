package main

import (
	"encoding/json"
	"fmt"
	"os"
	"runtime"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

const nodes = 120000
const cohort = 4000
const samples = 2400000

type graph struct {
	offsets []int
	targets []uint32
}

func build() (graph, graph) {
	forward := graph{offsets: make([]int, nodes+1)}
	counts := make([]int, nodes)
	for source := 0; source < nodes; source++ {
		boundary := source / cohort * cohort
		if boundary > 0 {
			state := uint64(source + 1)
			seen := make(map[uint32]bool)
			for slot := 0; slot < 16; slot++ {
				state = state*6364136223846793005 + 1442695040888963407
				target := uint32((state >> 32) % uint64(boundary))
				if slot == 0 {
					target = uint32(source % 1024)
				}
				if !seen[target] {
					seen[target] = true
					forward.targets = append(forward.targets, target)
					counts[target]++
				}
			}
		}
		forward.offsets[source+1] = len(forward.targets)
	}
	backward := graph{offsets: make([]int, nodes+1), targets: make([]uint32, len(forward.targets))}
	for index, count := range counts {
		backward.offsets[index+1] = backward.offsets[index] + count
	}
	cursors := append([]int(nil), backward.offsets[:nodes]...)
	for source := 0; source < nodes; source++ {
		for _, target := range forward.targets[forward.offsets[source]:forward.offsets[source+1]] {
			backward.targets[cursors[target]] = uint32(source)
			cursors[target]++
		}
	}
	return forward, backward
}

func main() {
	workers, err := strconv.Atoi(os.Args[1])
	if err != nil || workers < 1 {
		panic("positive worker count required")
	}
	runtime.GOMAXPROCS(workers)
	buildStart := time.Now()
	forward, backward := build()
	buildSeconds := time.Since(buildStart).Seconds()
	var next atomic.Uint64
	var wait sync.WaitGroup
	results := make([]uint64, workers)
	start := time.Now()
	for worker := 0; worker < workers; worker++ {
		wait.Add(1)
		go func(worker int) {
			defer wait.Done()
			var checksum uint64
			marks := make([]uint32, nodes)
			masks := make([]uint8, nodes)
			touched := make([]uint32, 0, nodes)
			for {
				job := int(next.Add(1) - 1)
				if job >= samples {
					break
				}
				focal := cohort + ((job%24000)*7919)%(nodes-cohort)
				stamp := uint32(job + 1)
				touched = touched[:0]
				visit := func(target uint32, bit uint8) {
					age := int(target)/cohort - focal/cohort
					if age < 1 || age > 5 {
						return
					}
					if marks[target] != stamp {
						marks[target] = stamp
						masks[target] = 0
						touched = append(touched, target)
					}
					masks[target] |= bit
				}
				for _, target := range backward.targets[backward.offsets[focal]:backward.offsets[focal+1]] {
					visit(target, 1)
				}
				for _, reference := range forward.targets[forward.offsets[focal]:forward.offsets[focal+1]] {
					for _, target := range backward.targets[backward.offsets[reference]:backward.offsets[reference+1]] {
						visit(target, 2)
					}
				}
				var counts [4]uint64
				for _, target := range touched {
					counts[masks[target]]++
				}
				checksum += uint64(focal+1) * (counts[1] + 1009*counts[3] + 1000003*counts[2])
			}
			results[worker] = checksum
		}(worker)
	}
	wait.Wait()
	elapsed := time.Since(start).Seconds()
	var checksum uint64
	for _, result := range results {
		checksum += result
	}
	encoded, _ := json.Marshal(map[string]any{"language": "go", "workers": workers, "nodes": nodes, "edges": len(forward.targets), "focals": samples, "checksum": checksum, "build_seconds": buildSeconds, "compute_seconds": elapsed})
	fmt.Println(string(encoded))
}
