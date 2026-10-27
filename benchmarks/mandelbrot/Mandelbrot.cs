// CPU-bound workload: count points inside the Mandelbrot set.
//
// Pure scalar float math in a tight nested loop. No allocation, no I/O.
// This isolates *raw interpreter/compiler quality* from everything else.
using System;

public static class Mandelbrot
{
    private const int MaxIter = 50;

    static long Run(int n)
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
                if (i == MaxIter)
                {
                    inside++;
                }
            }
        }
        return inside;
    }

    public static void Main(string[] args)
    {
        int n = args.Length > 0 ? int.Parse(args[0]) : 1000;
        Console.WriteLine(Run(n));
    }
}
