# Block 5 — Energy and carbon footprint

**Run:** `make carbon`

This block has a second agenda: teaching juniors to be sceptical of numbers,
including the ones you are showing them.

---

## Why we estimate instead of measure

You cannot read joules from userspace. Direct measurement needs:

- **Intel RAPL** (`/sys/class/powercap/…`) — requires privileges, and is
  virtualised away or zeroed on most cloud VMs
- **`perf stat -e power/energy-pkg/`** — same restriction
- an **external power meter** — the only truly honest option, and not available
  in a training room

So we use the standard published model, the same shape as the Cloud Carbon
Footprint and Green Software Foundation SCI methodologies:

```
energy (Wh) = CPU-seconds × (TDP / cores) × utilisation × PUE
CO2e (g)    = energy (kWh) × grid carbon intensity (gCO2e/kWh)
```

Every constant is a command-line flag in `tools/carbon.py`. That is deliberate:
the class should leave knowing that **carbon numbers are estimates built on
assumptions**, and that the honest way to present one is with its assumptions
attached.

### The defaults, and why

| Constant | Default | Meaning |
| --- | --- | --- |
| TDP | 205 W | a representative server CPU (EPYC-class) |
| Cores | 64 | → 3.2 W per core |
| PUE | 1.12 | facility power ÷ IT power. Hyperscalers publish 1.1–1.2; enterprise rooms are 1.5–2.0 |
| Utilisation | 1.0 | fraction of a core actually used |
| Embodied | 1.0 | multiplier for manufacturing carbon (try 1.3) |
| Grid | 350 g/kWh | eu-central-1 |

**What is soft:** the absolute values. Anyone quoting these to three significant
figures is fooling themselves.

**What is robust:** the *ranking*. If language A burns 4x the CPU-seconds of
language B on the same task, it burns roughly 4x the energy under any
assumptions you choose. That is why the tool sorts by CPU time and shows the
ratio.

---

## The result

`wordfreq`, 50 million executions/month, eu-central-1:

| Language | CPU/run | Wh/month | CO2e/month | vs best |
| --- | ---: | ---: | ---: | ---: |
| Rust | 388 ms | 19 308 | **6.76 kg** | 1.0x |
| C++ | 712 ms | 35 465 | 12.41 kg | 1.8x |
| Go | 759 ms | 37 802 | 13.23 kg | 2.0x |
| C# | 961 ms | 47 898 | 16.76 kg | 2.5x |
| Python | 1163 ms | 57 938 | 20.28 kg | 3.0x |
| Java | 1660 ms | 82 699 | 28.94 kg | 4.3x |
| TypeScript | 1981 ms | 98 721 | 34.55 kg | 5.1x |

Switching TypeScript → Rust saves ~28 kg CO2e/month = **0.33 tonnes/year**.

Notice what the model is doing: it multiplies *CPU-seconds*, so Java's 1660 ms
(it spawns JIT and GC threads, so CPU time exceeds wall time) costs more than
its 1354 ms wall time suggests, and Go's 759 ms CPU is well above its 577 ms
wall time for the same reason. Wall time and CPU time are different questions.

---

## Now puncture it — in this order

### 1. Put 0.33 tonnes/year in context

One economy passenger, London–New York return, is roughly **0.6–1.0 tonnes**.
So this entire rewrite — at *fifty million executions per month* — saves less
than one person skipping one flight.

**At low volume, language choice is climate noise.** A cron job that runs 100
times a month saves *milligrams*. Do not let anyone justify a rewrite on carbon
grounds at that scale. If they do, they are doing PR, not engineering.

### 2. Changing region beats changing language by ~17x

Run this live — it is the punchline of the block:

```bash
python3 tools/carbon.py --requests 50e6 --region eu-north-1
```

| Region | gCO2e/kWh | TypeScript CO2e/month |
| --- | ---: | ---: |
| ap-south-1 (India) | 630 | 62.2 kg |
| eu-central-1 (Germany) | 350 | 34.6 kg |
| us-east-1 (Virginia) | 350 | 34.6 kg |
| us-west-2 (Oregon) | 95 | 9.4 kg |
| eu-north-1 (Sweden) | 20 | **1.97 kg** |

Moving the *same TypeScript code* from Germany to Sweden cuts emissions ~17x.
Rewriting it in Rust cuts them 5.1x. **The deployment decision beats the
language decision, and it is a config change.**

Ordered list of what actually moves the needle:

1. **Do not run it at all** — cache, batch, deduplicate, delete the feature
2. **Pick a clean region** — 30x spread, zero code change
3. **Fix the algorithm** — O(n²) → O(n log n) beats any language change
4. **Right-size the instance** — idle over-provisioned capacity burns power
5. **Then** consider the language

### 3. The real carbon argument is density, not CPU

The strongest environmental case for an efficient runtime is **not** CPU
seconds. It is that if a service needs 1/10th the memory, it fits on 1/10th the
machines — and you avoid the **embodied carbon** of hardware you never bought.

Manufacturing a server is a large one-off emission, often 20–50% of its lifetime
total for lightly-utilised compute. Not buying it is a bigger win than running
it slightly more efficiently. Try `--embodied 1.3` to see it move.

That is why the **peak-RSS column matters more than it looks**, and it connects
straight back to the bin-packing arithmetic in Block 4.

### 4. A carbon number without its assumptions is a vibe

If a vendor, a blog post, or a colleague gives you a CO2 figure, ask:

- What PUE? What grid intensity, for which region, in which year?
- Does it include embodied carbon, or only operational?
- Is it marginal or average grid intensity? *(Marginal is more honest for
  "should I run this now" decisions and is usually dirtier.)*
- Measured, or modelled from CPU time like ours?

If they cannot answer, the number is decoration.

---

## Where the language-energy research actually stands

The most-cited source is Pereira et al., *"Energy Efficiency across Programming
Languages"* (SLE 2017), which ranked ~27 languages on the Computer Language
Benchmarks Game and found energy tracking execution time closely, with C and
Rust at the efficient end and interpreted languages 30–80x worse.

Use it, but state its limits honestly — juniors should see a lecturer criticise
their own source:

- It benchmarks **CLBG microbenchmarks**, not real applications. Our `wordfreq`
  result — where Python lands next to Java and beats TypeScript — is exactly the kind of case
  those microbenchmarks miss.
- It is from **2017**. Every runtime here has changed substantially since.
- It measures **CPU energy**, largely ignoring memory, storage, network and
  embodied carbon.
- Energy ≈ time × power, and power varies far less across languages than time
  does — so the finding is close to "slower languages use more energy", which
  is true but not deep.

---

## Discussion prompts

1. Your manager reads that Rust is 50x more efficient than Python and asks for
   a rewrite of a job that runs hourly. What do you say? *(Compute the actual
   saving — grams. Then propose the region change and the algorithm fix.)*
2. When *is* the carbon argument real? *(Very high volume, or where efficiency
   lets you shrink the fleet — the embodied-carbon effect.)*
3. Why might a "slower" language be greener in practice? *(If it lets you ship
   the caching layer this quarter instead of next.)*
4. Is a serverless function greener than a always-on VM? *(Usually yes at low
   duty cycle — you are sharing hardware. But cold starts burn CPU too, and
   idle provisioned concurrency is just a VM with extra steps.)*
