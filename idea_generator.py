"""Idea Generator — Gauntlet front-end.

Reads a baseline PDF and a seed idea (from the project config), assembles a
system prompt from the full persona collection, and asks either Gemini or
Claude to produce a Markdown research kernel.  Automatically generates both
idea_kernel.md and idea_kernel.pdf (requires markdown-pdf package).

Usage:
    python idea_generator.py baseline.pdf
    python idea_generator.py -c config_archresearch.toml baseline.pdf
    python idea_generator.py -c config_archresearch.toml -o output_dir/ baseline.pdf
    python idea_generator.py --provider claude baseline.pdf
    python idea_generator.py --provider claude --model claude-opus-4-5-20251101 baseline.pdf
"""

import argparse
import base64
import os
import sys
import time
import tomllib
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-pro",
    "claude": "claude-opus-4-5-20251101",
}


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
# Gemini provider
# ---------------------------------------------------------------------------

def generate_with_gemini(
    baseline_pdf: Path,
    system_prompt: str,
    seed: str,
    model_name: str,
) -> str:
    """Generate a research kernel using the Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError:
        sys.exit("ERROR: google-generativeai not installed. "
                 "Install with: pip install google-generativeai")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("ERROR: GOOGLE_API_KEY not set. Check your .env file.")
    genai.configure(api_key=api_key)

    # Upload PDF and wait for processing.
    print(f"[upload]  Uploading baseline PDF to Gemini…", end="", flush=True)
    pdf_file = genai.upload_file(str(baseline_pdf), mime_type="application/pdf")
    while pdf_file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(1)
        pdf_file = genai.get_file(pdf_file.name)
    if pdf_file.state.name == "FAILED":
        raise ValueError(f"Upload failed: {pdf_file.state.name}")
    print("  ready.")

    print(f"[generate] Producing research kernel with {model_name}…")
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
    )
    response = model.generate_content(
        [pdf_file,
         f"Here is the Baseline Paper (PDF).\n\n"
         f"Here is the Seed Idea:\n{seed}\n\n"
         f"Generate the Research Proposal Kernel."],
        generation_config={"temperature": 0.7},
    )
    return response.text


# ---------------------------------------------------------------------------
# Claude provider
# ---------------------------------------------------------------------------

def generate_with_claude(
    baseline_pdf: Path,
    system_prompt: str,
    seed: str,
    model_name: str,
) -> str:
    """Generate a research kernel using the Anthropic API.

    Claude accepts PDFs inline as base64 document content blocks — no separate
    upload / polling step is needed.
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("ERROR: anthropic not installed. "
                 "Install with: pip install anthropic")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY not set. Check your .env file.")
    client = Anthropic(api_key=api_key, max_retries=5)

    print(f"[load]    Reading baseline PDF: {baseline_pdf}")
    if not baseline_pdf.exists():
        raise FileNotFoundError(f"PDF not found: {baseline_pdf}")
    pdf_b64 = base64.standard_b64encode(baseline_pdf.read_bytes()).decode("utf-8")

    print(f"[generate] Producing research kernel with {model_name}…")
    response = client.messages.create(
        model=model_name,
        max_tokens=8192,
        temperature=0.7,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Here is the Baseline Paper (attached above).\n\n"
                        f"Here is the Seed Idea:\n{seed}\n\n"
                        "Generate the Research Proposal Kernel."
                    ),
                },
            ],
        }],
    )
    return response.content[0].text


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
    parser.add_argument("--provider", choices=["gemini", "claude"], default="gemini",
                        help="LLM provider for generation (default: gemini)")
    parser.add_argument("--model", type=str, default=None,
                        help="override the default model name for the chosen provider")
    args = parser.parse_args()

    model_name = args.model or DEFAULT_MODELS[args.provider]

    # --- Config ---
    with open(args.config, "rb") as f:
        cfg = tomllib.load(f)
    personas    = [p["name"] for p in cfg["personas"]]
    synthesizer = cfg["synthesizer"]
    seed        = cfg.get("seed")
    if not seed:
        sys.exit(f'ERROR: "seed" key missing from {args.config}.\n'
                 'Add a multiline  seed = """…"""  entry to your config.')

    # --- Build prompt ---
    print("[setup]   Building system prompt…")
    system_prompt = build_system_prompt(personas, synthesizer)

    # --- Generate ---
    if args.provider == "claude":
        response_text = generate_with_claude(
            args.baseline_pdf, system_prompt, seed, model_name
        )
    else:
        response_text = generate_with_gemini(
            args.baseline_pdf, system_prompt, seed, model_name
        )

    # --- Save ---
    args.output.mkdir(parents=True, exist_ok=True)
    out_file = args.output / "idea_kernel.md"
    out_file.write_text(response_text, encoding="utf-8")
    print(f"[done]    Kernel saved to: {out_file}")
    quit()
    # --- Convert to PDF ---
    pdf_file = args.output / "idea_kernel.pdf"
    try:
        from markdown_pdf import MarkdownPdf, Section
        print(f"[convert] Generating PDF from markdown…")
        pdf = MarkdownPdf()
        pdf.add_section(Section(response_text))
        pdf.save(str(pdf_file))
        print(f"[done]    PDF saved to: {pdf_file}")
    except ImportError:
        print(f"[warning] markdown-pdf not installed. Skipping PDF generation.")
        print(f"          Install with: pip install markdown-pdf")
    except Exception as e:
        print(f"[warning] PDF conversion failed: {e}")
        print(f"          Markdown file is still available at: {out_file}")


if __name__ == "__main__":
    main()
