// Stack vs heap, decided by the COMPILER - and it will tell you what it chose.
//
// This is the single best stack-vs-heap teaching tool in any of our five
// languages, because Go's escape analysis is directly observable:
//
//   go build -gcflags='-m' demos/stack-heap/escape.go
//
// Read the output. Every "escapes to heap" is an allocation you are paying
// for; every "does not escape" is a free one that lives on the stack and
// disappears when the function returns, with zero GC involvement.
//
// Then run the program to see what that difference costs in wall time:
//
//   go run demos/stack-heap/escape.go
package main

import (
	"fmt"
	"time"
)

type Point struct {
	X, Y float64
}

// STAYS ON THE STACK. The value is copied out on return, so nothing outlives
// the frame. Cost: bumping the stack pointer. Effectively free, no GC work.
//
//go:noinline
func makeStackPoint(x, y float64) Point {
	p := Point{X: x, Y: y}
	return p
}

// ESCAPES TO THE HEAP. We return a pointer, so the object must outlive the
// frame that created it. Cost: an allocation now, plus GC work later.
//
//go:noinline
func makeHeapPoint(x, y float64) *Point {
	p := &Point{X: x, Y: y}
	return p
}

// ALSO ESCAPES, and this one surprises people: passing to an interface{}
// (here via fmt) forces a heap allocation because the callee could keep it.
// This is why logging in a hot loop is so much more expensive than it looks.
//
//go:noinline
func leakToInterface(x, y float64) interface{} {
	return Point{X: x, Y: y}
}

const iterations = 20_000_000

func main() {
	fmt.Println("Build with `go build -gcflags='-m'` to see the compiler's decisions.")
	fmt.Println()

	start := time.Now()
	var sum float64
	for i := 0; i < iterations; i++ {
		p := makeStackPoint(float64(i), 1.0)
		sum += p.X
	}
	stack := time.Since(start)

	start = time.Now()
	sum = 0
	for i := 0; i < iterations; i++ {
		p := makeHeapPoint(float64(i), 1.0)
		sum += p.X
	}
	heap := time.Since(start)

	fmt.Printf("stack-allocated : %8.1f ms   (%d iterations)\n",
		float64(stack.Nanoseconds())/1e6, iterations)
	fmt.Printf("heap-allocated  : %8.1f ms   (%d iterations)\n",
		float64(heap.Nanoseconds())/1e6, iterations)
	fmt.Printf("heap is %.1fx slower, and it also created %d objects for the GC to clean up.\n",
		float64(heap)/float64(stack), iterations)
	fmt.Println()
	fmt.Println("Same struct. Same fields. Same arithmetic.")
	fmt.Println("The only difference is whether a pointer escaped the function.")

	_ = sum
}
