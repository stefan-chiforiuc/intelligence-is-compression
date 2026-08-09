// Parallel Mandelbrot in Go: goroutines + WaitGroup.
//
//	go run parallel_mandelbrot.go <n> <workers>
//
// Goroutines are not OS threads. They are green threads with 2 KB growable
// stacks, multiplexed by the runtime onto GOMAXPROCS OS threads. Creating one
// costs roughly a function call, so "one goroutine per unit of work" is normal
// Go style rather than a performance crime.
//
// Note what is NOT here: no thread pool, no executor, no async/await colouring,
// no callback. Go's bet is that concurrency should be so cheap and so plain
// that you reach for it without ceremony. That bet is most of why Go took over
// networked services.
package main

import (
	"fmt"
	"os"
	"runtime"
	"strconv"
	"sync"
	"time"
)

const maxIter = 50

func band(n, y0, y1 int) int64 {
	var inside int64
	fn := float64(n)
	for y := y0; y < y1; y++ {
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
	n, workers := 1000, 1
	if len(os.Args) > 1 {
		n, _ = strconv.Atoi(os.Args[1])
	}
	if len(os.Args) > 2 {
		workers, _ = strconv.Atoi(os.Args[2])
	}
	runtime.GOMAXPROCS(workers)

	step := (n + workers - 1) / workers
	results := make([]int64, workers)

	start := time.Now()
	var wg sync.WaitGroup
	for w := 0; w < workers; w++ {
		y0 := w * step
		y1 := y0 + step
		if y1 > n {
			y1 = n
		}
		if y0 >= n {
			continue
		}
		wg.Add(1)
		// Each goroutine writes to its OWN slot, so there is no shared mutable
		// state and no lock. This is the cheapest correct way to fan out.
		go func(idx, a, b int) {
			defer wg.Done()
			results[idx] = band(n, a, b)
		}(w, y0, y1)
	}
	wg.Wait()
	ms := float64(time.Since(start).Nanoseconds()) / 1e6

	var total int64
	for _, r := range results {
		total += r
	}
	fmt.Printf("inside=%d workers=%d ms=%.1f\n", total, workers, ms)
}
