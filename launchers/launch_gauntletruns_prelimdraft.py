"""launch_gauntletruns_prelimdraft.py — Batch-run Gauntlet in preliminary draft analysis mode.

For each subdirectory containing baseline.pdf and a draft PDF:
1. Uploads the DRAFT to Gemini and identifies 2 closest topics
2. Maps topics to persona files using sanitize_filename logic
3. Verifies all personas exist in the specified persona directory
4. Generates a custom config.toml for the paper (baseline + selected personas)
5. Runs main.py with baseline.pdf as call and draft.pdf as proposal

Usage:
    python launch_gauntletruns_prelimdraft.py <papers_dir> \\
        --topics ../TOPICS.txt \\
        --baseline-config ../config_prelim_draftanalyst_archgeneric.toml \\
        --persona-dir personas/prelim_draftanalyst
"""

import argparse
import os
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")

MODEL_NAME = "gemini-2.5-pro"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    """Convert a topic string into a clean filename (same logic as persona_factory)."""
    name = name.lower()
    name = re.sub(r'[^a-z0-9]', '_', name)
    name = re.sub(r'_+', '_', name)
    return name.strip('_') + ".md"


def load_topics(filepath: Path) -> list[str]:
    """Read topics from a text file, one per line. Ignore empty lines and comments."""
    if not filepath.exists():
        sys.exit(f"ERROR: Topics file not found: {filepath}")

    text = filepath.read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    return lines


def upload_pdf_to_gemini(pdf_path: Path) -> any:
    """Upload a PDF to Gemini and wait for processing."""
    print(f"          uploading to Gemini...", end="", flush=True)
    file = genai.upload_file(str(pdf_path), mime_type="application/pdf")
    while file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(1)
        file = genai.get_file(file.name)
    if file.state.name == "FAILED":
        raise ValueError(f"Upload failed: {file.state.name}")
    print(" ready.")
    return file


def get_matching_topics(pdf_file, available_topics: list[str]) -> list[str]:
    """Ask Gemini to identify 2 closest topics.

    Returns a list of 2 topic strings from available_topics.
    """
    model = genai.GenerativeModel(model_name=MODEL_NAME)

    topics_formatted = "\n".join(f"{i+1}. {topic}" for i, topic in enumerate(available_topics))

    prompt = f"""This is a computer architecture research paper.

From the following list of topics, identify the 2 CLOSEST topics that directly relate to this paper's core contribution.

AVAILABLE TOPICS:
{topics_formatted}

Reply with ONLY two lines, each containing one topic name EXACTLY as written above:
CLOSEST_1: <topic name>
CLOSEST_2: <topic name>
"""

    response = model.generate_content([pdf_file, prompt])

    selected_topics = []
    for line in response.text.strip().splitlines():
        if ":" in line:
            topic = line.split(":", 1)[1].strip()
            if topic in available_topics:
                selected_topics.append(topic)

    if len(selected_topics) != 2:
        raise ValueError(f"Expected 2 topics, got {len(selected_topics)}: {selected_topics}")

    return selected_topics


def verify_personas_exist(topics: list[str], persona_base: Path) -> dict[str, Path]:
    """Map topics to persona files and verify they exist.

    Returns dict of {topic: persona_path}.
    Exits if any persona is missing.
    """
    persona_map = {}
    missing = []

    for topic in topics:
        persona_filename = sanitize_filename(topic)
        persona_path = persona_base / persona_filename

        if not persona_path.exists():
            missing.append(f"  - Topic: {topic}\n    Expected: {persona_path}")
        else:
            persona_map[topic] = persona_path

    if missing:
        print("\n❌ ERROR: Missing personas:")
        for m in missing:
            print(m)
        sys.exit(1)

    return persona_map


def generate_short_name(topic: str, existing_shorts: set[str]) -> str:
    """Generate a short name for a persona (2-4 chars)."""
    # Try first 2-4 letters of first word
    words = topic.lower().split()
    if words:
        base = re.sub(r'[^a-z]', '', words[0])[:4]
        candidate = base[:2]

        # If collision, try longer versions
        for length in [3, 4]:
            if candidate not in existing_shorts:
                return candidate
            candidate = base[:length]

        # Last resort: add number
        i = 2
        while f"{candidate}{i}" in existing_shorts:
            i += 1
        return f"{candidate}{i}"

    return "unk"


