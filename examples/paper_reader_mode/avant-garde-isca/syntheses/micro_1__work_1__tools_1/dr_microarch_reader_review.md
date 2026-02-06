# Avant-Garde: The Whiteboard Explanation

Alright, let's reverse-engineer this paper. Forget the marketing about "empowering GPUs" – let's look at what's actually happening in the silicon.

## 1. The Whiteboard Explanation: How This Thing Actually Works

**The Problem They're Solving:**

Modern DNNs want to use "scaled numeric formats" like MX9 (Microsoft's Microscaling) where you have:
- A block of 16 elements
- Each element is 8-bit fixed-point
- But there's a *shared* 8-bit scaling factor (exponent) for the whole block
- AND a second-level 1-bit scaling factor shared between pairs of elements

Current GPUs (even H100 with FP8 support) can't handle this natively. So what happens? Look at Figure 3 – you end up with this ugly instruction stream:

```
wmma.mma    {R0-7}, ...     // Tensor Core does the dot product
ld.global R16, [RD2]        // Load scaling factors (CUDA Core)
mul R20, R16, R18           // Multiply scaling factors together
mad R8, R0, R20, R8         // Apply to each result element
mad R9, R1, R20, R9         // ... and again
// ... repeat for every element
```

The Tensor Core computes the raw dot product, then CUDA Cores have to clean up by applying the scaling factors. This is **2.14× more instructions** and **1.38× more register pressure** than plain INT8 (Figure 4).

**The Data Flow in Avant-Garde:**

```
Memory → Load → [Operand Transformer] → Register File → [Avant-Garde Tensor Core] → Writeback
                      ↓                                           ↓
              "Flatten" multi-level                    Dot product + scale
              scaling into single-level                in one operation
```

Here's the key insight: They **pre-process** the operands to "flatten" multi-level formats into single-level ones, then the Tensor Core handles the single scaling factor natively.

For MX9 specifically:
1. You have 16 elements with a shared 8-bit exponent, plus 8 pairs each with a 1-bit sub-exponent
2. The Operand Transformer multiplies each element by its second-level scaling factor
3. Now you have 16 elements with just ONE shared scaling factor
4. The Tensor Core does: `result = dot_product(A_elements, B_elements) × combined_scale_factor`

---

## 2. The 'Aha!' Moment: The Clever Part

The real trick is **where** they put the scaling factor multiplication in the Tensor Core pipeline.

Look at Figure 8. A standard Tensor Core has:
```
Dot Product Unit → Pipeline Register → Adder Tree → Accumulator
```

Avant-Garde adds:
```
Dot Product Unit → Pipeline Register → Adder Tree → [Scaling Unit] → Accumulator
                                                          ↑
                                           8-bit adder combines
                                           scale_A + scale_B
```

**Why this is clever:** The scaling factors are exponents (powers of 2). Adding two exponents is equivalent to multiplying their represented values. So:
- `scale_combined = scale_A + scale_B` (8-bit integer add – trivial)
- `result = dot_product × 2^scale_combined` (one shift/multiply)

This happens **after** the dot product but **before** accumulation, so you don't need separate instructions. The scaling factor arithmetic is essentially "free" because it's just an 8-bit add running in parallel with the dot product.

The Operand Transformer is also clever in how it handles block size mismatches (Figure 5):
- Block size ≤ 16: Coalesce multiple blocks into one 32-element "flattened block" (warp-aligned)
- Block size > 32: Split into multiple flattened blocks, each keeping the original scale factor
- Block size = 32: Direct mapping

This ensures the flattened format always aligns with GPU warp size (32 threads), maximizing SIMT efficiency.

---

## 3. The Skeptic's Check: What They're Glossing Over

**Overhead Claim: "1.4% area, 1.2% power"**

Let's sanity-check this. They say:
- Operand Transformer: 16 FP8/INT8 multipliers + 32 temporary registers
- Tensor Core additions: 8-bit adder + "scaling unit"

**Red flags:**

1. **The "Scaling Unit" is suspiciously vague.** They say it "performs a low-latency multiplication that applies the combined scaling factor to the dot product result." But the dot product result is FP32 (or at least wider than 8-bit). Multiplying an FP32 by a power-of-2 scaling factor isn't just a shift – you need to handle the FP32 exponent field. This is probably a small FP adder (to add the scale to the FP32 exponent), but they don't detail it.

2. **Operand Transformer latency:** They claim "two cycles per warp" for multi-level formats. But look at the description – for N scaling levels, you need 2×(N-1) iterations. For MX9 (2 levels), that's 2 iterations. Each iteration uses 16 multipliers to process 32 elements (so 2 passes). That's 4 cycles minimum, not 2. They claim this is "hidden by interleaved warp execution" – maybe, but only if you have enough warps in flight.

3. **Register file pressure for flattened format:** They claim no increase in register usage, but look at Section 3.1: "For all non-GEMM operations, Avant-Garde maintains operands in registers in the same manner as the baseline GPU... if a block contains four-bit elements, each element is stored in a four-byte register, leaving the remaining 28 bits unused." So for non-GEMM ops, you're still wasting register space. They handwave this as "non-GEMM operations represent only a small portion of the total workload."

4. **Memory layout complexity:** The API requires programmers to "understand the data layout and use the API to fetch elements and scaling factors accordingly." This is pushing complexity to software. The `flatten()` function is called explicitly by the programmer (Figure 9) – this isn't automatic.

5. **Unflattening for training:** Section 3.2 mentions an "unflattening API" that "leverages CUDA cores" and "introduces a long latency." For training workloads where you need to update weights, this could be significant. They dismiss it as "infrequent" but don't quantify it.

**The 45nm synthesis caveat:** They synthesized in FreePDK 45nm and then... extrapolated to H100? The H100 is 4nm. Scaling these numbers is non-trivial. The 1.4% area claim should be taken with a grain of salt.

---

## 4. Discussion Questions

**For the student to consider:**

1. **What happens when the L1 cache misses?** The Operand Transformer sits between operand read and execute. If you're waiting on memory, does the flattening pipeline stall? They don't discuss how the Operand Transformer interacts with the memory hierarchy.

2. **What about formats with block sizes that don't divide evenly into 32?** They show 16, 32, 64, but what about HBFP with block size 576 (mentioned in Section 2.1)? That's 18 flattened blocks with 32 elements each... but 576/32 = 18, so you'd have 18 separate scaling factors to track. How does the Tensor Core handle accumulating results across 18 different scaling factors?

3. **Why only 2-level formats in evaluation?** They claim support for "arbitrary" scaled numeric formats but only evaluate HBFP (1-level), MX9 (2-level), and MXFP8 (1-level). The sensitivity study mentions "up to four scaling levels" but doesn't show accuracy results for these. Is there precision loss with deeper hierarchies?

4. **The accuracy claim is suspicious.** Table 4 shows flattened MX9 has *identical* accuracy to non-flattened MX9 for ViT-Base. But flattening involves multiplying 8-bit fixed-point elements by 1-bit scaling factors – this should introduce some quantization error. Either the 1-bit scaling factors are trivial (just ±1?), or they're cherry-picking models where it doesn't matter.

---

## The Bottom Line

**The actual innovation:** A pipeline stage that pre-multiplies sub-block scaling factors into elements, plus a Tensor Core modification that applies the remaining block-level scaling factor after the dot product but before accumulation.

**The hardware cost they're hiding:** The "scaling unit" is doing FP32 exponent manipulation, not just a shift. The Operand Transformer adds latency that may not always be hidden. The memory layout complexity is pushed to the programmer.

**Is it worth it?** For workloads that are truly bottlenecked on the CUDA Core instructions for scaling (their Figure 4 shows 2.14× instruction overhead), yes. But if you're memory-bound or have other bottlenecks, the 1.74× throughput improvement won't materialize.