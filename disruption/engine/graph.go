package main

import (
	"bufio"
	"compress/gzip"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"math"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"sync"
	"sync/atomic"
	"time"
)

const GraphCalculationVersion = "graph-transform-v1"

type Audit struct {
	Invalid     uint64 `json:"invalid"`
	Duplicate   uint64 `json:"duplicate"`
	Dangling    uint64 `json:"dangling"`
	SelfLoop    uint64 `json:"self_loop"`
	SameYear    uint64 `json:"same_year"`
	FutureYear  uint64 `json:"future_year"`
	UnknownYear uint64 `json:"unknown_year"`
}

type Graph struct {
	IDs                    []uint64
	Years                  []int32
	CitedBy                []int64
	RawReferenceCounts     []int64
	Offsets                []uint64
	Targets                []uint32
	IncomingOffsets        []uint64
	Incoming               []uint32
	Audit                  []Audit
	SnapshotDate           string
	FoundationConfigSHA256 string
	BridgeManifestSHA256   string
}

type bridgeShard struct {
	Nodes            string `json:"nodes"`
	References       string `json:"references"`
	Rows             uint64 `json:"rows"`
	NodesSHA256      string `json:"nodes_sha256"`
	ReferencesSHA256 string `json:"references_sha256"`
}

type bridgeManifest struct {
	SchemaVersion          string        `json:"schema_version"`
	Status                 string        `json:"status"`
	SnapshotDate           string        `json:"snapshot_date"`
	FoundationConfigSHA256 string        `json:"foundation_config_sha256"`
	Shards                 []bridgeShard `json:"shards"`
	Rows                   *uint64       `json:"rows,omitempty"`
	TotalRows              *uint64       `json:"total_rows,omitempty"`
}

type graphFile struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
	Count  uint64 `json:"count"`
	Width  int    `json:"width"`
}

type graphManifest struct {
	SchemaVersion          string               `json:"schema_version"`
	Status                 string               `json:"status"`
	SnapshotDate           string               `json:"snapshot_date"`
	FoundationConfigSHA256 string               `json:"foundation_config_sha256"`
	BridgeManifestSHA256   string               `json:"bridge_manifest_sha256"`
	NodeCount              uint64               `json:"node_count"`
	EdgeCount              uint64               `json:"edge_count"`
	Files                  map[string]graphFile `json:"files"`
	CalculationVersion     string               `json:"calculation_version"`
	EngineBinarySHA256     string               `json:"engine_binary_sha256"`
	GeneratedAt            string               `json:"generated_at"`
}

func localGraphPath(base, name string) (string, error) {
	if name == "" || filepath.IsAbs(name) || !filepath.IsLocal(name) {
		return "", fmt.Errorf("unsafe relative graph path %q", name)
	}
	return filepath.Join(base, name), nil
}

func checkedGzip(path, expected string, consume func(io.Reader) error) error {
	if decoded, err := hex.DecodeString(expected); err != nil || len(decoded) != sha256.Size {
		return fmt.Errorf("invalid SHA256 for %s", path)
	}
	file, err := os.Open(path)
	if err != nil {
		return err
	}
	defer file.Close()
	hasher := sha256.New()
	compressed, err := gzip.NewReader(io.TeeReader(file, hasher))
	if err != nil {
		return fmt.Errorf("%s: %w", path, err)
	}
	defer compressed.Close()
	reader := bufio.NewReaderSize(compressed, 1<<20)
	if err := consume(reader); err != nil {
		return fmt.Errorf("%s: %w", path, err)
	}
	if _, err := reader.ReadByte(); err != io.EOF {
		if err == nil {
			return fmt.Errorf("%s: unexpected trailing records", path)
		}
		return fmt.Errorf("%s: %w", path, err)
	}
	if actual := hex.EncodeToString(hasher.Sum(nil)); actual != expected {
		return fmt.Errorf("%s: SHA256 mismatch", path)
	}
	return nil
}

