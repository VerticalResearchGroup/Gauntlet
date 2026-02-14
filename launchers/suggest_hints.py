"""suggest_hints.py — Generate research extension hints for organized papers.

Walks through directories created by organize_pdfs.py, reads each paper,
and uses Gemini Pro to suggest 3-5 viable extension directions for future
research. Results are written to hints.txt in each paper's directory.

Usage:
    python suggest_hints.py <organized_directory>
"""

import argparse
import os
import sys
import time
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
# Helpers (reused patterns from organize_pdfs.py)
# ---------------------------------------------------------------------------

def upload_pdf(path: Path):
    """Upload a PDF to Gemini and wait for processing."""
    print(f"  uploading…", end="", flush=True)
    file = genai.upload_file(str(path), mime_type="application/pdf")
    while file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(1)
        file = genai.get_file(file.name)
    if file.state.name == "FAILED":
        raise ValueError(f"Upload failed: {file.state.name}")
    print(" ready.")
    return file


def get_extension_hints(gemini_file) -> str:
    """Ask Gemini for 3-5 research extension directions.

    Returns the raw response text (one idea per line).
    """
    model = genai.GenerativeModel(model_name=MODEL_NAME)
    response = model.generate_content([
        gemini_file,
        "Read this paper in depth, and suggest 3 to 5 directions it can be "
        "extended to be viable as future research publishable at a top-tier venue. Just 3 to 5 sentences "
        "per direction is fine. Provide your output in the format of one idea "
        "per line (numbered 1-5)."
    ])
    return response.text.strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate research extension hints for organized papers"
    )
    parser.add_argument("organized_dir", type=Path,
                        help="directory containing organized paper subdirectories")
    args = parser.parse_args()

    # --- API key ---
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("ERROR: GOOGLE_API_KEY not set. Check your .env file.")
    genai.configure(api_key=api_key)

    # --- Find subdirectories ---
    subdirs = [d for d in args.organized_dir.iterdir() if d.is_dir()]
    if not subdirs:
        sys.exit(f"No subdirectories found in {args.organized_dir}")

    print(f"[setup]   {len(subdirs)} paper(s) to process\n")

    for paper_dir in sorted(subdirs):
        # Find the PDF in this directory (should be exactly one)
        pdfs = list(paper_dir.glob("*.pdf"))
        if not pdfs:
            print(f"[skip]    {paper_dir.name} — no PDF found\n")
            continue
        if len(pdfs) > 1:
            print(f"[skip]    {paper_dir.name} — multiple PDFs, skipping\n")
            continue

        pdf = pdfs[0]
        hints_file = paper_dir / "hints.txt"

        # Skip if hints already exist (idempotent)
        if hints_file.exists():
            print(f"[skip]    {paper_dir.name} — hints.txt exists\n")
            continue

        print(f"[process] {paper_dir.name}")
        print(f"          {pdf.name}")

        gemini_file = upload_pdf(pdf)
        hints = get_extension_hints(gemini_file)

        hints_file.write_text(hints, encoding="utf-8")
        print(f"          → hints.txt\n")

        # Clean up to stay within quota
        try:
            genai.delete_file(gemini_file.name)
        except Exception:
            pass

    print(f"[done]    {len(subdirs)} paper(s) processed")


if __name__ == "__main__":
    main()
