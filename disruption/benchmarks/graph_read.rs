use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

const NODES: usize = 120000;
const COHORT: usize = 4000;
const SAMPLES: usize = 2400000;

struct Graph {
    offsets: Vec<usize>,
    targets: Vec<u32>,
}

fn build() -> (Graph, Graph) {
    let mut forward = Graph {
        offsets: vec![0; NODES + 1],
        targets: Vec::new(),
    };
    let mut counts = vec![0usize; NODES];
    for source in 0..NODES {
        let boundary = source / COHORT * COHORT;
        if boundary > 0 {
            let mut state = (source + 1) as u64;
            let mut seen = Vec::new();
            for slot in 0..16 {
                state = state
                    .wrapping_mul(6364136223846793005)
                    .wrapping_add(1442695040888963407);
                let mut target = ((state >> 32) % boundary as u64) as u32;
                if slot == 0 {
                    target = (source % 1024) as u32;
                }
                if !seen.contains(&target) {
                    seen.push(target);
                    forward.targets.push(target);
                    counts[target as usize] += 1;
                }
            }
        }
        forward.offsets[source + 1] = forward.targets.len();
    }
    let mut backward = Graph {
        offsets: vec![0; NODES + 1],
        targets: vec![0; forward.targets.len()],
    };
    for index in 0..NODES {
        backward.offsets[index + 1] = backward.offsets[index] + counts[index];
    }
    let mut cursors = backward.offsets[..NODES].to_vec();
    for source in 0..NODES {
        for &target in &forward.targets[forward.offsets[source]..forward.offsets[source + 1]] {
            backward.targets[cursors[target as usize]] = source as u32;
            cursors[target as usize] += 1;
        }
    }
    (forward, backward)
}

fn main() {
    let workers: usize = std::env::args().nth(1).unwrap().parse().unwrap();
    assert!(workers > 0);
    let build_start = Instant::now();
    let (forward, backward) = build();
    let build_seconds = build_start.elapsed().as_secs_f64();
    let next = AtomicUsize::new(0);
    let start = Instant::now();
    let checksum: u64 = std::thread::scope(|scope| {
        let handles: Vec<_> = (0..workers)
            .map(|_| {
                let forward = &forward;
                let backward = &backward;
                let next = &next;
                scope.spawn(move || {
                    let mut marks = vec![0u32; NODES];
                    let mut masks = vec![0u8; NODES];
                    let mut touched = Vec::with_capacity(NODES);
                    let mut checksum = 0u64;
                    loop {
                        let job = next.fetch_add(1, Ordering::Relaxed);
                        if job >= SAMPLES {
                            break;
                        }
                        let focal = COHORT + ((job % 24000) * 7919) % (NODES - COHORT);
                        let stamp = (job + 1) as u32;
                        touched.clear();
                        let mut visit = |target: u32, bit: u8| {
                            let index = target as usize;
                            let age = (index / COHORT) as i32 - (focal / COHORT) as i32;
                            if !(1..=5).contains(&age) {
                                return;
                            }
                            if marks[index] != stamp {
                                marks[index] = stamp;
                                masks[index] = 0;
                                touched.push(target);
                            }
                            masks[index] |= bit;
                        };
                        for &target in
                            &backward.targets[backward.offsets[focal]..backward.offsets[focal + 1]]
                        {
                            visit(target, 1);
                        }
                        for &reference in
                            &forward.targets[forward.offsets[focal]..forward.offsets[focal + 1]]
                        {
                            let reference = reference as usize;
                            for &target in &backward.targets
                                [backward.offsets[reference]..backward.offsets[reference + 1]]
                            {
                                visit(target, 2);
                            }
                        }
                        let mut counts = [0u64; 4];
                        for &target in &touched {
                            counts[masks[target as usize] as usize] += 1;
                        }
                        checksum += (focal as u64 + 1)
                            * (counts[1] + 1009 * counts[3] + 1000003 * counts[2]);
                    }
                    checksum
                })
            })
            .collect();
        handles
            .into_iter()
            .map(|handle| handle.join().unwrap())
            .sum()
    });
    println!("{{\"language\":\"rust\",\"workers\":{},\"nodes\":{},\"edges\":{},\"focals\":{},\"checksum\":{},\"build_seconds\":{},\"compute_seconds\":{}}}", workers, NODES, forward.targets.len(), SAMPLES, checksum, build_seconds, start.elapsed().as_secs_f64());
}
