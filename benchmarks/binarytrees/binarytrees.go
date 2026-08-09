// Allocation / GC-bound workload: build and walk many short-lived binary trees.
//
// This is the mirror image of mandelbrot.go: almost no arithmetic, but millions
// of tiny object allocations with a mix of short-lived garbage and one
// long-lived tree. It is the classic way to expose garbage collector behaviour
// and the true per-object memory overhead of a runtime.
package main

import (
	"fmt"
	"os"
	"strconv"
)

const minDepth = 4

type Node struct {
	l, r *Node
}

func make_(depth int) *Node {
	if depth > 0 {
		return &Node{make_(depth - 1), make_(depth - 1)}
	}
	return &Node{nil, nil}
}

func count(n *Node) int {
	if n.l == nil {
		return 1
	}
	return 1 + count(n.l) + count(n.r)
}

func main() {
	n := 16
	if len(os.Args) > 1 {
		v, err := strconv.Atoi(os.Args[1])
		if err != nil {
			fmt.Fprintln(os.Stderr, "bad depth:", err)
			os.Exit(1)
		}
		n = v
	}
	maxDepth := n
	if minDepth+2 > maxDepth {
		maxDepth = minDepth + 2
	}

	stretchDepth := maxDepth + 1
	fmt.Printf("stretch tree of depth %d\t check: %d\n", stretchDepth, count(make_(stretchDepth)))

	longLived := make_(maxDepth)

	for depth := minDepth; depth <= maxDepth; depth += 2 {
		iterations := 1 << (maxDepth - depth + minDepth)
		check := 0
		for i := 0; i < iterations; i++ {
			check += count(make_(depth))
		}
		fmt.Printf("%d\t trees of depth %d\t check: %d\n", iterations, depth, check)
	}

	fmt.Printf("long lived tree of depth %d\t check: %d\n", maxDepth, count(longLived))
}
