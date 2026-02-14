So the full pipeline is:

organize_pdfs.py → creates subdirectories
suggest_hints.py → adds hints.txt to each
(human) → creates config_archresearch.toml in each with appropriate seed
launch_idearuns.py → generates idea_kernel.md in each
(human) → edits and converts idea_kernel.md → idea_kernel.pdf
launch_gauntletruns.py → runs Gauntlet on each, outputs to runs/

scratch/launch_idearuns.py. Run it like:


python scratch/launch_idearuns.py path/to/organized/papers
For each subdirectory, it:

Looks for exactly one PDF (skips if zero or multiple).
Looks for config_archresearch.toml (skips if missing).
Calls idea_generator.py -c <config> -o <subdir> <pdf> as a subprocess.
Reports success/failure and continues to the next subdirectory even if one fails.
Summarizes at the end: how many succeeded, skipped, failed.

scratch/launch_gauntletruns.py. Run it like:

python scratch/launch_gauntletruns.py path/to/organized/papers

For each subdirectory, it:

Looks for idea_kernel.pdf (the proposal to review) — skips if missing.
Finds the OTHER PDF (not idea_kernel.pdf) — this becomes the call/solicitation.
Looks for config_archresearch.toml — skips if missing.
Runs main.py -c <config> -o <subdir>/runs/ <call_pdf> idea_kernel.pdf.
Reports success/failure and continues to the next subdirectory.
Expected structure:


organized_papers/
  paper1-short-name/
    paper1.pdf                    ← becomes the "call"
    config_archresearch.toml
    idea_kernel.md                ← from idea_generator.py
    idea_kernel.pdf               ← you converted this
    runs/                         ← Gauntlet output lands here
      RUN_CONFIG.md
      expert_reviews/
      syntheses/
