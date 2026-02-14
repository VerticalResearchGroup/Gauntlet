Based on the prompts we have designed (specifically asking for "System Variables" like , "Workload Models" like Poisson arrivals, and "Cost Functions" based on algorithmic steps), **we are strictly targeting Mechanistic Models, not Roofline Models.**

However, there is a risk. If the `Spec Generator` gets lazy, it might revert to a Roofline (e.g., "Max throughput = Bandwidth / Message Size").

**To prevent this**, we have drafted this `PERF_README.md`. It explicitly defines the difference so the user (and the agents, if you include this in their context) understands that we are modeling the **logic**, not just the **limits**.

Here is the essay/README.

---

# 🧠 Beyond the Roofline: Mechanistic Modeling in Gauntlet

## Introduction

The Quantitative Evaluator in Gauntlet is not designed to tell you the *theoretical maximum* performance of a system. It is designed to tell you the *logical behavior* of the system under load.

To understand the output of this engine, you must understand the distinction between a **Roofline Model** and the **Mechanistic Analytical Models** we generate.

## The Distinction: Speed Limits vs. Traffic Patterns

### 1. The Roofline Model (What we allow, but don't prefer)

A **Roofline Model** calculates the absolute upper bound of performance based on hardware constraints. It assumes perfect scheduling, zero overhead, and infinite parallelism.

* **The Question it answers:** "What is the fastest this hardware could possibly go?"
* **The Metaphor:** The **Speed Limit** on a highway. (e.g., "The road handles 65 MPH").
* **The Formula:** 
* **The Problem:** Most systems never hit the roofline because of *software overhead*, *contention*, and *algorithmic complexity*.

### 2. The Mechanistic Model (Our Standard)

A **Mechanistic Model** (or First-Principles Analytical Model) constructs a cost function based on the logical steps the algorithm must perform. It accounts for how the system scales with input size (), contention (), and protocol overhead.

* **The Question it answers:** "How does the algorithm behave as I add more nodes/data?"
* **The Metaphor:** The **Traffic Simulation**. (e.g., "Even if the limit is 65 MPH, the merge lane causes a bottleneck that slows traffic to 30 MPH when cars > 100").
* **The Formula:** 

## Why We Use Mechanistic Models

We use Mechanistic Models to expose **"The Magic Gap."**

In many research papers, authors present a mechanism that *should* have high overhead (e.g., complex locking, multi-round consensus), yet their graphs show performance close to the hardware Roofline.

* If we used a Roofline Model, we would just say, "Yes, the hardware allows this."
* By using a Mechanistic Model, we can say: **"Mathematically, your locking protocol implies a latency of , but your graph shows . This is a Magic Gap. Either you have a hidden optimization, or the data is wrong."**

## How to Interpret the Plots

* **Blue Line (Baseline):** The standard approach.
* **Green Line (Proposed - Mechanistic):** The predicted performance of the new technique derived from its *logical description*.
* **Red X (Claimed Data):** The data points extracted from the paper.

**The Verdict:**

* **X sits on Green:** The paper is consistent. The mechanism explains the results.
* **X is significantly better than Green:** The paper is claiming performance that its own described mechanism cannot support. **(The Magic Gap)**.
* **X is worse than Green:** The implementation has unstated inefficiencies.

---

## ⚠️ A Note on Fidelity

These are **Analytical** models, not **Discrete Event Simulations (DES)**.

* We use Python equations (vectorized math) to approximate behavior.
* We do not simulate individual packet arrivals or CPU clock cycles.
* We focus on **Asymptotic Behavior** and **Trade-offs** (e.g., "Does latency explode when ?").