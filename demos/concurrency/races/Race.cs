// C#: the same race, on a runtime with a specified memory model and a good
// toolbox - and, as in Java and Go, no compile-time protection at all.
//
//   dotnet Race.dll
//
// `counter++` is load / add / store. Two threads interleave and increments are
// lost. `volatile` is not the fix here either: it gives VISIBILITY, not
// ATOMICITY.
//
// The correct tools: lock, Interlocked.Increment, or a concurrent collection.
using System;
using System.Threading;

public static class Race
{
    const int Threads = 8;
    const int Increments = 100_000;

    static long unsafeCounter = 0;
    static volatile int volatileCounter = 0;
    static long guardedCounter = 0;
    static long atomicCounter = 0;
    static readonly object Lock = new object();

    static void SpawnAndJoin(Action body)
    {
        var ts = new Thread[Threads];
        for (int i = 0; i < Threads; i++)
        {
            ts[i] = new Thread(() => body());
            ts[i].Start();
        }
        foreach (var t in ts) t.Join();
    }

    public static void Main()
    {
        long expected = (long)Threads * Increments;

        SpawnAndJoin(() => { for (int i = 0; i < Increments; i++) unsafeCounter++; });     // race
        SpawnAndJoin(() => { for (int i = 0; i < Increments; i++) volatileCounter++; });   // STILL a race
        SpawnAndJoin(() =>
        {
            for (int i = 0; i < Increments; i++)
            {
                lock (Lock) { guardedCounter++; }                                          // correct
            }
        });
        SpawnAndJoin(() => { for (int i = 0; i < Increments; i++) Interlocked.Increment(ref atomicCounter); }); // correct

        Console.WriteLine($"C#     expected      {expected}");
        Console.WriteLine($"C#     racy          {unsafeCounter}   (lost {expected - unsafeCounter})");
        Console.WriteLine($"C#     volatile      {volatileCounter}   (lost {expected - volatileCounter} - volatile is NOT atomic)");
        Console.WriteLine($"C#     lock          {guardedCounter}");
        Console.WriteLine($"C#     Interlocked   {atomicCounter}");
    }
}
