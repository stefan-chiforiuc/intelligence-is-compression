// Mixed real-world workload: read a text file, count words, print the top 10.
//
// This is the closest of the four benchmarks to actual business code: file I/O,
// string slicing, hash map inserts, and a sort. It is dominated by *library and
// runtime quality* (how good is the string type, how good is the hash map)
// rather than by raw loop speed, which is why the language ranking here looks
// very different from Mandelbrot.
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class WordFreq {
    public static void main(String[] args) throws IOException {
        String path = args.length > 0 ? args[0] : "data/words.txt";
        String text = new String(Files.readAllBytes(Path.of(path)), StandardCharsets.US_ASCII);

        Map<String, Integer> counts = new HashMap<>(1 << 16);
        int i = 0;
        final int len = text.length();
        while (i < len) {
            while (i < len && Character.isWhitespace(text.charAt(i))) {
                i++;
            }
            int start = i;
            while (i < len && !Character.isWhitespace(text.charAt(i))) {
                i++;
            }
            if (i > start) {
                counts.merge(text.substring(start, i), 1, Integer::sum);
            }
        }

        List<Map.Entry<String, Integer>> pairs = new ArrayList<>(counts.entrySet());
        pairs.sort(Comparator.comparingInt((Map.Entry<String, Integer> e) -> -e.getValue())
                .thenComparing(Map.Entry::getKey));

        System.out.println("distinct: " + counts.size());
        for (int k = 0; k < 10 && k < pairs.size(); k++) {
            System.out.println(pairs.get(k).getKey() + " " + pairs.get(k).getValue());
        }
    }
}
