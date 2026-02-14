"""launch_gauntletruns.py — Batch-run main.py (Gauntlet) across idea kernels.

For each subdirectory:
1. Looks for idea_kernel.pdf (the proposal to review) — skip if missing
2. Finds the OTHER PDF (not idea_kernel.pdf) — this is the call/solicitation
3. Finds config_archresearch.toml
4. Runs main.py with those inputs, output to <subdir>/runs/

Usage:
    python launch_gauntletruns.py <start_directory>
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch-run main.py (Gauntlet) across idea kernel directories"
    )
    parser.add_argument("start_dir", type=Path,
                        help="directory containing paper subdirectories")
    args = parser.parse_args()

    subdirs = [d for d in args.start_dir.iterdir() if d.is_dir()]
    if not subdirs:
        sys.exit(f"No subdirectories found in {args.start_dir}")

    print(f"[setup]   {len(subdirs)} subdirectories to process\n")

    # main.py is in the parent directory (Gauntlet root)
    main_script = Path(__file__).resolve().parent.parent / "main.py"
    if not main_script.exists():
        sys.exit(f"ERROR: main.py not found at {main_script}")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for subdir in sorted(subdirs):
        print(f"[process] {subdir.name}")

        # Check for idea_kernel.pdf (the proposal)
        proposal = subdir / "idea_kernel.pdf"
        if not proposal.exists():
            print(f"          [skip] idea_kernel.pdf not found\n")
            skip_count += 1
            continue

        # Find the OTHER PDF (not idea_kernel.pdf) — this is the call
        all_pdfs = list(subdir.glob("*.pdf"))
        call_pdfs = [p for p in all_pdfs if p.name != "idea_kernel.pdf"]

        if not call_pdfs:
            print(f"          [skip] no call PDF found (need another PDF besides idea_kernel.pdf)\n")
            skip_count += 1
            continue
        if len(call_pdfs) > 1:
            print(f"          [skip] multiple non-kernel PDFs, ambiguous which is the call\n")
            skip_count += 1
            continue
        call_pdf = call_pdfs[0]

        # Find config_archresearch.toml
        config = subdir / "config_archresearch.toml"
        if not config.exists():
            print(f"          [skip] config_archresearch.toml not found\n")
            skip_count += 1
            continue

        # Output goes to <subdir>/runs/
        out_dir = subdir / "runs"

        # Run main.py (the Gauntlet)
        cmd = [
            sys.executable,
            str(main_script),
            "-c", str(config),
            "-o", str(out_dir),
            str(call_pdf),
            str(proposal)
        ]

        print(f"          call:     {call_pdf.name}")
        print(f"          proposal: {proposal.name}")
        print(f"          config:   {config.name}")
        print(f"          output:   runs/")
        print(f"          → running main.py (Gauntlet)...")

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
