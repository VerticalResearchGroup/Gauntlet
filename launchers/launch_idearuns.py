"""launch_idearuns.py — Batch-run idea_generator.py across organized papers.

For each subdirectory in the provided start directory:
1. Finds the PDF
2. Finds config_archresearch.toml
3. Runs idea_generator.py with that PDF, config, and output to that subdir

Usage:
    python launch_idearuns.py <start_directory>
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-run idea_generator.py across organized paper directories"
    )
    parser.add_argument("start_dir", type=Path,
                        help="directory containing paper subdirectories")
    args = parser.parse_args()

    subdirs = [d for d in args.start_dir.iterdir() if d.is_dir()]
    if not subdirs:
        sys.exit(f"No subdirectories found in {args.start_dir}")

    print(f"[setup]   {len(subdirs)} subdirectories to process\n")

    # idea_generator.py is in the parent directory (Gauntlet root)
    idea_gen_script = Path(__file__).resolve().parent.parent / "idea_generator.py"
    if not idea_gen_script.exists():
        sys.exit(f"ERROR: idea_generator.py not found at {idea_gen_script}")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for subdir in sorted(subdirs):
        print(f"[process] {subdir.name}")

        # Find the PDF
        pdfs = list(subdir.glob("*.pdf"))
        if not pdfs:
            print(f"          [skip] no PDF found\n")
            skip_count += 1
            continue
        if len(pdfs) > 1:
            print(f"          [skip] multiple PDFs found\n")
            skip_count += 1
            continue
        pdf = pdfs[0]

        # Find config_archresearch.toml
        config = subdir / "config_archresearch.toml"
        if not config.exists():
            print(f"          [skip] config_archresearch.toml not found\n")
            skip_count += 1
            continue

        # Run idea_generator.py
        cmd = [
            sys.executable,
            str(idea_gen_script),
            "-c", str(config),
            "-o", str(subdir),
            str(pdf)
        ]

        print(f"          PDF:    {pdf.name}")
        print(f"          config: {config.name}")
        print(f"          output: {subdir.name}/")
        print(f"          → running idea_generator.py...")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"          ✓ success\n")
            success_count += 1
        else:
            print(f"          ✗ failed (exit code {result.returncode})")
            if result.stderr:
                print(f"          stderr: {result.stderr[:300]}\n")
            fail_count += 1

    print(f"[done]    {success_count} succeeded, {skip_count} skipped, {fail_count} failed")


if __name__ == "__main__":
    main()
