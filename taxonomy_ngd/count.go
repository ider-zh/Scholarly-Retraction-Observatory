package main

import (
    "encoding/binary"
    "encoding/json"
    "io"
    "os"
)

func main() {
    data, err := io.ReadAll(os.Stdin)
    if err != nil { panic(err) }
    position := 0
    read := func() uint32 {
        value := binary.LittleEndian.Uint32(data[position:position+4])
        position += 4
        return value
    }
    rows := int(read())
    dimensions := make([]int, 4)
    for index := range dimensions { dimensions[index] = int(read()) }
    offsets := make([][]uint32, 4)
    labels := make([][]uint32, 4)
    for group := 0; group < 4; group++ {
        count := int(read())
        offsets[group] = make([]uint32, rows+1)
        labels[group] = make([]uint32, count)
        for index := range offsets[group] { offsets[group][index] = read() }
        for index := range labels[group] { labels[group][index] = read() }
    }
    result := []int64{}
    for group := 0; group < 4; group += 2 {
        left := make([]int64, dimensions[group])
        right := make([]int64, dimensions[group+1])
        joint := make([]int64, dimensions[group]*dimensions[group+1])
        for row := 0; row < rows; row++ {
            leftLabels := labels[group][offsets[group][row]:offsets[group][row+1]]
            rightLabels := labels[group+1][offsets[group+1][row]:offsets[group+1][row+1]]
            for _, label := range leftLabels { left[label]++ }
            for _, label := range rightLabels { right[label]++ }
            for _, leftID := range leftLabels {
                for _, rightID := range rightLabels { joint[int(leftID)*len(right)+int(rightID)]++ }
            }
        }
        result = append(result, left...)
        result = append(result, right...)
        result = append(result, joint...)
    }
    if position != len(data) { panic("trailing input") }
    if err := json.NewEncoder(os.Stdout).Encode(result); err != nil { panic(err) }
}
