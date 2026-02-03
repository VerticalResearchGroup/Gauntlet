"""Gauntlet — flywheel multi-agent review engine.

Phase 1  –  9 expert reviews   (3 personas × 3 temperatures).
Phase 2  – 27 synthesis reports (one per input combination).
Each synthesis folder is self-contained: SYNTHESIS.md + the 3 source reviews.

The script is idempotent: re-running it skips outputs that already exist
and are not error placeholders, so you can resume cleanly after a rate-limit
interruption without redoing successful work.

Output layout
-------------
outputs/
├── RUN_CONFIG.md
├── expert_reviews/
│   ├── dr_silas_vane/
│   │   ├── run_1.md                       # temp 0.3
│   │   ├── run_2.md                       # temp 0.7
│   │   └── run_3.md                       # temp 1.0
│   ├── prof_amara_kito/  …
│   └── dr_julian_rex/                  …
└── syntheses/
    ├── silas_1__amara_1__julian_1/
    │   ├── SYNTHESIS.md
    │   ├── dr_silas_vane_review.md
    │   ├── prof_amara_kito_review.md
    │   └── dr_julian_rex_review.md
    └── …                                  # 27 folders total
"""

import itertools
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv
from pypdf import PdfReader

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODEL = "claude-opus-4-5-20251101"

# Three temperatures give diversity within each persona.
# Low → precise/conservative | Mid → balanced | High → creative/divergent
#TEMPERATURES: list[float] = [0.3, 0.7, 1.0]
TEMPERATURES: list[float] = [0.3]


# Synthesiser uses a moderate temperature; diversity comes from the
# different review combinations fed into it, not from sampling.
SYNTH_TEMP: float = 0.5

# SDK-level retries — handles transient 429s with exponential back-off.
MAX_RETRIES: int = 5

PERSONA_ORDER: list[str] = [
    "dr_silas_vane",
    "prof_amara_kito",
    "dr_julian_rex",
]

# Short labels used in combo directory names.
PERSONA_SHORT: dict[str, str] = {
    "dr_silas_vane":   "silas",
    "prof_amara_kito": "amara",
    "dr_julian_rex":   "julian",
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_pdf_text(path: Path) -> str:
    """Extract full text from a PDF."""
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def load_persona(name: str) -> str:
    """Read persona prompt, strip the markdown header if present."""
    path = BASE_DIR / "personas" / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Persona file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("**System Prompt:**"):
        text = text[len("**System Prompt:**"):].strip()
    return text


def build_context(call_text: str, proposal_text: str) -> str:
    """Labeled concatenation of the two source documents."""
    return (
        "=== SOLICITATION / CALL FOR PROPOSALS ===\n"
        f"{call_text}\n\n"
        "=== MY PROPOSAL ===\n"
        f"{proposal_text}\n"
    )


def combo_label(combo: tuple[int, ...]) -> str:
    """(1, 2, 3) -> 'silas_1__amara_2__julian_3'"""
    return "__".join(f"{PERSONA_SHORT[p]}_{r}" for p, r in zip(PERSONA_ORDER, combo))


def is_valid_output(path: Path) -> bool:
    """True when path exists and does NOT start with an error placeholder."""
    if not path.exists():
        return False
    return not path.read_text(encoding="utf-8").startswith("[ERROR")


# ---------------------------------------------------------------------------
# Phase 1 — expert reviews  (sequential, idempotent)
# ---------------------------------------------------------------------------

def phase1(client: Anthropic, context: str) -> dict[str, dict[int, str]]:
    """Run (or resume) 9 expert reviews.  Returns {persona: {run_idx: text}}."""
    reviews: dict[str, dict[int, str]] = {p: {} for p in PERSONA_ORDER}

    for persona in PERSONA_ORDER:
        prompt = load_persona(persona)
        for i, temp in enumerate(TEMPERATURES, start=1):
            out_dir  = BASE_DIR / "outputs" / "expert_reviews" / persona
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"run_{i}.md"

            # --- resume: skip if already good ---
            if is_valid_output(out_file):
                print(f"  [skip]    {persona:42s} run={i}  (cached)")
                reviews[persona][i] = out_file.read_text(encoding="utf-8")
                continue

            print(f"  [review]  {persona:42s} run={i}  temp={temp}")
            resp = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                temperature=temp,
                system=prompt,
                messages=[{"role": "user", "content": context}],
            )
            text: str = resp.content[0].text
            reviews[persona][i] = text
            out_file.write_text(text, encoding="utf-8")

    print(f"\n  -> phase 1 complete\n")
    return reviews


# ---------------------------------------------------------------------------
# Phase 2 — syntheses  (sequential, idempotent)
# ---------------------------------------------------------------------------

