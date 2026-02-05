# Idea Generation — The Concept

## The problem it solves

The Gauntlet is a critique engine. It takes a proposal and stress-tests it
from N expert perspectives, then synthesises the surviving insights. But a
critique engine is only as useful as the input it receives. If the kernel idea
has a structural flaw — wrong threat model, unprovable claim, untestable
design — the Gauntlet will find it, but only *after* you've already paid for
every review and synthesis in the run.

The Idea Generator exists to make that input defensible before it enters the
Gauntlet.

## The core move: writing against known adversaries

A naive idea generator would just take a seed and a baseline paper and produce
a proposal. The Idea Generator does something different: it is given the full
persona collection — the same experts who will later critique the output — and
asked to *design against them*.

This is not summarisation or expansion. It is adversarial drafting. The
Originator reads each expert's evaluation criteria and makes deliberate
architectural choices to pre-empt the objections each one will raise.

In practice this means the output is *structurally specific* in ways a
unconstrained generator wouldn't be. Compare:

> *Vague:* "We use a speculative mechanism to hide latency."
>
> *Adversarially grounded:* "We use a 64-entry prediction FIFO fed by
> graph-static analysis. On a miss the system falls back to the reactive
> baseline rather than stalling — this is the graceful-degradation property
> Prof. Bench will ask about."

The second version exists because the Originator knew Prof. Bench was coming.

## What the seed is (and isn't)

The seed is the rough insight — the "Aha!" — not a polished argument. It
should be short and directional. The Originator's job is to expand it into a
structurally sound proposal. Over-specifying the seed constrains the
Originator's ability to find the best framing for that insight.

## The human step is load-bearing

The output is a Markdown kernel, not a submission. A human reads it, checks
the technical claims, adds domain knowledge, and converts to PDF before it
enters the Gauntlet. This step is deliberate: the Originator will get the
structure and adversarial framing right, but it will also confabulate
specifics (exact numbers, real system details, valid citations). The human
edits those out or grounds them before the Gauntlet sees them.

## Where it sits

```
Seed + Baseline PDF
        │
        ▼
  Idea Generator          ← produces a defensively-drafted kernel
        │
        ▼
  Human edits             ← grounds technical claims
        │
        ▼
  Gauntlet (main.py)      ← the real critique + synthesis
        │
        ▼
  Synthesis reports
```

The Idea Generator and the Gauntlet share the same persona collection. That
shared adversary set is what makes the two stages a coherent pipeline rather
than two independent scripts.

---

# Idea Generation — How to Run It

## Prerequisites

* `GOOGLE_API_KEY` set in your `.env` file (or shell environment).
  Get one free at [AI Studio](https://aistudio.google.com/app/apikey).
* A project config file (e.g. `config_archresearch.toml`) that contains
  a `seed` entry in addition to the usual `[[personas]]` and `synthesizer`
  keys.  See [Setting up the config](#setting-up-the-config) below.

## The command

```bash
python idea_generator.py [options] <baseline.pdf>
```

| Argument | What it is | Default |
|---|---|---|
| `baseline.pdf` | The prior-art / baseline paper (positional, required) | — |
| `-c` / `--config` | Project config file | `config.toml` in the script directory |
| `-o` / `--output` | Output directory — `idea_kernel.md` is written here | current directory |

### Examples

```bash
# Simplest — uses config.toml, writes idea_kernel.md to CWD
python idea_generator.py baseline_paper.pdf

# Explicit project config, output to a project folder
python idea_generator.py -c config_archresearch.toml -o projects/ccAI baseline_paper.pdf
```

## Setting up the config

The config file is the same one you pass to `main.py` for the Gauntlet, with
one addition: a `seed` key.  The seed is a multiline string — keep it rough
and directional (see [What the seed is](#what-the-seed-is-and-isnt) above).

```toml
synthesizer = "synthesizer_archresearch"

# The seed — rough direction, not a polished argument.
seed = """
We want to extend the baseline paper (ccAI).
The problem is that ccAI uses a reactive FPGA interposer which adds latency
on the critical path.
We want to move to a CXL-based architecture and use "speculative decryption"
based on the fact that AI compute graphs are deterministic.
"""

[[personas]]
name  = "dr_microarch"
short = "micro"

[[personas]]
name  = "prof_workloads"
short = "work"

[[personas]]
name  = "prof_simtools"
short = "tools"
```

If `seed` is missing the script will exit with a clear error telling you
exactly what to add.

## What happens, step by step

1. **Config is loaded.** The persona names and synthesizer name are read.
   The `seed` string is pulled out.
2. **System prompt is assembled.** Each persona's full `.md` file is loaded
   from `personas/` and injected into the "Know Your Adversaries" block.
   The synthesizer's `.md` is added too.  This is the large prompt that
   tells the Originator exactly who is coming.
3. **Baseline PDF is uploaded** to Gemini and processed.
4. **Generation runs.** The seed and the uploaded PDF are sent as the user
   message.  The Originator produces the kernel.
5. **Output is saved** as `idea_kernel.md` in the output directory.

## After you have the kernel

1. Open `idea_kernel.md`.  Read it critically.
2. Ground any confabulated specifics — numbers, citations, system details.
3. Convert to PDF (any method: Word, Pandoc, a browser, whatever).
4. Feed it into the Gauntlet:

```bash
python main.py -c config_archresearch.toml -o runs/ccAI \
    inputs/proposal_call.pdf projects/ccAI/idea_kernel.pdf
```

The `-c` flag is the same config file.  That's what keeps the two stages
talking about the same adversaries.
