# Lumina: Decoding the Architecture

Alright, let's reverse-engineer this paper. The authors are targeting real-time 3D Gaussian Splatting (3DGS) on mobile SoCs, and they claim 4.5× speedup over a mobile Volta GPU. Let's look at the wiring diagram and figure out what's actually happening.

---

## 1. The Whiteboard Explanation

Here's how 3DGS rendering actually works, stripped of the jargon:

**The Baseline Pipeline (Figure 1):**
1. **Projection**: Take millions of 3D Gaussian "blobs" and figure out which ones land on which 16×16 pixel tiles on your screen. Filter out anything outside the camera's view.
2. **Sorting**: For each tile, sort all the Gaussians that touch it by depth (front-to-back). This is a radix sort on millions of (tile_id, depth) pairs.
3. **Rasterization**: For each pixel, walk through the sorted Gaussian list and accumulate color using alpha blending (Equation 1). Stop when the accumulated opacity exceeds a threshold.

**The Problem**: Sorting takes ~23% of execution time, and Rasterization takes ~67%. The GPU is terrible at Rasterization because:
- Only ~10% of Gaussians actually contribute to any given pixel (α > 1/255)
- Different pixels terminate at different points in the Gaussian list
- This causes **69% warp divergence** - threads sit idle waiting for their warp-mates to finish

---

## 2. The 'Aha!' Moments

### Trick #1: Sorting Sharing (S²)

**The insight**: If you move your head slightly, the depth order of Gaussians barely changes. So why re-sort every frame?

**The mechanism**:
- Predict where the camera will be N/2 frames in the future using simple velocity extrapolation: `S_k = T_k + v × (N/2)Δt`
- Sort Gaussians at that predicted pose with an **expanded viewport** (extra tiles around the edges)
- Reuse that sorting result for the next N frames (they use N=6)
- Run sorting speculatively in parallel with rasterization of the current frame

**The hidden cost they acknowledge**: You need to expand the sorting viewport by ~4-8 pixels per dimension to catch Gaussians that might drift into view. Figure 23 shows this trades off quality vs. speedup.

### Trick #2: Radiance Caching (RC)

**The insight**: Two rays that hit the same first k significant Gaussians will produce nearly identical pixel colors. This is the clever part.

**The mechanism** (Figure 10):
1. During rasterization, identify the first k=5 Gaussians with α > 1/255
2. Concatenate their IDs to form a cache tag (using bits 3-18 of each ID, so 80 bits total)
3. Look up in a 4-way set-associative cache (4×1024 entries, 52KB)
4. **Cache hit**: Skip the remaining hundreds of Gaussian integrations, use cached RGB
5. **Cache miss**: Complete full rasterization, update cache

**Why this works**: Figure 11 shows that 99% of a pixel's final color comes from just 1.5% of the Gaussians. If you match the first few significant ones, you've essentially matched the ray.

### Trick #3: LuminCore Architecture (Figure 17)

**The insight**: GPUs are fundamentally wrong for this workload because of SIMT. You need to decouple the "is this Gaussian significant?" check from the "accumulate color" computation.

**The mechanism**:
- **Frontend**: 8×8 array of NRUs, each with 4 PEs. Each PE is a 3-stage pipeline that computes α for one Gaussian (Figure 18: 3 multipliers + 3 MACs + comparator)
- **Backend**: Shared across PEs, handles the expensive color integration (exponent, RGB accumulation) only for significant Gaussians
- **Shift Registers**: Buffer significant Gaussians between frontend and backend
- **Sparsity-Aware Remapping**: When cache hits leave PEs idle, reconfigure so all PEs collaborate on a single pixel's Gaussian list

---

## 3. The Skeptic's Check

### Hardware Costs They Mention:
- **LuminCore area**: 1.05 mm² (they claim 0.4% of Xavier SoC's 350 mm²)
- **Feature Buffer**: 176 KB double-buffered SRAM
- **Output Buffer**: 6 KB double-buffered
- **LuminCache**: 52 KB (4-way, 4096 entries)
- **Per-NRU storage**: 160B shift registers + 88B α-record registers

### What I'm Suspicious About:

1. **The cache thrashing problem**: They say LuminCache covers 64×64 pixels shared across 4×4 tiles. But they also say cache-hit pixels are "uniformly distributed" (Figure 15). When you move to the next batch of tiles, you flush the entire cache and reload from DRAM. That's a lot of memory traffic they're hiding behind "double buffering."

2. **The 5-Gaussian tag assumption**: They use bits 3-18 of each Gaussian ID (16 bits × 5 = 80 bits for the tag). But Gaussian IDs can be up to 6 million (Figure 2a). That's 23 bits needed. They're only using 16 bits per ID, so there's aliasing. The cache could return wrong colors for different Gaussians that hash to the same tag.

3. **The fine-tuning requirement**: Section 3.3 admits that RC "occasionally introduces rendering artifacts" and requires retraining with a scale-constrained loss. This means you can't just drop Lumina onto any pretrained 3DGS model - you need to retrain. That's a significant deployment cost they downplay.

4. **The trajectory prediction accuracy**: They use a simple linear velocity model (Equation 2-3). For VR head tracking at 90 FPS, this might work. But for handheld AR or drone footage? The prediction error would blow up the expanded viewport, eating into their speedup.

5. **The 12nm scaling**: They synthesized at 16nm TSMC and scaled to 12nm using DeepScaleTool. This is standard practice, but the power numbers should be taken with a grain of salt.

### The Real Comparison (Section 6.4):
Against GSCore (the only other 3DGS accelerator), Lumina claims 29.6× vs GSCore's 3.2× over GPU baseline. But look carefully - they added GSCore's CCU and GSU units to their baseline, so the comparison is against an already-accelerated system. The raw NRU+GPU baseline (without S² or RC) already beats GSCore at 9.6×. The architectural contribution is the frontend-backend split, not the caching.

---

## 4. Discussion Question

**Ask yourself**: What happens to the Radiance Cache hit rate when the scene contains dynamic objects?

The entire caching scheme assumes that Gaussian IDs are stable across frames. But in a scene with moving objects (think: a person walking through a room), the Gaussians representing that person will have completely different depth orderings frame-to-frame. The cache would thrash, and you'd fall back to full rasterization for every pixel touching the dynamic region.

The paper only evaluates on static scenes (Synthetic-NeRF, Tanks&Temples). For the AR/VR use case they're targeting, this is a significant limitation they don't address.

---

## Summary: The Delta vs. Baseline

| Component | Standard 3DGS | Lumina |
|-----------|---------------|--------|
| Sorting | Every frame | Every 6 frames (speculative) |
| Rasterization | Full Gaussian list per pixel | Early termination via cache lookup |
| Execution model | GPU SIMT (warp divergence) | Frontend filters, backend integrates |
| Memory access | Streaming Gaussians | 52KB radiance cache + double-buffered feature buffer |

The fundamental architectural insight is **decoupling significance testing from color accumulation**. The GPU wastes cycles because all threads must execute the same instruction, even when most Gaussians are insignificant. LuminCore's frontend-backend split lets you filter first, then only pay for the expensive math on the ~10% that matter.