func BuildGraph(inputPath string) (*Graph, error) {
	manifestBytes, err := os.ReadFile(inputPath)
	if err != nil {
		return nil, err
	}
	var manifest bridgeManifest
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		return nil, err
	}
	if manifest.SchemaVersion != "graph-bridge-v1" || manifest.Status != "complete" || len(manifest.Shards) == 0 {
		return nil, errors.New("bridge must be a complete graph-bridge-v1 manifest with shards")
	}
	if _, err := time.Parse("2006-01-02", manifest.SnapshotDate); err != nil {
		return nil, fmt.Errorf("invalid bridge snapshot date: %w", err)
	}
	var nodeCount uint64
	for _, shard := range manifest.Shards {
		if shard.Rows > math.MaxUint32-nodeCount {
			return nil, errors.New("graph exceeds uint32 node capacity")
		}
		nodeCount += shard.Rows
	}
	if nodeCount == 0 {
		return nil, errors.New("empty graph")
	}
	for _, declaredRows := range []*uint64{manifest.Rows, manifest.TotalRows} {
		if declaredRows != nil && *declaredRows != nodeCount {
			return nil, errors.New("bridge total rows differs from shard rows")
		}
	}
	manifestHash := sha256.Sum256(manifestBytes)
	log.Printf("graph build: phase=nodes nodes=%d shards=%d", nodeCount, len(manifest.Shards))
	graph := &Graph{
		IDs: make([]uint64, nodeCount), Years: make([]int32, nodeCount),
		CitedBy: make([]int64, nodeCount), RawReferenceCounts: make([]int64, nodeCount),
		Offsets: make([]uint64, nodeCount+1), IncomingOffsets: make([]uint64, nodeCount+1),
		Audit: make([]Audit, nodeCount), SnapshotDate: manifest.SnapshotDate,
		FoundationConfigSHA256: manifest.FoundationConfigSHA256,
		BridgeManifestSHA256:   hex.EncodeToString(manifestHash[:]),
	}
	index := make(map[uint64]uint32, nodeCount)
	base := filepath.Dir(inputPath)
	var ordinal uint64
	for shardIndex, shard := range manifest.Shards {
		path, err := localGraphPath(base, shard.Nodes)
		if err != nil {
			return nil, err
		}
		if (shardIndex+1)%25 == 0 || shardIndex+1 == len(manifest.Shards) {
			log.Printf("graph build: phase=nodes shards=%d/%d rows=%d/%d", shardIndex+1, len(manifest.Shards), ordinal, nodeCount)
		}
		err = checkedGzip(path, shard.NodesSHA256, func(reader io.Reader) error {
			var record [32]byte
			for row := uint64(0); row < shard.Rows; row++ {
				if _, err := io.ReadFull(reader, record[:]); err != nil {
					return err
				}
				id := binary.LittleEndian.Uint64(record[0:8])
				year := int32(binary.LittleEndian.Uint32(record[8:12]))
				flags := binary.LittleEndian.Uint32(record[12:16])
				citedBy := int64(binary.LittleEndian.Uint64(record[16:24]))
				rawCount := int64(binary.LittleEndian.Uint64(record[24:32]))
				if id == 0 || flags != 0 || year < 0 || year > 9999 || citedBy < -1 || rawCount < -1 {
					return fmt.Errorf("invalid node record %d", ordinal)
				}
				if _, exists := index[id]; exists {
					return fmt.Errorf("duplicate Work ID %d", id)
				}
				index[id] = uint32(ordinal)
				graph.IDs[ordinal], graph.Years[ordinal] = id, year
				graph.CitedBy[ordinal], graph.RawReferenceCounts[ordinal] = citedBy, rawCount
				ordinal++
			}
			return nil
		})
		if err != nil {
			return nil, err
		}
	}
	shardStarts := make([]uint64, len(manifest.Shards))
	for shardIndex := 1; shardIndex < len(manifest.Shards); shardIndex++ {
		shardStarts[shardIndex] = shardStarts[shardIndex-1] + manifest.Shards[shardIndex-1].Rows
	}
	for pass := 0; pass < 2; pass++ {
		log.Printf("graph build: phase=references pass=%d/2 shards=%d", pass+1, len(manifest.Shards))
		var completed atomic.Int64
		err := parallelGraphTasks(len(manifest.Shards), func(shardIndex int) error {
			shard := manifest.Shards[shardIndex]
			ordinal := shardStarts[shardIndex]
			path, err := localGraphPath(base, shard.References)
			if err != nil {
				return err
			}
			err = checkedGzip(path, shard.ReferencesSHA256, func(reader io.Reader) error {
				var header [16]byte
				var rawTargets []uint64
				for row := uint64(0); row < shard.Rows; row++ {
					if _, err := io.ReadFull(reader, header[:]); err != nil {
						return err
					}
					sourceID := binary.LittleEndian.Uint64(header[:8])
					length := int64(binary.LittleEndian.Uint64(header[8:]))
					if sourceID != graph.IDs[ordinal] || length != graph.RawReferenceCounts[ordinal] {
						return fmt.Errorf("reference row %d does not match node source/count", ordinal)
					}
					rawTargets = rawTargets[:0]
					var encoded [8]byte
					for position := int64(0); position < length; position++ {
						if _, err := io.ReadFull(reader, encoded[:]); err != nil {
							return err
						}
						rawTargets = append(rawTargets, binary.LittleEndian.Uint64(encoded[:]))
					}
					sort.Slice(rawTargets, func(left, right int) bool { return rawTargets[left] < rawTargets[right] })
					var audit Audit
					var cursor uint64
					if pass == 1 {
						cursor = graph.Offsets[ordinal]
					}
					for position, targetID := range rawTargets {
						if targetID == 0 {
							audit.Invalid++
							continue
						}
						duplicate := position > 0 && targetID == rawTargets[position-1]
						if duplicate {
							audit.Duplicate++
						}
						if targetID == sourceID {
							audit.SelfLoop++
							continue
						}
						target, exists := index[targetID]
						if !exists {
							audit.Dangling++
							continue
						}
						if duplicate {
							continue
						}
						sourceYear, targetYear := graph.Years[ordinal], graph.Years[target]
						switch {
						case sourceYear == 0 || targetYear == 0:
							audit.UnknownYear++
						case targetYear == sourceYear:
							audit.SameYear++
						case targetYear > sourceYear:
							audit.FutureYear++
						}
						if pass == 0 {
							graph.Offsets[ordinal+1]++
							atomic.AddUint64(&graph.IncomingOffsets[uint64(target)+1], 1)
						} else {
							if cursor >= graph.Offsets[ordinal+1] {
								return errors.New("reference edges changed between passes")
							}
							graph.Targets[cursor] = target
							cursor++
						}
					}
					if pass == 0 {
						graph.Audit[ordinal] = audit
					} else if cursor != graph.Offsets[ordinal+1] || audit != graph.Audit[ordinal] {
						return errors.New("reference audit changed between passes")
					}
					ordinal++
				}
				return nil
			})
			if err != nil {
				return err
			}
			done := completed.Add(1)
			if done%25 == 0 || done == int64(len(manifest.Shards)) {
				log.Printf("graph build: phase=references pass=%d/2 shards=%d/%d", pass+1, done, len(manifest.Shards))
			}
			return nil
		})
		if err != nil {
			return nil, err
		}
		if pass == 0 {
			for node := uint64(1); node <= nodeCount; node++ {
				if math.MaxUint64-graph.Offsets[node-1] < graph.Offsets[node] {
					return nil, errors.New("edge count overflow")
				}
				graph.Offsets[node] += graph.Offsets[node-1]
				graph.IncomingOffsets[node] += graph.IncomingOffsets[node-1]
			}
			edges := graph.Offsets[nodeCount]
			log.Printf("graph build: phase=allocate-csr nodes=%d canonical_edges=%d", nodeCount, edges)
			if edges > uint64(int(^uint(0)>>1))/4 {
				return nil, errors.New("edge arrays exceed addressable memory")
			}
			graph.Targets, graph.Incoming = make([]uint32, edges), make([]uint32, edges)
		}
	}
	cursors := append([]uint64(nil), graph.IncomingOffsets[:nodeCount]...)
	log.Printf("graph build: phase=incoming-csr nodes=%d", nodeCount)
	for source := uint64(0); source < nodeCount; source++ {
		for _, target := range graph.Targets[graph.Offsets[source]:graph.Offsets[source+1]] {
			graph.Incoming[cursors[target]] = uint32(source)
			cursors[target]++
		}
		if (source+1)%10000000 == 0 || source+1 == nodeCount {
			log.Printf("graph build: phase=incoming-csr nodes=%d/%d", source+1, nodeCount)
		}
	}
	log.Printf("graph build: complete nodes=%d canonical_edges=%d", nodeCount, len(graph.Targets))
	return graph, nil
}

