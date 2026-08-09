// Mixed real-world workload: read a text file, count words, print the top 10.
//
// This is the closest of the four benchmarks to actual business code: file I/O,
// string slicing, hash map inserts, and a sort. It is dominated by *library and
// runtime quality* (how good is the string type, how good is the hash map)
// rather than by raw loop speed, which is why the language ranking here looks
// very different from mandelbrot.
package main

import (
	"fmt"
	"os"
	"sort"
	"strings"
)

type pair struct {
	word string
	n    int
}

func main() {
	path := "data/words.txt"
	if len(os.Args) > 1 {
		path = os.Args[1]
	}

	data, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintln(os.Stderr, "read:", err)
		os.Exit(1)
	}

	counts := make(map[string]int, 1<<16)
	for _, w := range strings.Fields(string(data)) {
		counts[w]++
	}

	pairs := make([]pair, 0, len(counts))
	for w, n := range counts {
		pairs = append(pairs, pair{w, n})
	}
	sort.Slice(pairs, func(i, j int) bool {
		if pairs[i].n != pairs[j].n {
			return pairs[i].n > pairs[j].n
		}
		return pairs[i].word < pairs[j].word
	})

	fmt.Printf("distinct: %d\n", len(counts))
	for i := 0; i < 10 && i < len(pairs); i++ {
		fmt.Printf("%s %d\n", pairs[i].word, pairs[i].n)
	}
}
