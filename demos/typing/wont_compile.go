// DEMO 4a - Go: static + strong. This file DOES NOT COMPILE, on purpose.
//
// Run:  go build demos/typing/wont_compile.go
//
// Expected:
//   invalid operation: subtotal + shipping (mismatched types string and int)
//
// The bug from demos 1-3 is now impossible to ship. It is not a test failure,
// not a lint warning, not a runtime exception in production at 3am - the
// artifact simply cannot be produced.
package main

import (
	"encoding/json"
	"fmt"
)

type Order struct {
	Subtotal float64 `json:"subtotal"`
	Shipping float64 `json:"shipping"`
}

func main() {
	// Note the second half of the story: Go's JSON decoder also refuses the
	// bad payload at RUN time, because the struct declares what it expects.
	// You get "cannot unmarshal string into Go struct field Order.subtotal
	// of type float64" - loud, immediate, and at the boundary.
	var order Order
	if err := json.Unmarshal([]byte(`{"subtotal": "100", "shipping": 5}`), &order); err != nil {
		fmt.Println("decode error:", err)
	}

	subtotal := "100"
	shipping := 5

	// >>> This is the line that will not compile. <<<
	total := subtotal + shipping
	fmt.Println(total)
}