func parallelGraphTasks(count int, task func(int) error) error {
	workers := runtime.GOMAXPROCS(0)
	if workers > 40 {
		workers = 40
	}
	if workers > count {
		workers = count
	}
	var group sync.WaitGroup
	var next atomic.Int64
	var failed atomic.Bool
	var firstError error
	var once sync.Once
	for worker := 0; worker < workers; worker++ {
		group.Add(1)
		go func() {
			defer group.Done()
			for !failed.Load() {
				index := int(next.Add(1) - 1)
				if index >= count {
					return
				}
				if err := task(index); err != nil {
					once.Do(func() { firstError = err; failed.Store(true) })
					return
				}
			}
		}()
	}
	group.Wait()
	return firstError
}

func writeGraphArray(directory, name string, count uint64, width int, encode func(uint64, []byte)) (graphFile, error) {
	result := graphFile{Path: name + ".bin.gz", Count: count, Width: width}
	file, err := os.OpenFile(filepath.Join(directory, result.Path), os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0644)
	if err != nil {
		return result, err
	}
	defer file.Close()
	hasher := sha256.New()
	compressed, err := gzip.NewWriterLevel(io.MultiWriter(file, hasher), gzip.BestSpeed)
	if err != nil {
		return result, err
	}
	buffer := make([]byte, width*8192)
	for start := uint64(0); start < count; {
		batch := uint64(8192)
		if count-start < batch {
			batch = count - start
		}
		for offset := uint64(0); offset < batch; offset++ {
			encode(start+offset, buffer[int(offset)*width:int(offset+1)*width])
		}
		if _, err := compressed.Write(buffer[:int(batch)*width]); err != nil {
			compressed.Close()
			return result, err
		}
		start += batch
	}
	if err := compressed.Close(); err != nil {
		return result, err
	}
	if err := file.Sync(); err != nil {
		return result, err
	}
	if err := file.Close(); err != nil {
		return result, err
	}
	result.SHA256 = hex.EncodeToString(hasher.Sum(nil))
	return result, nil
}

