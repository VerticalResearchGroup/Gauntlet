# Methodology Audit: Avant-Garde Evaluation

*adjusts glasses, pulls up Figure 10*

Let me be direct with you: this paper has some solid evaluation choices, but there are several places where the methodology raises my eyebrows.

---

## 1. The Benchmark Selection: Reasonable but Narrow

**What they used:** A microbenchmark (1M parameters), ViT-Base (86M), ViT-Large (307M), BERT (110M), and GPT-2 Small (124M).

**The Good:** They cover both vision (ViT) and language (BERT, GPT-2) domains. They include multiple model sizes within ViT to show scaling trends. This is standard practice for GPU architecture papers.

**The Suspicious:**
- Where are the **sparse workloads**? Scaled numeric formats are supposed to help with memory-bound scenarios, but all these benchmarks are dense GEMM-heavy transformer models.
- **GPT-2 Small** (124M parameters) is... small. In 2025, we're talking about models with 70B+ parameters. The paper claims to address "large-scale DNN workloads" (Section 1), but their largest model is 307M parameters.
- No **convolutional networks** (ResNet, EfficientNet). These have different memory access patterns and would stress the system differently.
- No **recommendation models** (DLRM) which are actually what runs in datacenters and have irregular embedding lookups.

---

## 2. The Baseline Validity: This Is Where It Gets Interesting

**Their baseline:** NVIDIA H100 with software-based scaled numeric format support.

*Here's the thing:* The H100 **natively supports FP8**. The paper acknowledges this (Section 4). But their comparison for HBFP and MX9 is against a **software implementation** on the H100.

**The Question You Should Ask:** Is this a fair comparison, or are they comparing hardware against software?

Look at Figure 3. They show the instruction stream for software-based MX9 on conventional GPUs. Those `mul` and `mad` instructions are indeed overhead. But this is comparing:
- **Avant-Garde:** Hardware-accelerated scaled format support
- **Baseline:** Software emulation on hardware that wasn't designed for it

This is like comparing a GPU's native FP16 performance against FP16 emulated in software on a CPU. Of course the hardware wins.

**What would be a stronger baseline?**
- Compare against NVIDIA's actual FP8 performance (which they do, but only briefly)
- Compare against other proposed accelerators for scaled formats (DBPS [26], FAST [50], Bucket Getter [29])

---

## 3. The "Gotcha" Graph: Figure 10's Y-Axis

Look at Figure 10 carefully. The throughput improvements range from 1.65× to 1.93×.

**But notice:**
- The microbenchmark shows the **highest** improvement (up to 2.9× for MX9)
- Real DNN workloads show **lower** improvements (1.65× for ViT-Large)

The paper actually acknowledges this in Section 5.1: *"The throughput improvement of Avant-Garde slightly decreases as model size increases."*

**Translation:** The bigger and more realistic your workload, the smaller the gains. This is a classic pattern where microbenchmarks overstate benefits.

---

## 4. The Missing Data: What I Would Have Loved to See

### 4.1 Memory Bandwidth Sensitivity
The paper claims reduced memory overhead, but where's the **memory bandwidth utilization** graph? Scaled formats should reduce data movement. Show me the bytes transferred.

### 4.2 Training Workloads
Table 4 shows accuracy for **inference only**. The paper claims Avant-Garde supports training (Section 3.2 mentions "unflattening" for weight updates), but there's no training throughput evaluation.

**Why does this matter?** Training has different characteristics:
- Backward passes have different memory access patterns
- Gradient accumulation may stress the unflattening path
- Mixed-precision training requires frequent format conversions

### 4.3 Batch Size Sensitivity
All experiments appear to use a single batch size (not specified). How does Avant-Garde perform as batch size varies? Larger batches might amortize the operand transformation overhead differently.

### 4.4 Block Size Sensitivity for Real Workloads
Section 5.6 mentions a sensitivity study on block size, but they say *"we omit a plot for this analysis"* because variations were minimal. 

**Red flag:** When authors omit data because "it's not interesting," I want to see it anyway. What if block size 512 shows degradation in some workloads but not others?

---

## 5. The Accuracy Evaluation: Thin but Acceptable

Table 4 shows accuracy within 0.2% of FP32. This is good, but:

- Only **three models** tested (ViT-Base, BERT, GPT-2)
- Only **MX9** format tested for accuracy (what about HBFP and MXFP8?)
- No **training convergence curves** showing loss over epochs

The paper uses Microsoft's MX emulator for functional simulation. This is reasonable, but it's not the same as running on actual hardware.

---

## 6. The Simulation Infrastructure Question

They use **Accel-Sim** to model an H100. Accel-Sim is a validated simulator, but:

*"As Accel-Sim does not support FP8, we modify the simulator to compute a scaling factor so that FP8 operations execute with the same latency as INT8."* (Section 4)

**Translation:** They're making assumptions about FP8 behavior. This is necessary but introduces uncertainty.

**The power modeling** uses AccelWattch with "scaling" for FP8. Again, reasonable but approximate.

---

## Discussion Question for You

Here's what I want you to think about:

**If we ran Avant-Garde on a real Google Search query trace or a Meta recommendation model instead of these academic benchmarks, would the gains hold?**

Consider:
1. Real datacenter workloads have **irregular memory access patterns** (embedding lookups, sparse attention)
2. They operate under **strict latency SLAs** (99th percentile matters, not average)
3. They often use **model parallelism** across multiple GPUs, which introduces communication overhead that might dominate

The paper optimizes the **compute path**, but in many real scenarios, compute is not the bottleneck—memory bandwidth and communication are.

---

## My Verdict

**Strengths:**
- Clear methodology description
- Multiple numeric formats tested
- Reasonable model diversity within transformers
- Honest about diminishing returns at scale

**Weaknesses:**
- Software baseline inflates gains
- Missing sparse/irregular workloads
- No training evaluation despite claims
- Microbenchmark results prominently featured

**The Bottom Line:** The 74% throughput improvement and 44% execution time reduction are real *for the specific scenario of software-emulated scaled formats on dense transformer inference*. Whether these gains translate to production datacenter workloads remains an open question.

What aspects would you like to dig into further?