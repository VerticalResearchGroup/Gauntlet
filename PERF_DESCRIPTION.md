# The Quantitative Evaluator: Architecture & Design

**Version:** 1.0
**Last Updated:** 2025-02-13
**Purpose:** Convert research paper claims into rigorous, executable Python simulations to expose "magic gaps" where claimed performance exceeds theoretical limits.

---

## Table of Contents

1. [Overview](#overview)
2. [The Constitution: PRIME_DIRECTIVE.md](#the-constitution)
3. [Three-Phase Architecture](#three-phase-architecture)
4. [Phase 1: Specification Loop](#phase-1-specification-loop)
5. [Phase 2: Implementation Loop](#phase-2-implementation-loop)
6. [Phase 3: Interpretation](#phase-3-interpretation)
7. [The Verify-Repair Mechanism](#the-verify-repair-mechanism)
8. [Personas & Agents](#personas--agents)
9. [Output Artifacts](#output-artifacts)
10. [Usage & Configuration](#usage--configuration)
11. [Design Philosophy](#design-philosophy)

---

## Overview

The **Quantitative Evaluator** is a closed-loop AI system that transforms textual claims in research papers into mathematical models and executable code. It operates on the principle that **"Show me the math, then show me the code."**

### The Core Problem

Research papers often make performance claims like:
- *"Our system achieves 10x speedup over baseline"*
- *"We reduce latency by 50% while maintaining throughput"*
- *"Our approach scales linearly to 100 nodes"*

But these claims often lack rigorous mathematical derivations. The Quantitative Evaluator:

1. **Extracts** the mathematical relationships from prose
2. **Implements** those relationships as executable Python models
3. **Validates** that the model matches the paper's reported results
4. **Exposes** discrepancies ("magic gaps") where claims exceed theoretical limits

### Key Innovation: Verify-Repair Loops

Unlike simple one-shot generation, the system uses **autonomous verify-repair loops**:
- Each artifact (spec or code) is **verified** by specialized agents
- If verification fails, a **repair agent** fixes the issues
- The loop continues until approval (max 3 attempts)
- **All intermediate drafts and critiques are saved** for full audit trail

---

## The Constitution

### PRIME_DIRECTIVE.md

Every agent in the system operates under a shared **constitution** that defines immutable scientific standards. This is prepended to every agent's prompt to ensure alignment.

#### The Four Pillars

**1. First-Principles Derivation**
- Models must calculate behavior from logic, not arbitrary values
- ❌ Forbidden: `def cost(): return 500`
- ✅ Required: `def cost(): return num_messages * msg_size / bandwidth`

**2. Calibration (The Truth Overlay)**
- Don't just model theory—check the paper's honesty
- Extract specific data points from figures/tables as "Reference Results"
- Plot these as scatter points over theoretical curves to show gaps

**3. Self-Containment**
- Python script must be standalone (no external CSVs, APIs, or files)
- Generate synthetic data from distributions defined in the spec
- Must run with: `python model.py` (no arguments, no setup)

**4. Baseline vs. Proposed**
- Analysis is meaningless without comparison
- Always model the **Status Quo (Baseline)** and **New Contribution (Proposed)** side-by-side
- Show the delta, not just the final numbers

---

## Three-Phase Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PHASE 1: TEXT → MATH                      │
│                  (Specification Loop)                        │
│                                                              │
│  Input: Research Paper PDF                                   │
│  Output: SPECIFICATION.md (mathematical model)               │
│                                                              │
│  Agents:                                                     │
│    • Prof. Aximo (Generator) → Draft Spec                   │
│    • Dr. Logic (Verifier)    → Critique                     │
│    • Prof. Aximo (Repairer)  → Fixed Spec                   │
│                                                              │
│  Loop: Generate → Verify → Repair (max 3 iterations)        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  PHASE 2: MATH → PYTHON                      │
│                 (Implementation Loop)                        │
│                                                              │
│  Input: SPECIFICATION.md + Paper                            │
│  Output: model.py (executable Python)                        │
│                                                              │
│  Agents:                                                     │
│    • Vector (Implementer)        → Draft Code               │
│    • QA Engineer (Func Verifier) → Syntax/Logic Check       │
│    • PI (Directive Verifier)     → Prime Directive Check    │
│    • Vector (Repairer)           → Fixed Code               │
│                                                              │
│  Loop: Implement → Dual Verify → Repair (max 3 iterations)  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                PHASE 3: PYTHON → INSIGHT                     │
│                     (Interpretation)                         │
│                                                              │
│  Input: SPECIFICATION.md + model.py                          │
│  Output: INTERPRETATION.md (plain-English summary)           │
│                                                              │
│  Agent:                                                      │
│    • Technical Communicator → Human-readable explanation     │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Specification Loop

**Goal:** Reverse-engineer the "physics" of the paper into a mathematical specification.

### Step 1.1: Generation

**Agent:** Prof. Aximo (`spec_generator.md`)

**Task:**
- Read the entire research paper
- Extract all variables, constraints, and formulas
- Identify baseline and proposed systems
- Extract calibration data from tables/figures
- Output: `SPEC_draft_v1.md`

**Example Output Structure:**
```markdown
# Mathematical Specification

## 1. System Variables
| Variable | Description | Default/Range |
|----------|-------------|---------------|
| $N$      | Number of nodes | {1, 2, 4, 8, 16} |
| $B$      | Bandwidth (GB/s) | 10-100 |

## 2. Baseline Model
$$Latency_{baseline} = \frac{DataSize}{Bandwidth} + Overhead$$

## 3. Proposed Model
$$Latency_{proposed} = \frac{DataSize}{Bandwidth \times N} + \frac{Overhead}{N}$$

## 4. Reference Results (from paper)
- Table 1: At N=8, claimed throughput = 5000 TPS
- Figure 3: At N=16, claimed latency = 15ms
```

### Step 1.2: Verification

**Agent:** Dr. Logic (`spec_verifier.md`)

**Task:**
- Check for missing variables or undefined symbols
- Verify formulas match the paper (no hallucinations)
- Ensure calibration data is extracted
- Check constraint definitions are complete

**Output Format:**
```
APPROVED: All variables defined, formulas match paper, calibration data present.
```

OR

```
REVISION NEEDED:
1. Variable $\alpha$ used in Eq. 3 but never defined
2. Missing calibration data from Figure 5
3. Baseline formula assumes zero overhead—unrealistic
```

**Saved to:** `SPEC_CRITIQUE_v1.txt`

### Step 1.3: Repair (if needed)

**Agent:** Prof. Aximo (`spec_repair.md`) - Correction Mode

**Task:**
- Read the critique from Dr. Logic
- Fix identified issues
- Regenerate the specification

**Output:** `SPEC_draft_v2.md`

### Loop Iteration

The verify-repair loop continues for up to **3 attempts**:
- `v1`: Initial generation
- `v2`: After first repair
- `v3`: After second repair

If approved at any point → **SPECIFICATION.md** (final)
If not approved after 3 attempts → Save as **SPECIFICATION.md** anyway with critiques saved

---

## Phase 2: Implementation Loop

**Goal:** Translate the mathematical specification into executable, self-contained Python code.

### Step 2.1: Implementation

**Agent:** Vector (`model_implementer.md`)

**Input:**
- `SPECIFICATION.md` (approved from Phase 1)
- Original paper (for context)

**Task:**
- Translate math equations into Python functions
- Implement baseline and proposed models
- Generate synthetic workload data
- Create visualization (plots comparing baseline vs. proposed vs. claimed)
- Follow Prime Directive requirements

**Output:** `model_draft_v1.py`

**Expected Code Structure:**
```python
import numpy as np
import matplotlib.pyplot as plt

# 1. Configuration (from spec)
class Config:
    num_nodes = 8
    bandwidth_gbps = 100
    # ...

# 2. Baseline model
def baseline_latency(data_size, config):
    return data_size / config.bandwidth + overhead

# 3. Proposed model
def proposed_latency(data_size, num_nodes, config):
    return data_size / (config.bandwidth * num_nodes) + overhead / num_nodes

# 4. Calibration data (from paper)
reported_results = {
    'table1_throughput': 5000,  # TPS at N=8
    'figure3_latency': 15,      # ms at N=16
}

# 5. Simulation & visualization
def main():
    # Generate synthetic workload
    # Run baseline and proposed models
    # Plot theoretical curves
    # Overlay reported results as scatter points
    # Identify "magic gaps"

if __name__ == "__main__":
    main()
```

### Step 2.2: Dual Verification

**Two independent verifiers run in parallel:**

#### 2.2a: Functional Verification

**Agent:** QA Engineer (`functional_verifier.md`)

**Task:**
- Verify all functions from spec are implemented
- Check mathematical formulas match the spec exactly
- Check for syntax errors or bugs
- Verify imports and dependencies are present

**Output:** `MODEL_CRITIQUE_FUNCTIONAL_v1.txt`

**Example:**
```
REVISION NEEDED:
1. Function `baseline_latency()` missing overhead term from Eq. 2
2. Syntax error on line 47: unmatched parenthesis
3. Missing `import matplotlib.pyplot`
```

#### 2.2b: Directive Verification

**Agent:** PI (`directive_verifier.md`)

**Task:**
- Verify first-principles derivation (no hardcoded magic numbers)
- Check calibration points are plotted from paper
- Ensure code is self-contained (no external files)
- Verify baseline vs. proposed comparison exists

**Output:** `MODEL_CRITIQUE_DIRECTIVE_v1.txt`

**Example:**
```
REVISION NEEDED:
1. VIOLATION: Line 23 hardcodes `cost = 500` instead of deriving from bandwidth
2. MISSING: Calibration points from Table 1 not plotted on graphs
3. VIOLATION: Reads external file 'data.csv' (not self-contained)
```

### Step 2.3: Repair (if needed)

**Agent:** Vector (`model_repair.md`) - Debug Mode

**Input:**
- Previous `model_draft_v1.py`
- Combined critiques from QA Engineer + PI
- `SPECIFICATION.md` (for reference)

**Task:**
- Fix all issues identified by both verifiers
- Regenerate corrected Python code

**Output:** `model_draft_v2.py`

### Loop Iteration

The verify-repair loop continues for up to **3 attempts**:
- `v1`: Initial implementation
- `v2`: After first repair
- `v3`: After second repair

Both verifiers must approve → **model.py** (final)
If not approved after 3 attempts → Save as **model.py** anyway with critiques saved

---

## Phase 3: Interpretation

**Goal:** Explain the model's behavior to a human researcher.

**Agent:** Technical Communicator (`model_interpretter.md`)

**Input:**
- `SPECIFICATION.md`
- `model.py`

**Task:**
Generate a plain-English summary covering:

1. **Assumptions:** What does the model assume?
2. **Calculations:** What does it compute?
3. **Findings:** What "magic gaps" were found?
4. **Limitations:** What's missing or simplified?

**Output:** `INTERPRETATION.md`

**Example:**
```markdown
# Model Interpretation

## Assumptions
This model assumes:
- Linear scaling with number of nodes (no coordination overhead)
- Uniform data distribution across nodes
- Zero network contention

## Key Findings

### Gap 1: Benchmark vs. Theory
The paper claims 10x speedup at 16 nodes, but our first-principles
model predicts only 6x due to fixed overhead costs. This suggests
either:
1. The benchmark operates under ideal conditions
2. The paper omitted a key optimization mechanism

### Gap 2: Calibration Mismatch
Table 1 reports 5000 TPS at N=8, but the model predicts 3200 TPS
given the stated bandwidth and latency constraints. This 56% gap
indicates missing information in the paper.

## Limitations
- Model does not account for cache effects
- Assumes infinite memory bandwidth
- No fault tolerance modeled
```

---

## The Verify-Repair Mechanism

### Why Verify-Repair?

**Problem:** Single-shot LLM generation often produces:
- Hallucinated formulas not in the paper
- Incomplete specifications missing key variables
- Code that doesn't match the spec
- Violations of Prime Directive principles

**Solution:** Autonomous self-correction through specialized verifier agents.

### How It Works

```
┌─────────────┐
│  Generator  │ → Draft
└─────────────┘
       ↓
┌─────────────┐
│  Verifier   │ → Critique
└─────────────┘
       ↓
   Approved? ─Yes→ Done ✓
       ↓ No
┌─────────────┐
│  Repairer   │ → Fixed Draft
└─────────────┘
       ↓
   (Loop back to Verifier)
```

### Key Design Choices

**1. Separation of Concerns**
- Generator focuses on extraction/implementation
- Verifier focuses on critique (different mindset)
- Repairer focuses on debugging

**2. Explicit Approval Format**
Verifiers must respond with:
- `APPROVED: <reason>` → Exit loop
- `REVISION NEEDED: <detailed critique>` → Trigger repair

**3. Maximum Attempts**
- Set to 3 to prevent infinite loops
- If max reached, save artifacts + critiques for human review

**4. Full Audit Trail**
Every iteration saves:
- Draft artifacts (`v1`, `v2`, `v3`)
- Critique artifacts (`v1`, `v2`, `v3`)
- This creates reproducible record of reasoning

---

## Personas & Agents

### Phase 1 Agents

| Agent | File | Role | Metaphor |
|-------|------|------|----------|
| **Prof. Aximo** | `spec_generator.md` | Extract math from text | Mathematician reverse-engineering a system |
| **Dr. Logic** | `spec_verifier.md` | Audit spec completeness | Pedantic reviewer checking definitions |
| **Prof. Aximo** | `spec_repair.md` | Fix spec based on critique | Same mathematician fixing mistakes |

### Phase 2 Agents

| Agent | File | Role | Metaphor |
|-------|------|------|----------|
| **Vector** | `model_implementer.md` | Translate math to Python | Software engineer implementing a spec |
| **QA Engineer** | `functional_verifier.md` | Check syntax & logic | Code reviewer checking correctness |
| **PI** | `directive_verifier.md` | Check Prime Directive | Research advisor ensuring rigor |
| **Vector** | `model_repair.md` | Fix code based on critiques | Same engineer debugging |

### Phase 3 Agent

| Agent | File | Role | Metaphor |
|-------|------|------|----------|
| **Tech Communicator** | `model_interpretter.md` | Explain to humans | Science writer translating for public |

### The Constitution

| Document | File | Role |
|----------|------|------|
| **Prime Directive** | `PRIME_DIRECTIVE.md` | Prepended to ALL agents |

---

## Output Artifacts

### Directory Structure

After running `python perf.py paper.pdf -c config_perf.toml -o outputs_perf/`:

```
outputs_perf/
│
├── Phase 1: Specification Artifacts
│   ├── SPEC_draft_v1.md                 # Initial extraction
│   ├── SPEC_CRITIQUE_v1.txt             # First verification
│   ├── SPEC_draft_v2.md                 # After first repair (if needed)
│   ├── SPEC_CRITIQUE_v2.txt             # Second verification (if needed)
│   ├── SPEC_draft_v3.md                 # After second repair (if needed)
│   ├── SPEC_CRITIQUE_v3.txt             # Third verification (if needed)
│   └── SPECIFICATION.md                 # ✅ FINAL (approved or last attempt)
│
├── Phase 2: Implementation Artifacts
│   ├── model_draft_v1.py                # Initial implementation
│   ├── MODEL_CRITIQUE_FUNCTIONAL_v1.txt # QA Engineer critique
│   ├── MODEL_CRITIQUE_DIRECTIVE_v1.txt  # PI critique
│   ├── model_draft_v2.py                # After first repair (if needed)
│   ├── MODEL_CRITIQUE_FUNCTIONAL_v2.txt # QA Engineer critique (if needed)
│   ├── MODEL_CRITIQUE_DIRECTIVE_v2.txt  # PI critique (if needed)
│   ├── model_draft_v3.py                # After second repair (if needed)
│   ├── MODEL_CRITIQUE_FUNCTIONAL_v3.txt # QA Engineer critique (if needed)
│   ├── MODEL_CRITIQUE_DIRECTIVE_v3.txt  # PI critique (if needed)
│   └── model.py                         # ✅ FINAL (approved or last attempt)
│
├── Phase 3: Interpretation Artifacts
│   └── INTERPRETATION.md                # Plain-English summary
│
└── Generated by model.py
    └── evaluation_plot.png              # Visualization (baseline vs proposed vs claimed)
```

### Artifact Versioning Scheme

**Spec Drafts:**
- `SPEC_draft_v1.md` → Initial generation
- `SPEC_draft_v2.md` → After 1st repair
- `SPEC_draft_v3.md` → After 2nd repair
- `SPECIFICATION.md` → Final (approved or max attempts)

**Spec Critiques:**
- `SPEC_CRITIQUE_v1.txt` → Critique of v1
- `SPEC_CRITIQUE_v2.txt` → Critique of v2
- `SPEC_CRITIQUE_v3.txt` → Critique of v3

**Model Drafts:**
- `model_draft_v1.py` → Initial implementation
- `model_draft_v2.py` → After 1st repair
- `model_draft_v3.py` → After 2nd repair
- `model.py` → Final (approved or max attempts)

**Model Critiques (Dual):**
- `MODEL_CRITIQUE_FUNCTIONAL_v1.txt` + `MODEL_CRITIQUE_DIRECTIVE_v1.txt`
- `MODEL_CRITIQUE_FUNCTIONAL_v2.txt` + `MODEL_CRITIQUE_DIRECTIVE_v2.txt`
- `MODEL_CRITIQUE_FUNCTIONAL_v3.txt` + `MODEL_CRITIQUE_DIRECTIVE_v3.txt`

---

## Usage & Configuration

### Basic Usage

```bash
python perf.py paper.pdf -c config_perf.toml -o outputs_perf/
```

### Configuration File

**config_perf.toml:**
```toml
# The Constitution (prepended to all agents)
prime_directive = "personas/quant_eval/PRIME_DIRECTIVE.md"

# Phase 1: Specification Loop
spec_generator = "personas/quant_eval/spec_generator.md"
spec_verifier = "personas/quant_eval/spec_verifier.md"
spec_repair = "personas/quant_eval/spec_repair.md"

# Phase 2: Implementation Loop
model_implementer = "personas/quant_eval/model_implementer.md"
functional_verifier = "personas/quant_eval/functional_verifier.md"
directive_verifier = "personas/quant_eval/directive_verifier.md"
model_repair = "personas/quant_eval/model_repair.md"

# Phase 3: Interpretation
model_interpreter = "personas/quant_eval/model_interpretter.md"
```

### Script Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `paper_pdf` | Research paper to evaluate | Required |
| `-c, --config` | Config file with persona paths | Required |
| `-o, --output` | Output directory | `outputs_perf/` |

### Tunable Constants (in perf.py)

```python
MODEL = "claude-opus-4-5-20251101"  # LLM model
TEMPERATURE = 0.5                   # Balanced creativity
MAX_RETRIES = 5                     # API retry limit
MAX_REPAIR_ATTEMPTS = 3             # Verify-repair iterations
```

---

## Design Philosophy

### 1. Rigor Over Speed

The system prioritizes **correctness** over **efficiency**:
- Uses verify-repair loops (slower but more accurate)
- Saves all intermediate artifacts (disk space for transparency)
- Uses most capable model (Opus 4.5) for all agents

### 2. Transparency Over Opacity

Every decision is recorded:
- Why was a spec rejected? → Read `SPEC_CRITIQUE_v1.txt`
- How did the spec evolve? → Compare `v1` vs `v2` vs `v3`
- What did the verifier catch? → Full critique saved

### 3. Composability Over Monoliths

Each agent is a **self-contained persona**:
- Swap out `spec_generator.md` for a different extraction strategy
- Replace `functional_verifier.md` with stricter checks
- Add new verifiers without modifying pipeline code

### 4. Scientific Integrity Over Hype

The Prime Directive enforces:
- **No magic numbers** (everything derived from first principles)
- **Calibration required** (plot paper's claims to check honesty)
- **Baseline comparison** (show the delta, not just the result)
- **Self-containment** (reproducible without external dependencies)

### 5. AI Augmentation, Not Replacement

The system is designed to **assist** researchers, not replace them:
- Saves artifacts for human review if verification fails
- Provides detailed critiques to explain failures
- Generates interpretations to guide understanding
- Creates executable models for manual experimentation

---

## Future Enhancements

### Potential Improvements

**1. Dynamic Repair Attempts**
- Adjust `MAX_REPAIR_ATTEMPTS` based on complexity
- Simple specs: 1-2 attempts
- Complex specs: 5+ attempts

**2. Confidence Scoring**
- Verifiers assign confidence scores (0-100%)
- Approval threshold: 90%+
- Partial approval: 70-89% (flag for human review)

**3. Multi-Modal Analysis**
- Extract data from graphs/figures directly (OCR + vision models)
- Parse tables more robustly
- Handle equations in LaTeX or images

**4. Incremental Refinement**
- After Phase 3, allow human to provide feedback
- Re-enter Phase 2 with human critique
- Iterate until human approves

**5. Comparative Analysis**
- Feed multiple papers on same topic
- Generate cross-paper comparison
- Identify inconsistencies across literature

**6. Execution Sandbox**
- Automatically run `model.py` in sandboxed environment
- Capture output, plots, and errors
- Feed back into verification loop

---

## Conclusion

The **Quantitative Evaluator** transforms the art of reading research papers into the science of mathematical verification. By combining:

- **Specialized agents** (each with a clear role)
- **Verify-repair loops** (autonomous self-correction)
- **Prime Directive** (shared scientific standards)
- **Full audit trails** (complete transparency)

The system provides **rigorous, reproducible analysis** of research claims. It doesn't replace human judgment—it **augments** it by doing the tedious work of extracting formulas, implementing models, and checking consistency.

**Key Insight:** Most "magic gaps" aren't fraud—they're **omissions**. Papers skip details due to page limits, implicit assumptions, or honest oversights. This system makes those gaps **visible** so researchers can address them.

---

**Document Metadata:**
- **Author:** Gauntlet System Architecture Team
- **Implementation:** `perf.py` (v1.0)
- **Last Tested:** 2025-02-13
- **License:** Internal research tool

---