def phase2(
    client: Anthropic,
    call_text: str,
    proposal_text: str,
    reviews: dict[str, dict[int, str]],
) -> None:
    """Run (or resume) all 27 syntheses.  Each folder is self-contained."""
    combos = list(itertools.product(
        range(1, len(TEMPERATURES) + 1), repeat=len(PERSONA_ORDER)
    ))

    for combo in combos:
        label   = combo_label(combo)
        out_dir = BASE_DIR / "outputs" / "syntheses" / label
        out_dir.mkdir(parents=True, exist_ok=True)
        synth_file = out_dir / "SYNTHESIS.md"

        # --- resume: skip if synthesis AND all copied source reviews are valid ---
        source_copies_ok = all(
            is_valid_output(out_dir / f"{p}_review.md")
            for p in PERSONA_ORDER
        )
        if is_valid_output(synth_file) and source_copies_ok:
            print(f"  [skip]    {label}")
            continue

        print(f"  [synth]   {label}")

        system_prompt = load_persona("synthesizer")

        # Tag each review with run index & temperature for the synthesiser.
        review_block = "\n\n".join(
            f"=== REVIEW BY {p.replace('_', ' ').upper()} "
            f"(run {r}, temp {TEMPERATURES[r-1]}) ===\n"
            f"{reviews[p][r]}"
            for p, r in zip(PERSONA_ORDER, combo)
        )

        user_msg = (
            "=== SOLICITATION / CALL FOR PROPOSALS ===\n"
            f"{call_text}\n\n"
            "=== MY PROPOSAL ===\n"
            f"{proposal_text}\n\n"
            "=== EXPERT REVIEWS ===\n"
            f"{review_block}\n"
        )

        resp = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            temperature=SYNTH_TEMP,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        synth_file.write_text(resp.content[0].text, encoding="utf-8")

        # Copy the 3 source reviews that fed this combo into the folder.
        for persona, run_idx in zip(PERSONA_ORDER, combo):
            src = BASE_DIR / "outputs" / "expert_reviews" / persona / f"run_{run_idx}.md"
            shutil.copy2(src, out_dir / f"{persona}_review.md")

    print(f"\n  -> phase 2 complete\n")


# ---------------------------------------------------------------------------
# Run-config writer
# ---------------------------------------------------------------------------

def write_run_config() -> None:
    """Drop a human-readable summary of run parameters into outputs/."""
    lines = [
        "# Gauntlet — Run Configuration",
        "",
        f"- **Model:** `{MODEL}`",
        f"- **Personas:** {', '.join(PERSONA_ORDER)}",
        f"- **Runs per persona:** {len(TEMPERATURES)}",
        f"- **Temperatures:** {TEMPERATURES}",
        f"- **Synthesis temperature:** {SYNTH_TEMP}",
        f"- **Total expert reviews:** {len(PERSONA_ORDER) * len(TEMPERATURES)}",
        f"- **Total syntheses:** {len(TEMPERATURES) ** len(PERSONA_ORDER)}",
        "",
        "## Temperature → run mapping",
        "",
    ]
    for i, t in enumerate(TEMPERATURES, start=1):
        lines.append(f"- `run_{i}` → temperature **{t}**")

    lines += [
        "",
        "## Synthesis folder naming",
        "",
        "`silas_<a>__amara_<b>__julian_<c>` means the synthesiser received",
        "silas `run_<a>`, amara `run_<b>`, julian `run_<c>`.",
        "",
        "Each folder contains `SYNTHESIS.md` **plus** copies of the three",
        "source reviews that produced it — no need to cross-reference.",
        "",
    ]
    (BASE_DIR / "outputs" / "RUN_CONFIG.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY not set. Check your .env file.")

    # max_retries=5 so the SDK backs off & retries on 429s automatically.
    client = Anthropic(api_key=api_key, max_retries=MAX_RETRIES)

    # --- Ingestion ---
    print("[setup]   Loading documents…")
    call_text     = load_pdf_text(BASE_DIR / "inputs" / "proposal_call.pdf")
    proposal_text = load_pdf_text(BASE_DIR / "inputs" / "my_proposal.pdf")
    context       = build_context(call_text, proposal_text)
    print(f"          {len(call_text):,} chars (call) + {len(proposal_text):,} chars (proposal)\n")

    # --- Metadata ---
    (BASE_DIR / "outputs").mkdir(exist_ok=True)
    write_run_config()

    n_reviews   = len(PERSONA_ORDER) * len(TEMPERATURES)
    n_syntheses = len(TEMPERATURES) ** len(PERSONA_ORDER)

    # --- Phase 1: expert reviews (sequential, resumes from cached outputs) ---
    print(f"[phase 1] {n_reviews} expert reviews  (sequential, idempotent)\n")
    reviews = phase1(client, context)

    # --- Phase 2: syntheses (sequential, resumes from cached outputs) ---
    print(f"[phase 2] {n_syntheses} syntheses       (sequential, idempotent)\n")
    phase2(client, call_text, proposal_text, reviews)

    # --- Summary ---
    print("[done]")
    print(f"  expert_reviews/  — {n_reviews} reviews ({len(PERSONA_ORDER)} personas × {len(TEMPERATURES)} runs)")
    print(f"  syntheses/       — {n_syntheses} self-contained folders")
    print(f"  RUN_CONFIG.md    — temperature & naming reference")


if __name__ == "__main__":
    main()
