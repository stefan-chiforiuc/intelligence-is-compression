#!/usr/bin/env bash
# What does "an object holding two references" actually cost, per language?
# Measured directly: allocate 1,000,000 live nodes and watch memory move.
#
#   bash demos/stack-heap/objsize/run.sh
set -uo pipefail
cd "$(dirname "$0")/../../.."
mkdir -p build/demos
D=demos/stack-heap/objsize

echo "Building ..."
rustc -O $D/objsize.rs -o build/demos/objsize_rs 2>/dev/null
g++ -O2 -std=c++20 $D/objsize.cpp -o build/demos/objsize_cpp
go build -o build/demos/objsize_go $D/objsize.go
dotnet build $D/ObjSize.csproj -c Release -o build/demos/objsize_cs --nologo -v q \
  -p:BaseIntermediateOutputPath="$PWD/build/obj/objsize/" >/dev/null
javac -d build/demos $D/ObjSize.java 2>&1 | grep -v 'Picked up' || true
npx --no-install tsc $D/objsize.ts --outDir build/demos --target es2022 \
  --module nodenext --moduleResolution nodenext --skipLibCheck --types node 2>/dev/null \
  || npx tsc $D/objsize.ts --outDir build/demos --target es2022 \
       --module nodenext --moduleResolution nodenext --skipLibCheck --types node

echo
echo "==============================================================================="
echo "COST OF ONE OBJECT WITH TWO REFERENCE FIELDS  (1,000,000 live instances)"
echo "==============================================================================="
echo
build/demos/objsize_rs
build/demos/objsize_cpp
build/demos/objsize_go
dotnet build/demos/objsize_cs/ObjSize.dll
java -Xms512m -Xmx512m -cp build/demos ObjSize 2>&1 | grep -v 'Picked up'
node build/demos/objsize.js
python3 $D/objsize.py

cat <<'EOF'

===============================================================================
HOW TO READ THIS
===============================================================================

  The DATA is 16 bytes in every language: two pointers. Everything above 16 is
  what the runtime charges you for the privilege of managing that object.

  Rust    ~32 B  16 B of data, rounded up by the allocator's size class.
                 No header at all - Rust knows the type statically, and the
                 lifetime is known at compile time, so nothing extra is stored.

  C++     ~32 B  Same story as Rust: 16 B of data, no header, rounded up to
                 glibc malloc's 16-byte-granular chunk (8 B of bookkeeping
                 hidden in the chunk). A custom pool/arena allocator is how
                 C++ gets this down to a flat 16 - you opt in, it is not free.

  Go      ~16 B  Two pointers, size class 16. Also no per-object header;
                 Go stores type info in the span metadata, not in the object.

  C#      ~32 B  8-byte header (sync block index) + 8-byte method-table
                 pointer + 2 x 8-byte references. Unlike the JVM there are no
                 compressed oops, so the same object is bigger than in Java.

  Java    ~24 B  12-byte header (mark word for locking/hashing + compressed
                 class pointer) + 2 x 4-byte compressed oops, padded to 8.
                 That header is what pays for synchronized, identityHashCode,
                 and generational GC.

  Node    ~80 B  V8 objects carry a hidden-class pointer, a properties backing
                 store and an elements backing store before your fields.

  Python  ~48 B with __slots__, ~95 B without. The difference is the
                 per-instance __dict__. This is the cheapest large win
                 available in Python: add __slots__ to bulk-allocated classes.

  WHY THE HEAP AND RSS NUMBERS DIFFER
  Java and Go report both. Heap delta answers "what does the object cost";
  RSS delta answers "what must my container memory limit allow for". RSS is
  always the bigger, uglier number, and it is the one that gets your pod
  OOM-killed. Size your limits from RSS, never from heap.
EOF
