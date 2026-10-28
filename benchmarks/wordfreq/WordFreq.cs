// Mixed real-world workload: read a text file, count words, print the top 10.
//
// This is the closest of the four benchmarks to actual business code: file I/O,
// string slicing, hash map inserts, and a sort. It is dominated by *library and
// runtime quality* (how good is the string type, how good is the hash map)
// rather than by raw loop speed.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

public static class WordFreq
{
    static bool IsWs(char c) => c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f';

    public static void Main(string[] args)
    {
        string path = args.Length > 0 ? args[0] : "data/words.txt";
        string text = Encoding.ASCII.GetString(File.ReadAllBytes(path));

        var counts = new Dictionary<string, int>(1 << 16, StringComparer.Ordinal);
        int i = 0;
        int len = text.Length;
        while (i < len)
        {
            while (i < len && IsWs(text[i]))
            {
                i++;
            }
            int start = i;
            while (i < len && !IsWs(text[i]))
            {
                i++;
            }
            if (i > start)
            {
                string w = text.Substring(start, i - start);
                counts[w] = counts.GetValueOrDefault(w) + 1;
            }
        }

        var pairs = new List<KeyValuePair<string, int>>(counts);
        pairs.Sort((a, b) =>
        {
            int c = b.Value.CompareTo(a.Value);
            return c != 0 ? c : string.CompareOrdinal(a.Key, b.Key);
        });

        Console.WriteLine("distinct: " + counts.Count);
        for (int k = 0; k < 10 && k < pairs.Count; k++)
        {
            Console.WriteLine(pairs[k].Key + " " + pairs[k].Value);
        }
    }
}
