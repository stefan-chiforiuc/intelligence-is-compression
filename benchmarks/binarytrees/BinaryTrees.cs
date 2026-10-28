// Allocation / GC-bound workload: build and walk many short-lived binary trees.
//
// This is the mirror image of Mandelbrot.cs: almost no arithmetic, but
// millions of tiny object allocations with a mix of short-lived garbage and one
// long-lived tree. The .NET GC is generational, like the JVM's, so the story
// here is similar to Java's.
using System;

public static class BinaryTrees
{
    private const int MinDepth = 4;

    private sealed class Node
    {
        public readonly Node? L, R;

        public Node(Node? l, Node? r)
        {
            L = l;
            R = r;
        }
    }

    static Node Make(int depth)
    {
        if (depth > 0)
        {
            return new Node(Make(depth - 1), Make(depth - 1));
        }
        return new Node(null, null);
    }

    static long Count(Node n)
    {
        if (n.L == null)
        {
            return 1;
        }
        return 1 + Count(n.L) + Count(n.R!);
    }

    public static void Main(string[] args)
    {
        int n = args.Length > 0 ? int.Parse(args[0]) : 16;
        int maxDepth = Math.Max(MinDepth + 2, n);

        int stretchDepth = maxDepth + 1;
        Console.Write($"stretch tree of depth {stretchDepth}\t check: {Count(Make(stretchDepth))}\n");

        Node longLived = Make(maxDepth);

        for (int depth = MinDepth; depth <= maxDepth; depth += 2)
        {
            long iterations = 1L << (maxDepth - depth + MinDepth);
            long check = 0;
            for (long i = 0; i < iterations; i++)
            {
                check += Count(Make(depth));
            }
            Console.Write($"{iterations}\t trees of depth {depth}\t check: {check}\n");
        }

        Console.Write($"long lived tree of depth {maxDepth}\t check: {Count(longLived)}\n");
    }
}
