// "Warm-up" curve for Go - the control group.
//
// Go is compiled ahead of time to a native binary. There is no interpreter,
// no tiered compiler, no on-stack replacement. Batch 0 runs exactly the same
// machine code as batch 24, so this line should be FLAT.
//
// That flatness is the entire value proposition of AOT: predictable
// performance from the first request, which is what you want for a serverless
// function or a CLI tool that runs for 200 ms and exits.
//
// Output: one "batch,milliseconds" line per batch, for run.py to chart.
package main

import (
	"fmt"
	"math"
	"time"
)

const (
	batches       = 60
	callsPerBatch = 200
	size          = 16
	maxIter       = 50
)

//go:noinline
func kernel(n int) int64 {
	var inside int64
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
	var sink int64
	for b := 0; b < batches; b++ {
		t0 := time.Now()
		for c := 0; c < callsPerBatch; c++ {
			sink += kernel(size)
		}
		ms := float64(time.Since(t0).Nanoseconds()) / 1e6
		fmt.Printf("%d,%.3f\n", b, ms)
	}
	if sink == math.MinInt64 {
		fmt.Println("unreachable")
	}
}
