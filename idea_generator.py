"""Idea Generator — Gauntlet front-end.

Reads a baseline PDF and a seed idea (from the project config), assembles a
system prompt from the full persona collection, and asks Gemini to produce a
Markdown research kernel.  The human edits and converts to PDF before feeding
it into main.py as the proposal.

Usage:
    python idea_generator.py baseline.pdf
    python idea_generator.py -c config_archresearch.toml baseline.pdf
    python idea_generator.py -c config_archresearch.toml -o kernel.md baseline.pdf
"""

import argparse
import os
import sys
import time
import tomllib
from pathlib import Path

import google.generativeai as genai
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODEL_NAME = "gemini-2.5-pro"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_persona(name: str) -> str:
    """Read persona prompt from personas/{name}.md, strip markdown header.

    Same logic as main.py — duplicated here so the two scripts stay
    independently runnable without shared-import side-effects.
    """
    path = BASE_DIR / "personas" / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Persona file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("**System Prompt:**"):
        text = text[len("**System Prompt:**"):].strip()
    return text


def upload_to_gemini(path: Path, mime_type: str = "application/pdf"):
    """Upload a file to Gemini and wait for it to finish processing."""
    print(f"  uploading '{path}'…", end="", flush=True)
    file = genai.upload_file(str(path), mime_type=mime_type)
    while file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(1)
        file = genai.get_file(file.name)
    if file.state.name == "FAILED":
        raise ValueError(f"Upload failed: {file.state.name}")
    print("  ready.")
    return file


def build_system_prompt(personas: list[str], synthesizer: str) -> str:
    """Assemble the Originator system prompt from the persona collection.

    Each persona's full .md content is injected as an adversary block so the
    Originator knows exactly what critiques are coming in the Gauntlet.
    """
    sections = []
    for name in personas:
        sections.append(f"--- {name} ---\n{load_persona(name)}\n")
    sections.append(f"--- Synthesizer ({synthesizer}) ---\n{load_persona(synthesizer)}\n")
    adversaries_block = "\n".join(sections)

    return f"""**ROLE:**
You are the **Originator** in a high-stakes "Gauntlet Idea Pipeline."
Your goal is to take a Seed Idea and the attached Baseline Paper, and generate
a **Robust Research Kernel** — a high-quality proposal.

**THE GAUNTLET CONTEXT:**
Your output is NOT the final paper. It will be brutally critiqued by the experts
listed below. You must write your proposal to **anticipate and pre-empt** 
objections they are likely to raise.

**KNOW YOUR ADVERSARIES:**
{adversaries_block}

**YOUR TASK:**
1.  **Analyze the Baseline:** Understand what was done so you can clearly define your "Delta."
2.  **Integrate the Seed Idea:** Use the seed as the core, but expand it into a complete mechanism.
3.  **Defensive Design:** Study each expert's evaluation criteria above.  For each one,
    anticipate the specific objection they will raise and address it directly in your design.

**OUTPUT SECTIONS (Markdown):**
1.  **Title & Abstract**
2.  **Main Problem** — the gap or threat the baseline leaves open.
3.  **Key Insight** — the core "Aha!" that unlocks the solution.
4.  **Qualitative Reasoning** — first-principles argument for why this works.
5.  **Design** — concrete mechanism / architecture / system.  Be specific.
6.  **Potential Quantitative Benefits** — estimated gains (even if rough).
7.  **Experimental / Evaluation Plan** — how you would validate this.

**TONE:**
Rigorous, specific, and ambitious.  Avoid vague marketing fluff."""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gauntlet Idea Generator — produce a research kernel"
    )
    parser.add_argument("baseline_pdf", type=Path,
                        help="baseline / prior-art PDF")
    parser.add_argument("-c", "--config", type=Path, default=BASE_DIR / "config.toml",
                        help="project config file (default: <script dir>/config.toml)")
    parser.add_argument("-o", "--output", type=Path, default=Path("."),
                        help="output directory (default: current directory)")
    args = parser.parse_args()

    # --- Config ---
    with open(args.config, "rb") as f:
        cfg = tomllib.load(f)
    personas    = [p["name"] for p in cfg["personas"]]
    synthesizer = cfg["synthesizer"]
    seed        = cfg.get("seed")
    if not seed:
        sys.exit(f'ERROR: "seed" key missing from {args.config}.\n'
                 'Add a multiline  seed = """…"""  entry to your config.')

    # --- API key ---
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("ERROR: GOOGLE_API_KEY not set. Check your .env file.")
    genai.configure(api_key=api_key)

    # --- Build prompt & upload baseline ---
    print("[setup]   Building system prompt…")
    system_prompt = build_system_prompt(personas, synthesizer)

    print("[upload]  Uploading baseline PDF…")
    pdf_file = upload_to_gemini(args.baseline_pdf)

    # --- Generate ---
    print("[generate] Producing research kernel…")
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system_prompt,
    )
    response = model.generate_content(
        [pdf_file,
         f"Here is the Baseline Paper (PDF).\n\n"
         f"Here is the Seed Idea:\n{seed}\n\n"
         f"Generate the Research Proposal Kernel."],
        generation_config={"temperature": 0.7},
    )

    # --- Save ---
    args.output.mkdir(parents=True, exist_ok=True)
    out_file = args.output / "idea_kernel.md"
    out_file.write_text(response.text, encoding="utf-8")
    print(f"[done]    Kernel saved to: {out_file}")


if __name__ == "__main__":
    main()
