Here is the Robust Research Kernel.

### 1. Title & Abstract

**Title:** Spec-CXL: Hiding Confidential AI Latency with Speculative Decryption over CXL

**Abstract:**
The `ccAI` system provides a compatible solution for confidential computing on legacy AI accelerators (xPUs) by interposing a `PCIe-SC` security module on the PCIe bus. While effective for compatibility, this "bump-in-the-wire" design places cryptographic operations squarely on the critical path of every sensitive memory access, introducing reactive latency that will become a bottleneck for future high-throughput workloads. We propose Spec-CXL, a new architecture that fundamentally changes the security model from reactive interposition to proactive, speculative execution. By leveraging the CXL.mem protocol and the deterministic nature of AI compute graphs, Spec-CXL attaches a security co-processor as a lookaside "Decryption Cache." A software predictor within the trusted VM analyzes the compute graph to pre-fetch and pre-decrypt required memory pages into the cache *before* the xPU requests them. This architectural shift moves decryption latency off the critical path, aiming to overlap security overhead entirely with computation, thereby delivering confidentiality at near-native performance for a wide range of AI workloads.

### 2. Main Problem

The baseline, `ccAI`, solves the crucial problem of retrofitting confidentiality onto diverse, non-confidential xPUs. Its core mechanism, the `PCIe-SC`, is an in-line hardware interposer that inspects, filters, and performs cryptographic operations on PCIe packets in flight. This design choice is its greatest strength and its most significant potential weakness.

The `PCIe-SC`'s data path is inherently **reactive**. When an xPU requests data from host memory via DMA, the following serialized sequence occurs:
1.  The encrypted packet arrives at the `PCIe-SC`.
2.  The `PCIe-SC`'s Packet Filter consults its L1/L2 tables to classify the packet.
3.  The Packet Handler is invoked, performing decryption (e.g., AES-GCM).
4.  The now-plaintext packet is forwarded to the xPU.

Each step adds latency to the memory access time. While `ccAI`'s evaluation shows this overhead is manageable for current LLMs (0.05% - 5.67%), this approach faces a looming **performance threat**. As xPUs become faster and AI workloads (e.g., Graph Neural Networks, large embedding tables for recommendation) become more memory-intensive with finer-grained accesses, this fixed, serial decryption latency will stop being "in the noise" and will become a primary performance bottleneck, violating Amdahl's Law. The `ccAI` architecture fundamentally cannot hide this latency; it can only minimize it through faster hardware.

### 3. Key Insight

Our key insight is that we can transform the security overhead from an unavoidable, serial latency into a parallel, background task that can be hidden by computation. This is enabled by two observations:

1.  **AI Compute Graphs are Largely Deterministic:** For a given model and input tensor shape, the sequence of kernel launches and the memory access patterns they generate are highly predictable. Even in models with data-dependent control flow (e.g., Mixture-of-Experts), the access patterns *within* a selected expert's execution are still predictable.
2.  **CXL enables a new architectural pattern:** The PCIe protocol is fundamentally about message passing between isolated endpoints. The CXL.mem protocol, however, allows a device to be a coherent memory-attached agent. This allows us to move the security module from being a "toll booth" on the PCIe highway to a "lookaside cache" in the shared memory system.

By combining these, we can **speculatively decrypt** memory pages just before they are needed. Instead of waiting for the xPU to request data and then decrypting it, we can predict what it will need next, decrypt it in parallel with the xPU's current computation, and place the plaintext in a secure, high-speed cache ready for immediate use.

### 4. Qualitative Reasoning

`ccAI` operates on a **pull model**: the xPU pulls data, triggering a reactive decryption. Spec-CXL operates on a **push model**: a predictor in the host TVM analyzes the compute graph and proactively pushes the necessary plaintext data into a secure cache that sits next to the xPU.

Consider the architectural difference:
*   **`ccAI` (Interposer):** `TVM <-> PCIe <-> PCIe-SC (Decrypt) <-> PCIe <-> xPU`. The `PCIe-SC` is on the critical path. A miss in the xPU's internal cache results in a full round trip through a cryptographic engine.
*   **Spec-CXL (Lookaside Cache):** The `CXL-SC` (CXL Security Co-processor) is attached to the CXL bus, alongside the xPU and host memory.
    *   **On a cache hit:** `xPU <-> CXL Fabric <-> CXL-SC (plaintext hit)`. The access happens at the speed of the CXL-SC's internal SRAM/DRAM cache.
    *   **On a cache miss:** The system falls back to a reactive path, but the goal is to make this the exception, not the rule.

This is analogous to the evolution from simple, blocking caches to modern CPUs with complex prefetchers and out-of-order execution that hide memory latency. We are applying the same principle to hiding *security* latency. The move from PCIe to CXL is the key enabler, allowing the security module to become a first-class participant in the memory hierarchy rather than a simple bus-level filter.

### 5. Design

Spec-CXL consists of two primary components: the hardware **CXL Security Co-processor (CXL-SC)** and the software **Graph Predictor** running inside the TVM.

