// Directly measure the true cost of one object holding two references.
// See objsize.py for the method.
//
// Like Java, .NET gets two numbers because they answer different questions:
//   * managed heap delta = GC.GetTotalMemory, what the object graph costs
//   * RSS delta          = what your Kubernetes memory limit has to allow for
// A .NET object carries an 8-byte header (sync block index) and an 8-byte
// method-table pointer before its fields: 16 B of overhead + 16 B of two
// 64-bit references = 32 B. There are no compressed oops in .NET.
using System;
using System.IO;

public static class ObjSize
{
    const int N = 1_000_000;

    sealed class Node
    {
        public Node? L, R;
    }

    static long RssBytes()
    {
        try
        {
            foreach (string line in File.ReadLines("/proc/self/status"))
            {
                if (line.StartsWith("VmRSS:"))
                {
                    return long.Parse(line.Substring(6).Replace("kB", "").Trim()) * 1024;
                }
            }
        }
        catch (Exception) { }
        return 0;
    }

    public static void Main()
    {
        // Settle the heap before taking a baseline.
        GC.Collect();
        GC.WaitForPendingFinalizers();
        long baseRss = RssBytes();
        long baseHeap = GC.GetTotalMemory(true);

        var keep = new Node[N];
        for (int i = 0; i < N; i++)
        {
            keep[i] = new Node();
        }

        long refs = (long)N * IntPtr.Size; // minus the array of references
        long heapDelta = GC.GetTotalMemory(false) - baseHeap - refs;
        long rssDelta = RssBytes() - baseRss - refs;

        Console.WriteLine($"C#     {"(heap)",-14} {(double)heapDelta / N,6:F1} bytes/node   (heap delta {heapDelta / 1048576.0:F1} MB for 1,000,000 nodes)");
        Console.WriteLine($"       {"(RSS)",-14} {(double)rssDelta / N,6:F1} bytes/node   (RSS  delta {rssDelta / 1048576.0:F1} MB - what the pod pays)");

        if (keep[N - 1] == null && keep[0] != null)
        {
            Console.WriteLine("unreachable");
        }
    }
}
