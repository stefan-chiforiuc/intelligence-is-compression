// BONUS - Go `:=`: short variable declaration, still STATIC.
//
// Run:  go build -o /dev/null demos/typing/var_inference.go
//
// Expected:
//   cannot use 42 (untyped int constant) as string value in assignment
//
// `:=` infers a type once, from the right-hand side, at the declaration.
// After that the variable is exactly as fixed as `var name string = "Ada"` -
// Go just let you skip writing `string` twice.
package main

import "fmt"

func main() {
	name := "Ada" // inferred once: string
	fmt.Printf("%T\n", name)

	// >>> This is the line that will not compile. <<<
	name = 42
	fmt.Println(name)
}
