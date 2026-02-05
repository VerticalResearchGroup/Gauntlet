Gauntlet 🥊

A combinatorial multi-agent stress test for high-stakes research proposals.

Gauntlet is a "virtual brainstorming engine" designed to subject research proposals (specifically one's that are a bit cross-cutting across areas) to intense scrutiny from simulated domain experts. It uses the Anthropic Claude Opus 4.5 API to create a divergence-convergence feedback loop.

Instead of a single review, Gauntlet explodes the solution space:

    Divergence: Three distinct expert personas each critique the proposal three times at different temperatures (0.3, 0.7, 1.0), naturally producing conservative, balanced, and divergent takes (Total: 9 distinct critiques).

    Convergence (The Flywheel): A "Synthesizer" agent takes every combination of one critique per expert (3³ = 27) and generates a unique strategic synthesis report for each, helping you find the "Golden Thread" narrative that satisfies all constraints.

Names below are fictitious names to just explain the readme!

🗂 Project Structure
```
Gauntlet/
├── inputs/
│   ├── proposal_call.pdf               # The funding solicitation
│   └── my_proposal.pdf                 # The preliminary draft
├── personas/
│   ├── dr_silas_vane.md                # Chaos Control & Swarm Dynamics Expert
│   ├── prof_amara_kito.md              # Bio-Photonic Interfaces Expert
│   ├── dr_julian_rex.md                # Exascale Cognitive Systems Expert
│   └── synthesizer.md                  # The Strategy Lead System Prompt
├── outputs/
│   ├── RUN_CONFIG.md                   # Run metadata & naming guide
│   ├── expert_reviews/                 # The 9 critiques (3 personas × 3 temps)
│   │   ├── dr_silas_vane/              #   run_1.md  run_2.md  run_3.md
│   │   ├── prof_amara_kito/
│   │   └── dr_julian_rex/
│   └── syntheses/                      # 27 self-contained action-plan folders
│       ├── silas_1__amara_1__julian_1/ #   SYNTHESIS.md + 3 source reviews
│       └── …
├── generate_persona.py                 # Optional: auto-generates persona .md files
├── .env                                # ANTHROPIC_API_KEY
├── config.toml                         # Persona & synthesizer selection
└── main.py                             # Orchestration & permutation logic
```
🧠 The Expert Panel (Simulated)

    Dr. Silas Vane: Expert in Chaos Control & Swarm Dynamics.

        Role: Focuses on emergent behavior, robustness, and mathematical proofs of stability in unpredictable environments.

    Prof. Amara Kito: Expert in Bio-Photonic Interfaces.

        Role: Focuses on the physical layer, energy constraints, biocompatibility, and the "wetware" interface constraints.

    Dr. Julian Rex: Expert in Exascale Cognitive Systems.

        Role: Focuses on massive scalability, foundation model architectures, and distributed system latency.

🚀 The Logic Flow

    Ingestion: The engine reads the proposal_call.pdf and my_proposal.pdf.

    The Gauntlet (Phase 1 — Divergence): Each expert reviews the proposal three times, once at each temperature (0.3, 0.7, 1.0). Low temperature yields precise, conservative critiques; high temperature yields creative, divergent pivots. This produces 9 distinct critique vectors with no manual prompt engineering.

    The Flywheel (Phase 2 — Convergence): The system computes the Cartesian product — one run per expert — giving 3³ = 27 unique input combinations. The Synthesizer agent produces a cohesive Action Plan for each. Every output folder is self-contained: SYNTHESIS.md plus copies of the three source reviews that fed it.

    Idempotent Resume: If you hit a rate limit mid-run, just re-run main.py. It skips any output that already exists and picks up exactly where it left off.

🛠 Usage

    Install dependencies:
    Bash

    pip install anthropic pypdf python-dotenv

    Add your API key to .env:
    Plaintext

    ANTHROPIC_API_KEY=sk-ant-...

    Edit config.toml to select which personas and synthesizer to use.

    Run the Gauntlet, passing your two PDFs as arguments:
    Bash

    python main.py inputs/proposal_call.pdf inputs/my_proposal.pdf

    Use -o to write output to a custom directory:
    Bash

    python main.py -o runs/nsf_2026 inputs/proposal_call.pdf inputs/my_proposal.pdf

🧬 Generator Tool (Optional)

If you don't want to write personas by hand, use the `generate_persona.py` script. It scrapes a researcher's website and uses Google Gemini to "clone" their writing style and expertise into a `.md` persona file in `personas/`.

1.  **Get a Google API Key** (Free tier available): [Google AI Studio](https://aistudio.google.com/app/apikey)
2.  **Add to `.env`**:
    ```bash
    GOOGLE_API_KEY=your_key_here
    ```
3.  **Install requirements**:
    ```bash
    pip install google-generativeai beautifulsoup4 requests
    ```
4.  **Run the generator**:
    ```bash
    python generate_persona.py
    ```
    *Input:* "Geoffrey Hinton"
    *Input:* "Deep Learning"
    *Input:* https://en.wikipedia.org/wiki/University_of_Toronto
    
    *Result:* `personas/geoffrey_hinton.txt` is created automatically.

🎛️ Tuning the Synthesizer
The `personas/synthesizer.md` file acts as the "triage" of this brainstorming. **You should edit this prompt** to match the specific funding opportunity you are targeting. You must also instruct the synthesizer on your specific goals: do you want it to find a cohesive narrative (the "Golden Thread"), conduct a brutal risk assessment, or focus on commercial viability? Tailoring this prompt ensures the final **Action Plan** is optimized for your specific success criteria.

📄 License

MIT