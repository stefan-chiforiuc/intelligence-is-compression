// CPU-bound workload: count points inside the Mandelbrot set.
//
// Pure scalar float math in a tight nested loop. No allocation, no I/O.
// This isolates *raw interpreter/compiler quality* from everything else.
package main

import (
	"fmt"
	"os"
	"strconv"
)

const maxIter = 50

func mandelbrot(n int) int {
	inside := 0
	fn := float64(n)
	for y := 0; y < n; y++ {
		ci := 2.0*float64(y)/fn - 1.0
		for x := 0; x < n; x++ {
			cr := 2.0*float64(x)/fn - 1.5
			zr, zi := 0.0, 0.0
			i := 0
			for i < maxIter && zr*zr+zi*zi <= 4.0 {
				t := zr*zr - zi*zi + cr
				zi = 2.0*zr*zi + ci
				zr = t
				i++
			}
			if i == maxIter {
				inside++
			}
		}
	}
	return inside
}

func main() {
	n := 1000
	if len(os.Args) > 1 {
		v, err := strconv.Atoi(os.Args[1])
		if err != nil {
			fmt.Fprintln(os.Stderr, "bad size:", err)
			os.Exit(1)
		}
		n = v
	}
	fmt.Println(mandelbrot(n))
}