def create_custom_config(
    baseline_config: Path,
    selected_topics: list[str],
    persona_base: Path,
    output_path: Path
) -> None:
    """Generate a custom config.toml based on baseline + selected personas."""

    # Load baseline
    with open(baseline_config, "rb") as f:
        config = tomllib.load(f)

    # Get existing short names to avoid collisions
    existing_shorts = {p["short"] for p in config.get("personas", [])}

    # Add new personas
    # main.py always prepends "personas/", so we need path relative to personas/ directory
    persona_relative_to_root = persona_base.relative_to(BASE_DIR.parent)

    # Strip "personas/" prefix if present
    persona_parts = persona_relative_to_root.parts
    if persona_parts[0] == "personas":
        persona_subdir = "/".join(persona_parts[1:])  # e.g., "prelim_draftanalyst"
    else:
        persona_subdir = persona_relative_to_root.as_posix()

    for topic in selected_topics:
        persona_filename = sanitize_filename(topic)
        persona_stem = persona_filename.replace(".md", "")

        # Config path should be relative to personas/ directory
        if persona_subdir:
            persona_full_name = f"{persona_subdir}/{persona_stem}"
        else:
            persona_full_name = persona_stem

        # Check if already in config
        if any(p["name"] == persona_full_name for p in config.get("personas", [])):
            continue

        short = generate_short_name(topic, existing_shorts)
        existing_shorts.add(short)

        config.setdefault("personas", []).append({
            "name": persona_full_name,
            "short": short
        })

    # Write custom config
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Auto-generated config for preliminary draft analysis\n")
        f.write(f"# Synthesizer persona\n")
        f.write(f'synthesizer = "{config["synthesizer"]}"\n\n')
        f.write("# Expert-reviewer personas\n")
        for persona in config["personas"]:
            f.write("[[personas]]\n")
            f.write(f'name  = "{persona["name"]}"\n')
            f.write(f'short = "{persona["short"]}"\n\n')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-run Gauntlet in preliminary draft analysis mode with dynamic persona selection"
    )
    parser.add_argument("papers_dir", type=Path,
                        help="directory containing paper subdirectories (each with baseline.pdf + draft PDF)")
    parser.add_argument("--topics", type=Path, required=True,
                        help="path to TOPICS.txt file")
    parser.add_argument("--baseline-config", type=Path, required=True,
                        help="baseline config.toml to extend (e.g., config_prelim_draftanalyst_archgeneric.toml)")
    parser.add_argument("--persona-dir", type=Path, required=True,
                        help="directory containing persona .md files (e.g., personas/prelim_draftanalyst)")

    args = parser.parse_args()

    # --- API key ---
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("ERROR: GOOGLE_API_KEY not set. Check your .env file.")
    genai.configure(api_key=api_key)

    # --- Validate paths ---
    # Make persona_dir absolute
    if not args.persona_dir.is_absolute():
        args.persona_dir = (BASE_DIR.parent / args.persona_dir).resolve()

    if not args.persona_dir.exists():
        sys.exit(f"ERROR: Persona directory not found: {args.persona_dir}")

    # --- Load topics ---
    available_topics = load_topics(args.topics)
    print(f"[setup]   {len(available_topics)} topics loaded from {args.topics.name}")

    # --- Find subdirectories ---
    subdirs = [d for d in args.papers_dir.iterdir() if d.is_dir()]
    if not subdirs:
        sys.exit(f"No subdirectories found in {args.papers_dir}")

    print(f"[setup]   {len(subdirs)} subdirectories to process\n")

    # main.py is in the parent directory (Gauntlet root)
    main_script = BASE_DIR.parent / "main.py"
    if not main_script.exists():
        sys.exit(f"ERROR: main.py not found at {main_script}")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for subdir in sorted(subdirs):
        print(f"[process] {subdir.name}")

        # Find baseline.pdf and draft PDF in subdirectory
        baseline_pdf = subdir / "baseline.pdf"
        if not baseline_pdf.exists():
            print(f"          [skip] baseline.pdf not found\n")
            skip_count += 1
            continue

        # Find draft PDF (any PDF that's not baseline.pdf)
        pdfs = [p for p in subdir.glob("*.pdf") if p.name != "baseline.pdf"]
        if not pdfs:
            print(f"          [skip] no draft PDF found (only baseline.pdf)\n")
            skip_count += 1
            continue
        if len(pdfs) > 1:
            print(f"          [skip] multiple draft PDFs found, ambiguous\n")
            skip_count += 1
            continue

        draft_pdf = pdfs[0]
        print(f"          baseline: {baseline_pdf.name}")
        print(f"          draft:    {draft_pdf.name}")

        # Check if already processed (idempotent)
        # Only skip if a FULL run completed (SYNTHESIS.md exists)
        runs_dir = subdir / "runs"
        if runs_dir.exists() and runs_dir.is_dir():
            # Check if runs directory contains a completed synthesis
            synthesis_files = list(runs_dir.glob("**/SYNTHESIS.md"))
            if synthesis_files:
                print(f"          [skip] already processed (found {len(synthesis_files)} completed run(s))\n")
                skip_count += 1
                continue

        try:
            # Upload DRAFT PDF and get matching topics
            gemini_file = upload_pdf_to_gemini(draft_pdf)
            print(f"          analyzing topics...")
            selected_topics = get_matching_topics(gemini_file, available_topics)

            print(f"          selected topics:")
            for i, topic in enumerate(selected_topics, 1):
                print(f"            {i}. {topic}")

            # Verify personas exist
            verify_personas_exist(selected_topics, args.persona_dir)
            print(f"          ✓ all personas verified")

            # Generate custom config
            custom_config = subdir / "config_prelimdraft.toml"
            create_custom_config(
                args.baseline_config,
                selected_topics,
                args.persona_dir,
                custom_config
            )
            print(f"          ✓ config generated: {custom_config.name}")

            # Clean up Gemini upload
            try:
                genai.delete_file(gemini_file.name)
            except Exception:
                pass

            # Output goes to <subdir>/runs/
            out_dir = subdir / "runs"

            # Run main.py (the Gauntlet)
            # Pass baseline.pdf as call, draft.pdf as proposal
            cmd = [
                sys.executable,
                str(main_script),
                "-c", str(custom_config),
                "-o", str(out_dir),
                str(baseline_pdf),
                str(draft_pdf)
            ]

            print(f"          → running Gauntlet...")
            print(f"          " + "="*60)

            result = subprocess.run(cmd)

            print(f"          " + "="*60)
            if result.returncode == 0:
                print(f"          ✓ success\n")
                success_count += 1
            else:
                print(f"          ✗ failed (exit code {result.returncode})\n")
                fail_count += 1

        except Exception as e:
            print(f"          ✗ error: {e}\n")
            fail_count += 1

    print(f"[done]    {success_count} succeeded, {skip_count} skipped, {fail_count} failed")


if __name__ == "__main__":
    main()