func SaveGraph(graph *Graph, outputDir string, bridgeManifestPath string) error {
	if err := validateGraph(graph); err != nil {
		return err
	}
	bridgeBytes, err := os.ReadFile(bridgeManifestPath)
	if err != nil {
		return err
	}
	bridgeHash := sha256.Sum256(bridgeBytes)
	if hex.EncodeToString(bridgeHash[:]) != graph.BridgeManifestSHA256 {
		return errors.New("bridge manifest changed since graph build")
	}
	if _, err := os.Lstat(outputDir); err == nil {
		return errors.New("graph output already exists; refusing overwrite")
	} else if !os.IsNotExist(err) {
		return err
	}
	parent := filepath.Dir(outputDir)
	if err := os.MkdirAll(parent, 0755); err != nil {
		return err
	}
	temporary, err := os.MkdirTemp(parent, ".graph-build-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(temporary)
	executable, err := os.Executable()
	if err != nil {
		return err
	}
	binaryFile, err := os.Open(executable)
	if err != nil {
		return err
	}
	binaryHash := sha256.New()
	_, hashErr := io.Copy(binaryHash, binaryFile)
	closeErr := binaryFile.Close()
	if hashErr != nil {
		return hashErr
	}
	if closeErr != nil {
		return closeErr
	}
	manifest := graphManifest{SchemaVersion: "disruption-graph-v1", Status: "complete", SnapshotDate: graph.SnapshotDate, FoundationConfigSHA256: graph.FoundationConfigSHA256, BridgeManifestSHA256: graph.BridgeManifestSHA256, NodeCount: uint64(len(graph.IDs)), EdgeCount: uint64(len(graph.Targets)), Files: make(map[string]graphFile), CalculationVersion: GraphCalculationVersion, EngineBinarySHA256: hex.EncodeToString(binaryHash.Sum(nil)), GeneratedAt: time.Now().UTC().Format(time.RFC3339Nano)}
	var tasks []func() error
	var manifestMutex sync.Mutex
	write := func(name string, count uint64, width int, encode func(uint64, []byte)) error {
		tasks = append(tasks, func() error {
			file, err := writeGraphArray(temporary, name, count, width, encode)
			if err == nil {
				manifestMutex.Lock()
				manifest.Files[name] = file
				manifestMutex.Unlock()
			}
			return err
		})
		return nil
	}
	arrays64 := map[string][]uint64{"ids": graph.IDs, "offsets": graph.Offsets, "incoming_offsets": graph.IncomingOffsets}
	for name, values := range arrays64 {
		if err := write(name, uint64(len(values)), 8, func(index uint64, target []byte) { binary.LittleEndian.PutUint64(target, values[index]) }); err != nil {
			return err
		}
	}
	arraysSigned := map[string][]int64{"cited_by": graph.CitedBy, "raw_reference_counts": graph.RawReferenceCounts}
	for name, values := range arraysSigned {
		if err := write(name, uint64(len(values)), 8, func(index uint64, target []byte) { binary.LittleEndian.PutUint64(target, uint64(values[index])) }); err != nil {
			return err
		}
	}
	arrays32 := map[string][]uint32{"targets": graph.Targets, "incoming": graph.Incoming}
	for name, values := range arrays32 {
		if err := write(name, uint64(len(values)), 4, func(index uint64, target []byte) { binary.LittleEndian.PutUint32(target, values[index]) }); err != nil {
			return err
		}
	}
	if err := write("years", uint64(len(graph.Years)), 4, func(index uint64, target []byte) { binary.LittleEndian.PutUint32(target, uint32(graph.Years[index])) }); err != nil {
		return err
	}
	if err := write("audit", uint64(len(graph.Audit)), 56, func(index uint64, target []byte) {
		audit := graph.Audit[index]
		values := [...]uint64{audit.Invalid, audit.Duplicate, audit.Dangling, audit.SelfLoop, audit.SameYear, audit.FutureYear, audit.UnknownYear}
		for position, value := range values {
			binary.LittleEndian.PutUint64(target[position*8:], value)
		}
	}); err != nil {
		return err
	}
	if err := parallelGraphTasks(len(tasks), func(index int) error { return tasks[index]() }); err != nil {
		return err
	}
	encoded, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(temporary, "manifest.json"), append(encoded, '\n'), 0644); err != nil {
		return err
	}
	for _, path := range []string{filepath.Join(temporary, "manifest.json"), temporary} {
		file, err := os.Open(path)
		if err != nil {
			return err
		}
		err = file.Sync()
		closeErr := file.Close()
		if err != nil {
			return err
		}
		if closeErr != nil {
			return closeErr
		}
	}
	if err := os.Rename(temporary, outputDir); err != nil {
		return err
	}
	directory, err := os.Open(parent)
	if err != nil {
		return err
	}
	defer directory.Close()
	return directory.Sync()
}

