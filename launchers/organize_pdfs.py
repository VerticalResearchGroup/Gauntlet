"""organize_pdfs.py — Extract titles via Gemini, organize PDFs into named directories.

Reads every PDF in a given directory, extracts its title using Gemini
1.5 Flash, generates a 4-5 word hyphenated short name, and copies each
PDF into a subdirectory named <short-name>-<original-stem>.

mapping.txt is written into this script's directory (scratch/).

Usage:
    python organize_pdfs.py <pdf_directory>
"""

import argparse
import os
import re
import shutil
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

MODEL_NAME = "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# Helpers
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


def get_title_and_short(gemini_file) -> tuple[str, str]:
    """Extract title and a 4-5 word hyphenated short name from the paper.

    Returns (title, short_name).  Falls back gracefully if the model
    doesn't return the expected format.
    """
    model = genai.GenerativeModel(model_name=MODEL_NAME)
    response = model.generate_content([
        gemini_file,
        "This is a research paper.\n"
        "1. Extract the exact title.\n"
        "2. From that title create a short-name: 4 to 5 words, lowercase, hyphenated.\n"
        "   Example: speculative-decryption-cxl-cache\n\n"
        "Reply with ONLY these two lines, nothing else:\n"
        "TITLE: <exact title>\n"
        "SHORT: <hyphenated short name>"
    ])

    title, short = "", ""
    for line in response.text.strip().splitlines():
        if line.upper().startswith("TITLE:"):
            title = line.split(":", 1)[1].strip()
        elif line.upper().startswith("SHORT:"):
            short = line.split(":", 1)[1].strip()

    # Sanitize: lowercase, only alphanumeric + hyphens, collapse runs
    short = re.sub(r'[^a-z0-9-]', '', short.lower())
    short = re.sub(r'-+', '-', short).strip('-')

    return title or "(no title)", short or "untitled"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Organize PDFs into titled directories via Gemini"
    )
    parser.add_argument("pdf_dir", type=Path,
                        help="directory containing the PDFs to organize")
    args = parser.parse_args()

    # --- API key ---
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("ERROR: GOOGLE_API_KEY not set. Check your .env file.")
    genai.configure(api_key=api_key)

    # --- Find PDFs ---
    pdfs = sorted(args.pdf_dir.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDFs found in {args.pdf_dir}")

    print(f"[setup]   {len(pdfs)} PDF(s) in {args.pdf_dir}\n")

    mapping: list[tuple[str, str, str]] = []  # (original name, dir name, title)

    for pdf in pdfs:
        # --- resume: check if already organized ---
        # Look for existing directory matching pattern *-{pdf.stem}
        existing_dirs = list(args.pdf_dir.glob(f"*-{pdf.stem}"))
        already_processed = False

        for existing_dir in existing_dirs:
            if existing_dir.is_dir() and list(existing_dir.glob("*.pdf")):
                # Found a directory with a PDF already - skip
                dir_name = existing_dir.name
                print(f"[skip]    {pdf.name:50s} → {dir_name}/ (cached)")
                mapping.append((pdf.name, dir_name, "(cached)"))
                already_processed = True
                break

        if already_processed:
            continue

        print(f"[process] {pdf.name}")

        gemini_file = upload_pdf(pdf)
        title, short = get_title_and_short(gemini_file)

        # Directory name: short-name + original stem as suffix
        dir_name   = f"{short}-{pdf.stem}"
        dest_dir   = args.pdf_dir / dir_name
        dest_dir.mkdir(exist_ok=True)
        shutil.copy2(pdf, dest_dir / pdf.name)

        print(f"          title: {title}")
        print(f"          →      {dir_name}/\n")

        mapping.append((pdf.name, dir_name, title))

        # Clean up the upload to stay within Gemini storage quota
        try:
            genai.delete_file(gemini_file.name)
        except Exception:
            pass

    # --- Write mapping.txt into scratch (next to this script) ---
    mapping_path = BASE_DIR / "mapping.txt"
    with open(mapping_path, "w", encoding="utf-8") as f:
        for pdf_name, dir_name, title in mapping:
            f.write(f"{pdf_name} → {dir_name}\n")
            f.write(f"  {title}\n\n")

    print(f"[done]    {len(mapping)} paper(s) organized")
    print(f"          mapping → {mapping_path}")


if __name__ == "__main__":
    main()
