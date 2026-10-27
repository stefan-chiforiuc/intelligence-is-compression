// Parallel Mandelbrot in C#: explicit Tasks on the thread pool.
//
//   dotnet ParallelMandelbrot.dll <n> <workers>
//
// Task.Run schedules onto the shared ThreadPool, which starts with as many
// threads as there are cores and injects more slowly (~1-2 per second) if you
// block. For CPU-bound work that is exactly what you want. `Parallel.For`
// would be the idiomatic one-liner; explicit Tasks keep this comparable to the
// other languages' "N workers, one band each" structure.
//
// As in Java, async/await would NOT help here: it is concurrency for I/O, not
// parallelism for CPU. An `async` method with no `await` runs synchronously.
using System;
using System.Diagnostics;
using System.Globalization;
using System.Threading;
using System.Threading.Tasks;

public static class ParallelMandelbrot
{
    const int MaxIter = 50;

    static long Band(int n, int y0, int y1)
    {
        long inside = 0;
        double fn = n;
        for (int y = y0; y < y1; y++)
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

    public static void Main(string[] args)
    {
        int n = args.Length > 0 ? int.Parse(args[0]) : 1000;
        int workers = args.Length > 1 ? int.Parse(args[1]) : 1;

        // Match a fixed-size pool, as the Java version does: exactly `workers`
        // threads ready, so we measure scaling and not thread injection.
        ThreadPool.SetMinThreads(workers, workers);

        int step = (n + workers - 1) / workers;
        var tasks = new Task<long>[workers];
        long t0 = Stopwatch.GetTimestamp();
        for (int w = 0; w < workers; w++)
        {
            int y0 = w * step;
            int y1 = Math.Min(y0 + step, n);
            tasks[w] = y0 >= n ? Task.FromResult(0L) : Task.Run(() => Band(n, y0, y1));
        }
        Task.WaitAll(tasks);
        long total = 0;
        foreach (var t in tasks) total += t.Result;
        double ms = Stopwatch.GetElapsedTime(t0).TotalMilliseconds;

        Console.WriteLine(string.Create(CultureInfo.InvariantCulture,
            $"inside={total} workers={workers} ms={ms:F1}"));
    }
}