func readGraphArray(directory string, file graphFile, count uint64, width int, decode func(uint64, []byte)) error {
	if file.Count != count || file.Width != width {
		return errors.New("graph array dimensions differ from manifest")
	}
	path, err := localGraphPath(directory, file.Path)
	if err != nil {
		return err
	}
	return checkedGzip(path, file.SHA256, func(reader io.Reader) error {
		buffer := make([]byte, width*8192)
		for start := uint64(0); start < count; {
			batch := uint64(8192)
			if count-start < batch {
				batch = count - start
			}
			if _, err := io.ReadFull(reader, buffer[:int(batch)*width]); err != nil {
				return err
			}
			for offset := uint64(0); offset < batch; offset++ {
				decode(start+offset, buffer[int(offset)*width:int(offset+1)*width])
			}
			start += batch
		}
		return nil
	})
}

func LoadGraph(graphDir string) (*Graph, error) {
	encoded, err := os.ReadFile(filepath.Join(graphDir, "manifest.json"))
	if err != nil {
		return nil, err
	}
	var manifest graphManifest
	if err := json.Unmarshal(encoded, &manifest); err != nil {
		return nil, err
	}
	if manifest.SchemaVersion != "disruption-graph-v1" || manifest.Status != "complete" || manifest.NodeCount == 0 || manifest.NodeCount > math.MaxUint32 || manifest.EdgeCount > uint64(int(^uint(0)>>1))/4 {
		return nil, errors.New("invalid graph manifest")
	}
	if manifest.CalculationVersion != GraphCalculationVersion {
		return nil, errors.New("unsupported graph calculation version")
	}
	if _, err := time.Parse("2006-01-02", manifest.SnapshotDate); err != nil {
		return nil, errors.New("invalid graph snapshot date")
	}
	if _, err := time.Parse(time.RFC3339Nano, manifest.GeneratedAt); err != nil {
		return nil, errors.New("invalid graph generation timestamp")
	}
	for _, digest := range []string{manifest.EngineBinarySHA256, manifest.BridgeManifestSHA256} {
		if decoded, err := hex.DecodeString(digest); err != nil || len(decoded) != sha256.Size {
			return nil, errors.New("invalid graph provenance hash")
		}
	}
	nodeCount, edgeCount := manifest.NodeCount, manifest.EdgeCount
	graph := &Graph{IDs: make([]uint64, nodeCount), Years: make([]int32, nodeCount), CitedBy: make([]int64, nodeCount), RawReferenceCounts: make([]int64, nodeCount), Offsets: make([]uint64, nodeCount+1), IncomingOffsets: make([]uint64, nodeCount+1), Targets: make([]uint32, edgeCount), Incoming: make([]uint32, edgeCount), Audit: make([]Audit, nodeCount), SnapshotDate: manifest.SnapshotDate, FoundationConfigSHA256: manifest.FoundationConfigSHA256, BridgeManifestSHA256: manifest.BridgeManifestSHA256}
	var tasks []func() error
	read := func(name string, count uint64, width int, decode func(uint64, []byte)) error {
		file, exists := manifest.Files[name]
		if !exists {
			return fmt.Errorf("missing graph array %s", name)
		}
		tasks = append(tasks, func() error { return readGraphArray(graphDir, file, count, width, decode) })
		return nil
	}
	for name, values := range map[string][]uint64{"ids": graph.IDs, "offsets": graph.Offsets, "incoming_offsets": graph.IncomingOffsets} {
		if err := read(name, uint64(len(values)), 8, func(index uint64, data []byte) { values[index] = binary.LittleEndian.Uint64(data) }); err != nil {
			return nil, err
		}
	}
	for name, values := range map[string][]int64{"cited_by": graph.CitedBy, "raw_reference_counts": graph.RawReferenceCounts} {
		if err := read(name, uint64(len(values)), 8, func(index uint64, data []byte) { values[index] = int64(binary.LittleEndian.Uint64(data)) }); err != nil {
			return nil, err
		}
	}
	for name, values := range map[string][]uint32{"targets": graph.Targets, "incoming": graph.Incoming} {
		if err := read(name, uint64(len(values)), 4, func(index uint64, data []byte) { values[index] = binary.LittleEndian.Uint32(data) }); err != nil {
			return nil, err
		}
	}
	if err := read("years", nodeCount, 4, func(index uint64, data []byte) { graph.Years[index] = int32(binary.LittleEndian.Uint32(data)) }); err != nil {
		return nil, err
	}
	if err := read("audit", nodeCount, 56, func(index uint64, data []byte) {
		graph.Audit[index] = Audit{binary.LittleEndian.Uint64(data[0:8]), binary.LittleEndian.Uint64(data[8:16]), binary.LittleEndian.Uint64(data[16:24]), binary.LittleEndian.Uint64(data[24:32]), binary.LittleEndian.Uint64(data[32:40]), binary.LittleEndian.Uint64(data[40:48]), binary.LittleEndian.Uint64(data[48:56])}
	}); err != nil {
		return nil, err
	}
	if err := parallelGraphTasks(len(tasks), func(index int) error { return tasks[index]() }); err != nil {
		return nil, err
	}
	if err := validateGraph(graph); err != nil {
		return nil, err
	}
	return graph, nil
}

func validateGraph(graph *Graph) error {
	nodes, edges := len(graph.IDs), len(graph.Targets)
	if nodes == 0 || uint64(nodes) > math.MaxUint32 || len(graph.Years) != nodes || len(graph.CitedBy) != nodes || len(graph.RawReferenceCounts) != nodes || len(graph.Audit) != nodes || len(graph.Offsets) != nodes+1 || len(graph.IncomingOffsets) != nodes+1 || len(graph.Incoming) != edges {
		return errors.New("graph array length mismatch")
	}
	for _, offsets := range [][]uint64{graph.Offsets, graph.IncomingOffsets} {
		if offsets[0] != 0 || offsets[nodes] != uint64(edges) {
			return errors.New("graph offsets have incorrect boundaries")
		}
		for node := 0; node < nodes; node++ {
			if offsets[node] > offsets[node+1] {
				return errors.New("graph offsets are not monotonic")
			}
		}
	}
	for _, values := range [][]uint32{graph.Targets, graph.Incoming} {
		for _, value := range values {
			if uint64(value) >= uint64(nodes) {
				return errors.New("graph edge endpoint outside node set")
			}
		}
	}
	return nil
}
