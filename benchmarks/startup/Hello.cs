// Cold-start workload: do essentially nothing, as fast as possible.
//
// Everything this program measures happens BEFORE your business logic runs:
// process spawn, host resolution (hostfxr), CLR initialisation, assembly
// loading. That fixed cost is what you pay on every single serverless
// invocation and on every pod restart during a rolling deploy.
//
// Mitigations worth knowing about: ReadyToRun (AOT-precompiled IL, cuts JIT
// time) and Native AOT (a real binary, no runtime to boot at all).
using System;

public static class Hello
{
    public static void Main(string[] args)
    {
        int n = args.Length > 0 ? int.Parse(args[0]) : 1;
        Console.WriteLine("ready " + (n * 2));
    }
}
