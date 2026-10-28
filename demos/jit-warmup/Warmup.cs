// JIT warm-up curve for .NET, measured from INSIDE one process.
//
// .NET's RyuJIT is tiered, like HotSpot: methods start in a quick, unoptimised
// tier 0, are counted, and get re-JITted at tier 1 once they are hot. On top of
// that, a loop-heavy method is promoted via on-stack replacement (OSR) and
// dynamic PGO feeds real branch data into the tier-1 compile.
//
// Run it twice to make the point:
//   dotnet build/demos/cs/Warmup.dll                          # normal: tiered JIT
//   DOTNET_TieredCompilation=0 dotnet build/demos/cs/Warmup.dll  # straight to full opt
//
// Output: one "batch,milliseconds" line per batch, for run.py to chart.
using System;
using System.Diagnostics;
using System.Globalization;

public static class Warmup
{
    const int Batches = 60;
    const int CallsPerBatch = 200;
    const int Size = 16;
    const int MaxIter = 50;

    // A separate method with a modest loop: we want the *invocation* counter to
    // drive tier promotion, as in the Java version of this demo.
    static long Kernel(int n)
    {
        long inside = 0;
        double fn = n;
        for (int y = 0; y < n; y++)
        {
            double ci = 2.0 * y / fn - 1.0;
            for (int x = 0; x < n; x++)
            {
                double cr = 2.0 * x / fn - 1.5;
                double zr = 0.0, zi = 0.0;
                int i = 0;
                while (i < MaxIter && zr * zr + zi * zi <= 4.0)
                {
                    double t = zr * zr - zi * zi + cr;
                    zi = 2.0 * zr * zi + ci;
                    zr = t;
                    i++;
                }
                if (i == MaxIter) inside++;
            }
        }
        return inside;
    }

    public static void Main()
    {
        long sink = 0;
        for (int b = 0; b < Batches; b++)
        {
            long t0 = Stopwatch.GetTimestamp();
            for (int c = 0; c < CallsPerBatch; c++)
            {
                sink += Kernel(Size);
            }
            double ms = Stopwatch.GetElapsedTime(t0).TotalMilliseconds;
            Console.WriteLine(string.Create(CultureInfo.InvariantCulture, $"{b},{ms:F3}"));
        }
        // Keep `sink` observable so nothing can be optimised away entirely.
        if (sink == long.MinValue) Console.WriteLine("unreachable");
    }
}
