use std::io::{self, Read};

fn read_number(data: &[u8], position: &mut usize) -> usize {
    let value = u32::from_le_bytes(data[*position..*position + 4].try_into().unwrap());
    *position += 4;
    value as usize
}

fn main() {
    let mut data = Vec::new();
    io::stdin().read_to_end(&mut data).unwrap();
    let mut position = 0;
    let rows = read_number(&data, &mut position);
    let dimensions: Vec<usize> = (0..4).map(|_| read_number(&data, &mut position)).collect();
    let mut offsets = Vec::new();
    let mut labels = Vec::new();
    for _group in 0..4 {
        let count = read_number(&data, &mut position);
        offsets.push((0..=rows).map(|_| read_number(&data, &mut position)).collect::<Vec<_>>());
        labels.push((0..count).map(|_| read_number(&data, &mut position)).collect::<Vec<_>>());
    }
    let mut result: Vec<i64> = Vec::new();
    for group in [0, 2] {
        let mut left = vec![0_i64; dimensions[group]];
        let mut right = vec![0_i64; dimensions[group + 1]];
        let mut joint = vec![0_i64; left.len() * right.len()];
        for row in 0..rows {
            let left_labels = &labels[group][offsets[group][row]..offsets[group][row + 1]];
            let right_labels = &labels[group + 1][offsets[group + 1][row]..offsets[group + 1][row + 1]];
            for &label in left_labels { left[label] += 1; }
            for &label in right_labels { right[label] += 1; }
            for &left_id in left_labels {
                for &right_id in right_labels { joint[left_id * right.len() + right_id] += 1; }
            }
        }
        result.extend(left);
        result.extend(right);
        result.extend(joint);
    }
    assert_eq!(position, data.len());
    println!("{:?}", result);
}
