import argparse
import hashlib
import json
import pathlib
import platform
import statistics
import subprocess
from datetime import datetime, timezone


def reference_checksum():
    nodes = 120000
    outgoing = [set() for _ in range(nodes)]
    incoming = [set() for _ in range(nodes)]
    for source in range(nodes):
        boundary = source // 4000 * 4000
        if not boundary:
            continue
        state = source + 1
        for slot in range(16):
            state = (state * 6364136223846793005 + 1442695040888963407) & ((1 << 64) - 1)
            target = source % 1024 if slot == 0 else (state >> 32) % boundary
            outgoing[source].add(target)
            incoming[target].add(source)
    checksum = 0
    for job in range(24000):
        focal = 4000 + job * 7919 % (nodes - 4000)
        minimum = (focal // 4000 + 1) * 4000
        maximum = (focal // 4000 + 6) * 4000
        direct = {target for target in incoming[focal] if minimum <= target < maximum}
        related = set().union(*(incoming[reference] for reference in outgoing[focal]))
        related = {target for target in related if minimum <= target < maximum}
        count_nf = len(direct - related)
        count_nb = len(direct & related)
        count_nr = len(related - direct)
        checksum += (focal + 1) * (count_nf + 1009 * count_nb + 1000003 * count_nr)
    return checksum * 100


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 3:
        parser.error("at least three repeats required")
    args.output.mkdir(parents=True, exist_ok=True)
    directory = pathlib.Path(__file__).resolve().parent
    versions = {"go": subprocess.check_output(["go", "version"], text=True).strip(), "rust": subprocess.check_output(["rustc", "--version"], text=True).strip()}
    subprocess.run(["go", "build", "-o", str(args.output / "graph-go"), str(directory / "graph_read.go")], check=True)
    subprocess.run(["rustc", "-O", "-o", str(args.output / "graph-rust"), str(directory / "graph_read.rs")], check=True)
    expected = reference_checksum()
    runs = []
    for repeat in range(args.repeats):
        languages = ("go", "rust") if repeat % 2 == 0 else ("rust", "go")
        for workers in (1, 8, 40):
            for language in languages:
                completed = subprocess.run(["/usr/bin/time", "-f", "%M", str(args.output / f"graph-{language}"), str(workers)], text=True, capture_output=True, check=True)
                result = json.loads(completed.stdout)
                result.update(repeat=repeat, peak_rss_kib=int(completed.stderr.strip()))
                if result["checksum"] != expected:
                    raise RuntimeError(f"checksum mismatch: {result}")
                runs.append(result)
                print(json.dumps(result), flush=True)
    summary = []
    for language in ("go", "rust"):
        for workers in (1, 8, 40):
            matches = [row for row in runs if row["language"] == language and row["workers"] == workers]
            summary.append({"language": language, "workers": workers, "median_compute_seconds": statistics.median(row["compute_seconds"] for row in matches), "max_peak_rss_kib": max(row["peak_rss_kib"] for row in matches)})
    result = {"generated_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(), "versions": versions, "source_sha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in ("graph_read.go", "graph_read.rs", "run_engine.py")}, "independent_python_checksum": expected, "runs": runs, "summary": summary}
    (args.output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