**1. CXL Security Co-processor (CXL-SC):**
This is a CXL Type-3 device that attaches to the host root port. It contains:
*   **Decryption Cache:** A region of secure, on-device memory (e.g., SRAM or HBM) that stores plaintext data. This memory is mapped into the xPU's physical address space.
*   **Cryptographic Engine:** High-throughput AES-GCM engines for decryption and encryption.
*   **CXL.mem Controller:** Manages memory requests from the xPU and snoops traffic. It also initiates its own memory reads from the host TVM to fill the Decryption Cache.
*   **Prediction Request FIFO:** A queue where the host-side Graph Predictor enqueues addresses of encrypted pages to be pre-fetched and decrypted.
*   **Write-back Encryption Buffer:** Buffers plaintext writes from the xPU, encrypts them in the background, and writes the ciphertext back to the host TVM memory, managing coherency via the CXL.cache protocol.




**2. Graph Predictor (TVM Software):**
This is a lightweight module within the `ccAI` Adaptor's successor.
*   It hooks into the xPU's runtime API (e.g., CUDA driver calls).
*   Before a kernel is launched, it analyzes the arguments (pointers to input/output tensors, model weights) and the kernel's known behavior to predict the set of memory pages that will be accessed.
*   For simple kernels (e.g., matrix multiplication), this can be a simple base+offset calculation. For more complex ones, it may rely on profiling data or lightweight static analysis.
*   It then enqueues "decryption requests" (physical addresses of encrypted pages) into the CXL-SC's Prediction Request FIFO via an MMIO write.

**Operational Flow (Read Path):**
1.  **Prediction:** Before launching `Kernel_N`, the Graph Predictor analyzes its inputs and predicts it will access pages `[P_i, P_j, P_k]`. It writes these addresses to the CXL-SC's FIFO.
2.  **Pre-Decryption:** While the xPU is busy executing `Kernel_N-1`, the CXL-SC dequeues the requests, issues CXL.mem reads to the host TVM to fetch the encrypted pages, decrypts them, and places the plaintext into its Decryption Cache. It manages the virtual-to-physical mappings for the xPU.
3.  **Execution & Hit:** The xPU begins `Kernel_N` and issues a memory read for a page `P_i`. This request goes over the CXL fabric to the CXL-SC, which serves the plaintext data directly from its cache—a fast cache hit.
4.  **Execution & Miss:** If the predictor was wrong and the xPU requests an un-predicted page `P_z`, the CXL-SC registers a miss. It stalls the xPU's request and executes a reactive, on-demand decryption, similar to `ccAI`. This is the slow path we aim to avoid.

### 6. Potential Quantitative Benefits

*   **Latency Reduction:** We hypothesize that for workloads with high prediction accuracy (>95%), Spec-CXL can reduce the average memory access security overhead by over **80-90%** compared to the reactive `ccAI` baseline. The goal is to move the overhead from the median access to the tail.
*   **Throughput Improvement:** By unblocking the memory pipeline, we expect to improve overall application throughput (e.g., tokens/second in LLMs) by **5-15%** on memory-bound AI tasks, an improvement that will grow as the gap between compute and memory speed widens.
*   **Graceful Degradation:** For workloads with poor predictability, the system performance will gracefully degrade to that of the reactive `ccAI` baseline, rather than failing.

### 7. Experimental / Evaluation Plan

Our evaluation plan is designed to be pragmatic and de-risk the project's core assumptions before committing to a full, complex hardware simulation.

*   **Phase 1: Predictor Feasibility & Upper-Bound Analysis (Prof. Bench's concern)**
    *   **Action:** Develop a Pin-tool or simulator plugin to generate detailed memory access traces for a suite of AI workloads (e.g., BERT, ResNet, GNNs, MoE models).
    *   **Goal:** Analyze these traces to answer: "How predictable are memory accesses?" We will implement several simple prediction algorithms (e.g., next-N-pages, strided) and measure their theoretical hit rate against the traces. This will establish the *upper bound* on performance gain and validate our core insight.

*   **Phase 2: Baseline Reproduction & Bottleneck Identification**
    *   **Action:** Using the `ccAI` authors' evaluation framework (or a faithful reproduction), replicate key results from their paper (e.g., Figure 8).
    *   **Goal:** Confirm our understanding of the baseline. Then, design a microbenchmark with fine-grained, high-frequency DMA requests to intentionally stress the `PCIe-SC`'s reactive path and quantify the exact latency bottleneck we aim to solve.

*   **Phase 3: Cycle-Accurate Cache Simulation (Dr. Sim's concern)**
    *   **Action:** Build a detailed, event-driven simulator of our `CXL-SC`, specifically modeling the Decryption Cache, cryptographic engine latency, and CXL bus contention. This model will be driven by the memory traces from Phase 1.
    *   **Goal:** This provides our primary performance results. We will compare the average memory access latency from this simulation against the baseline latency measured in Phase 2 to quantify our speedup. We will perform sensitivity analysis on cache size, predictor accuracy, and crypto engine throughput.

*   **Phase 4: Full System Simulation (Future Work)**
    *   **Action:** Integrate our `CXL-SC` model into a full-system simulator like gem5 with a modern CXL component model.
    *   **Goal:** This will be the capstone evaluation, allowing us to capture second-order effects like OS interaction, page table walks, and true system-level contention, validating the findings from the trace-driven simulation. This is a long-term goal for a full paper submission.