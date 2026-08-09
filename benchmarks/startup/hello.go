// Cold-start workload: do essentially nothing, as fast as possible.
//
// Everything this program measures happens BEFORE your business logic runs:
// process spawn, dynamic linking, runtime/VM initialisation, bytecode loading.
// That fixed cost is what you pay on every single serverless invocation and on
// every pod restart during a rolling deploy.
package main

import (
	"fmt"
	"os"
	"strconv"
)

func main() {
	n := 1
	if len(os.Args) > 1 {
		if v, err := strconv.Atoi(os.Args[1]); err == nil {
			n = v
		}
	}
	fmt.Printf("ready %d\n", n*2)
}
