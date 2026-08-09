// Go: a data race that compiles, runs, and quietly gives the wrong answer.
//
//   go run demos/concurrency/races/race.go          # wrong number
//   go run -race demos/concurrency/races/race.go    # the detector names the line
//
// `counter++` is not one operation. It is load, add, store. Two goroutines can
// load the same value, both add one, and both store the same result — one
// increment vanishes. Nothing crashes. The number is just wrong, and it is a
// DIFFERENT wrong number every run, which is what makes these bugs so hard.
//
// Go's answer is cultural rather than structural: "Do not communicate by
// sharing memory; share memory by communicating." Channels, or a mutex, or an
// atomic. The compiler will not stop you doing it wrong — but `-race` will
// catch it at run time if you actually exercise the path.
package main

import (
	"fmt"
	"sync"
	"sync/atomic"
)

const (
	goroutines = 8
	increments = 100_000
)

func main() {
	expected := goroutines * increments

	// --- 1. The race -------------------------------------------------------
	var unsafe int64
	var wg sync.WaitGroup
	for g := 0; g < goroutines; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < increments; i++ {
				unsafe++ // <-- DATA RACE: load, add, store
			}
		}()
	}
	wg.Wait()

	// --- 2. A mutex --------------------------------------------------------
	var mu sync.Mutex
	var guarded int64
	for g := 0; g < goroutines; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < increments; i++ {
				mu.Lock()
				guarded++
				mu.Unlock()
			}
		}()
	}
	wg.Wait()

	// --- 3. An atomic ------------------------------------------------------
	var atomicCounter atomic.Int64
	for g := 0; g < goroutines; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for i := 0; i < increments; i++ {
				atomicCounter.Add(1)
			}
		}()
	}
	wg.Wait()

	fmt.Printf("Go     expected      %d\n", expected)
	fmt.Printf("Go     racy          %d   (lost %d increments)\n", unsafe, int64(expected)-unsafe)
	fmt.Printf("Go     mutex         %d\n", guarded)
	fmt.Printf("Go     atomic        %d\n", atomicCounter.Load())
}
