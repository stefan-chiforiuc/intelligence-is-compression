// Directly measure the true cost of one object holding two references.
// See objsize.py for the method.
package main

import (
	"bufio"
	"fmt"
	"os"
	"runtime"
	"strconv"
	"strings"
	"unsafe"
)

const N = 1_000_000

type Node struct {
	l, r *Node
}

func rssBytes() int64 {
	f, err := os.Open("/proc/self/status")
	if err != nil {
		return 0
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		if strings.HasPrefix(sc.Text(), "VmRSS:") {
			fields := strings.Fields(sc.Text())
			kb, _ := strconv.ParseInt(fields[1], 10, 64)
			return kb * 1024
		}
	}
	return 0
}

func heapAlloc() int64 {
	var ms runtime.MemStats
	runtime.ReadMemStats(&ms)
	return int64(ms.HeapAlloc)
}

func main() {
	runtime.GC()
	baseRss := rssBytes()
	baseHeap := heapAlloc()

	keep := make([]*Node, N)
	for i := 0; i < N; i++ {
		keep[i] = &Node{}
	}

	// HeapAlloc is exact. RSS can UNDERCOUNT here, because the Go runtime
	// reserves and touches heap arenas up front, so some of these nodes land
	// on pages that were already resident before we took the baseline. Report
	// both, and trust the heap number for "what does one object cost".
	heapDelta := heapAlloc() - baseHeap - int64(N*8) // minus the slice of pointers
	rssDelta := rssBytes() - baseRss - int64(N*8)

	fmt.Printf("Go     %-14s %6.1f bytes/node   (heap delta %.1f MB for %s nodes)\n",
		"(heap)", float64(heapDelta)/N, float64(heapDelta)/1048576, "1,000,000")
	fmt.Printf("       %-14s %6.1f bytes/node   (RSS  delta %.1f MB - undercounts, see comment)\n",
		"(RSS)", float64(rssDelta)/N, float64(rssDelta)/1048576)
	fmt.Printf("       %-14s %6d bytes        (unsafe.Sizeof - the data alone)\n",
		"", unsafe.Sizeof(Node{}))

	// Keep the slice reachable so the GC cannot collect it before we measure.
	if keep[N-1] == nil && keep[0] != nil {
		fmt.Println("unreachable")
	}
}
