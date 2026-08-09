// The same service simulation as Service.java, for Go's collector.
//
// Go's GC is a concurrent mark-and-sweep tuned for ONE thing above all others:
// short pauses. It deliberately gives up throughput to get them. You should
// see a much tighter p99/p50 ratio than Java's default G1, and a much worse
// CPU-time figure - which is exactly the trade Go chose.
//
// Knobs worth demonstrating:
//   GOGC=100  (default) collect when the heap doubles
//   GOGC=400            collect 4x less often: faster, uses more memory
//   GOGC=off            never collect: fastest and unbounded memory
//   GOMEMLIMIT=256MiB   a soft memory ceiling (Go 1.19+); the right knob for
//                       containers, and the fix for most Go OOM-kills
package main

import (
	"fmt"
	"os"
	"sort"
	"time"
)

const (
	requests          = 200_000
	objectsPerRequest = 200
)

type Payload struct {
	id   int64
	name string
	next *Payload
}

var cache = make([]*Payload, 100_000)

func main() {
	for i := range cache {
		cache[i] = &Payload{id: int64(i), name: fmt.Sprintf("cached-%d", i)}
	}

	latencies := make([]time.Duration, requests)
	var sink int64

	for r := 0; r < requests; r++ {
		t0 := time.Now()

		var head *Payload
		for i := 0; i < objectsPerRequest; i++ {
			head = &Payload{id: int64(r)*31 + int64(i), name: "req", next: head}
		}
		for head != nil {
			sink += head.id
			head = head.next
		}

		if r&1023 == 0 {
			cache[r%len(cache)] = &Payload{id: int64(r), name: "promoted"}
		}

		latencies[r] = time.Since(t0)
	}

	report(latencies)
	if sink < 0 {
		fmt.Fprintln(os.Stderr, "unreachable")
	}
}

func report(l []time.Duration) {
	sorted := make([]time.Duration, len(l))
	copy(sorted, l)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i] < sorted[j] })

	var total time.Duration
	for _, v := range l {
		total += v
	}
	us := func(d time.Duration) float64 { return float64(d.Nanoseconds()) / 1000.0 }

	p50 := sorted[len(sorted)*50/100]
	p99 := sorted[len(sorted)*99/100]

	fmt.Printf("requests    %d\n", len(l))
	fmt.Printf("mean        %8.1f us\n", us(total)/float64(len(l)))
	fmt.Printf("p50         %8.1f us\n", us(p50))
	fmt.Printf("p99         %8.1f us\n", us(p99))
	fmt.Printf("p99.9       %8.1f us\n", us(sorted[len(sorted)*999/1000]))
	fmt.Printf("max         %8.1f us   <-- the worst pause a user saw\n", us(sorted[len(sorted)-1]))
	fmt.Printf("p99/p50     %8.1fx  <-- tail amplification\n", us(p99)/us(p50))
}
