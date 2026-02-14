"""perf.py — Quantitative Performance Evaluator for Research Papers

A three-phase verify-repair pipeline:
Phase 1: Specification Loop (Text → Math)
  - Generate spec (Prof. Aximo)
  - Verify spec (Dr. Logic)
  - Repair if needed (Prof. Aximo - Correction Mode)

Phase 2: Implementation Loop (Math → Python)
  - Implement model (Vector)
  - Dual verification (QA Engineer + PI)
  - Repair if needed (Vector - Debug Mode)

Phase 3: Interpretation (Python → Insight)
  - Interpret results (Technical Communicator)

The goal is to expose "magic gaps" where claimed performance exceeds
what the described mechanism can theoretically support.

Usage:
    python perf.py paper.pdf -c config_perf.toml -o outputs_perf/
"""

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Tuple

from anthropic import Anthropic
from dotenv import load_dotenv
from pypdf import PdfReader


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODEL = "claude-opus-4-5-20251101"
TEMPERATURE: float = 0.5
MAX_RETRIES: int = 5
MAX_REPAIR_ATTEMPTS: int = 3  # Max iterations for verify-repair loops


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_pdf_text(path: Path) -> str:
    """Extract full text from a PDF."""
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def load_persona(persona_path: Path, prime_directive_path: Path) -> str:
    """Read persona prompt and prepend the PRIME_DIRECTIVE.md (constitution).

    Returns combined prompt: PRIME_DIRECTIVE + persona-specific instructions.
    """
    if not persona_path.exists():
        raise FileNotFoundError(f"Persona file not found: {persona_path}")

    # Load prime directive (constitution)
    if not prime_directive_path.exists():
        raise FileNotFoundError(f"Prime directive not found: {prime_directive_path}")

    prime_directive = prime_directive_path.read_text(encoding="utf-8").strip()

    # Load persona-specific prompt
    persona_text = persona_path.read_text(encoding="utf-8").strip()

    # Strip markdown wrapper if present
    if persona_text.startswith("**System Prompt:**"):
        persona_text = persona_text[len("**System Prompt:**"):].strip()

    # Combine: Constitution first, then specific role
    combined_prompt = f"""{prime_directive}

---

# YOUR SPECIFIC ROLE

{persona_text}
"""

    return combined_prompt


def validate_python_syntax(code: str) -> Tuple[bool, Optional[str]]:
    """Validate Python code syntax.

    Returns (is_valid, error_message).
    """
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"


def extract_code_from_markdown(text: str) -> str:
    """Extract Python code from markdown code blocks."""
    if "```python" in text:
        start = text.find("```python") + len("```python")
        end = text.find("```", start)
        if end != -1:
            return text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + len("```")
        end = text.find("```", start)
        if end != -1:
            return text[start:end].strip()
    return text.strip()


# ---------------------------------------------------------------------------
# Phase 1: Specification Loop (Text → Math)
# ---------------------------------------------------------------------------

def phase1_generate_spec(
    client: Anthropic,
    paper_text: str,
    spec_generator_prompt: str,
    out_dir: Path
) -> str:
    """Generate initial mathematical specification."""
    print("\n[Phase 1.1] Generating mathematical specification...")
    print("            Agent: Prof. Aximo (spec_generator)")

    response = client.messages.create(
        model=MODEL,
        max_tokens=16384,
        temperature=TEMPERATURE,
        system=spec_generator_prompt,
        messages=[{"role": "user", "content": paper_text}],
    )

    spec_text = response.content[0].text
    print(f"            ✓ Generated")

    return spec_text


def phase1_verify_spec(
    client: Anthropic,
    paper_text: str,
    spec_text: str,
    spec_verifier_prompt: str
) -> Tuple[bool, str]:
    """Verify specification for completeness and correctness.

    Returns (is_valid, critique_or_approval).
    """
    print("\n[Phase 1.2] Verifying specification...")
    print("            Agent: Dr. Logic (spec_verifier)")

    user_message = f"""Please verify the following Mathematical Specification.

=== THE SPECIFICATION TO VERIFY ===
{spec_text}

=== ORIGINAL PAPER (for reference) ===
{paper_text}

Check for:
1. Missing variables or undefined symbols
2. Hallucinated formulas (not in the paper)
3. Missing calibration/reference data points
4. Incomplete constraint definitions

Respond with either:
- "APPROVED: <brief reason>" if the spec is complete
- "REVISION NEEDED: <detailed critique>" if there are issues
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        temperature=TEMPERATURE,
        system=spec_verifier_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    verification_result = response.content[0].text

    # Check if approved
    is_approved = verification_result.strip().upper().startswith("APPROVED")

    if is_approved:
        print("            ✓ APPROVED")
    else:
        print("            ✗ REVISION NEEDED")

    return is_approved, verification_result


def phase1_repair_spec(
    client: Anthropic,
    paper_text: str,
    spec_text: str,
    critique: str,
    spec_repair_prompt: str
) -> str:
    """Repair specification based on critique."""
    print("\n[Phase 1.3] Repairing specification...")
    print("            Agent: Prof. Aximo (spec_repair - Correction Mode)")

    user_message = f"""Your previous specification received critique from Dr. Logic.
Please fix the issues identified.

=== YOUR PREVIOUS SPECIFICATION ===
{spec_text}

=== DR. LOGIC'S CRITIQUE ===
{critique}

=== ORIGINAL PAPER (for reference) ===
{paper_text}

Please generate the CORRECTED specification addressing all points raised.
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=16384,
        temperature=TEMPERATURE,
        system=spec_repair_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    repaired_spec = response.content[0].text
    print("            ✓ Repaired")

    return repaired_spec


def run_phase1_loop(
    client: Anthropic,
    paper_text: str,
    personas: Dict[str, str],
    out_dir: Path
) -> str:
    """Run Phase 1 verify-repair loop until spec is approved."""

    # Generate initial spec
    spec_text = phase1_generate_spec(
        client,
        paper_text,
        personas['spec_generator'],
        out_dir
    )

    # Save initial draft as version 1
    draft_file = out_dir / "SPEC_draft_v1.md"
    draft_file.write_text(spec_text, encoding="utf-8")

    # Verify-repair loop
    for attempt in range(MAX_REPAIR_ATTEMPTS):
        is_approved, critique = phase1_verify_spec(
            client,
            paper_text,
            spec_text,
            personas['spec_verifier']
        )

        # Save critique for this attempt
        critique_file = out_dir / f"SPEC_CRITIQUE_v{attempt + 1}.txt"
        critique_file.write_text(critique, encoding="utf-8")
        print(f"            ✓ Critique saved: {critique_file.name}")

        if is_approved:
            # Save final approved spec
            final_spec_file = out_dir / "SPECIFICATION.md"
            final_spec_file.write_text(spec_text, encoding="utf-8")
            print(f"\n            ✓ Final spec saved: {final_spec_file}")
            return spec_text

        # Repair needed
        if attempt < MAX_REPAIR_ATTEMPTS - 1:
            spec_text = phase1_repair_spec(
                client,
                paper_text,
                spec_text,
                critique,
                personas['spec_repair']
            )

            # Save repaired draft
            draft_file = out_dir / f"SPEC_draft_v{attempt + 2}.md"
            draft_file.write_text(spec_text, encoding="utf-8")
            print(f"            ✓ Draft v{attempt + 2} saved: {draft_file.name}")
        else:
            print(f"\n            ⚠ Max repair attempts ({MAX_REPAIR_ATTEMPTS}) reached.")
            print(f"            Saving spec anyway - may need manual review.")
            final_spec_file = out_dir / "SPECIFICATION.md"
            final_spec_file.write_text(spec_text, encoding="utf-8")

            return spec_text

    return spec_text


# ---------------------------------------------------------------------------
# Phase 2: Implementation Loop (Math → Python)
# ---------------------------------------------------------------------------

def phase2_implement_model(
    client: Anthropic,
    paper_text: str,
    spec_text: str,
    model_implementer_prompt: str,
    out_dir: Path
) -> str:
    """Implement analytical model based on spec."""
    print("\n[Phase 2.1] Implementing analytical model...")
    print("            Agent: Vector (model_implementer)")

    user_message = f"""You have been provided with a Mathematical Specification by Prof. Aximo.
Your task is to implement this as a self-contained Python script.

=== THE SPECIFICATION ===
{spec_text}

=== ORIGINAL PAPER (for context) ===
{paper_text}

Please generate the complete Python script (`model.py`) that implements this specification.
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=16384,
        temperature=TEMPERATURE,
        system=model_implementer_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    model_code = extract_code_from_markdown(response.content[0].text)
    print(f"            ✓ Generated")

    return model_code


def phase2_verify_functional(
    client: Anthropic,
    spec_text: str,
    model_code: str,
    functional_verifier_prompt: str
) -> Tuple[bool, str]:
    """Verify model implementation matches specification (syntax/logic check)."""
    print("\n[Phase 2.2a] Functional verification...")
    print("             Agent: QA Engineer (functional_verifier)")

    user_message = f"""Please verify that this Python implementation correctly matches the Mathematical Specification.

=== THE SPECIFICATION ===
{spec_text}

=== THE IMPLEMENTATION ===
```python
{model_code}
```

Check for:
1. All functions from the spec are implemented
2. Mathematical formulas match the spec
3. Syntax errors or bugs
4. Missing imports or dependencies

Respond with either:
- "APPROVED: <brief reason>" if implementation is correct
- "REVISION NEEDED: <detailed critique>" if there are issues
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        temperature=TEMPERATURE,
        system=functional_verifier_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    verification_result = response.content[0].text
    is_approved = verification_result.strip().upper().startswith("APPROVED")

    if is_approved:
        print("             ✓ APPROVED")
    else:
        print("             ✗ REVISION NEEDED")

    return is_approved, verification_result


def phase2_verify_directive(
    client: Anthropic,
    model_code: str,
    directive_verifier_prompt: str
) -> Tuple[bool, str]:
    """Verify model meets Prime Directive requirements (science/goals check)."""
    print("\n[Phase 2.2b] Directive verification...")
    print("             Agent: PI (directive_verifier)")

    user_message = f"""Please verify that this Python implementation meets the Prime Directive requirements.

=== THE IMPLEMENTATION ===
```python
{model_code}
```

Check for:
1. First-principles derivation (not hardcoded values)
2. Calibration points plotted from paper
3. Self-contained (no external files needed)
4. Baseline vs Proposed comparison

Respond with either:
- "APPROVED: <brief reason>" if requirements are met
- "REVISION NEEDED: <detailed critique>" if there are violations
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        temperature=TEMPERATURE,
        system=directive_verifier_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    verification_result = response.content[0].text
    is_approved = verification_result.strip().upper().startswith("APPROVED")

    if is_approved:
        print("             ✓ APPROVED")
    else:
        print("             ✗ REVISION NEEDED")

    return is_approved, verification_result


def phase2_repair_model(
    client: Anthropic,
    spec_text: str,
    model_code: str,
    critique_functional: str,
    critique_directive: str,
    model_repair_prompt: str
) -> str:
    """Repair model implementation based on critiques."""
    print("\n[Phase 2.3] Repairing model implementation...")
    print("            Agent: Vector (model_repair - Debug Mode)")

    combined_critique = f"""=== FUNCTIONAL VERIFIER (QA Engineer) ===
{critique_functional}

=== DIRECTIVE VERIFIER (PI) ===
{critique_directive}
"""

    user_message = f"""Your previous implementation received critiques from the verification team.
Please fix the issues identified.

=== YOUR PREVIOUS IMPLEMENTATION ===
```python
{model_code}
```

=== CRITIQUES ===
{combined_critique}

=== THE SPECIFICATION (for reference) ===
{spec_text}

Please generate the CORRECTED Python script addressing all points raised.
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=16384,
        temperature=TEMPERATURE,
        system=model_repair_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    repaired_code = extract_code_from_markdown(response.content[0].text)
    print("            ✓ Repaired")

    return repaired_code


def run_phase2_loop(
    client: Anthropic,
    paper_text: str,
    spec_text: str,
    personas: Dict[str, str],
    out_dir: Path
) -> str:
    """Run Phase 2 verify-repair loop until model is approved."""

    # Generate initial implementation
    model_code = phase2_implement_model(
        client,
        paper_text,
        spec_text,
        personas['model_implementer'],
        out_dir
    )

    # Save initial draft as version 1
    draft_file = out_dir / "model_draft_v1.py"
    draft_file.write_text(model_code, encoding="utf-8")

    # Verify-repair loop
    for attempt in range(MAX_REPAIR_ATTEMPTS):
        # Dual verification
        functional_approved, critique_functional = phase2_verify_functional(
            client,
            spec_text,
            model_code,
            personas['functional_verifier']
        )

        directive_approved, critique_directive = phase2_verify_directive(
            client,
            model_code,
            personas['directive_verifier']
        )

        # Save critiques for this attempt
        critique_func_file = out_dir / f"MODEL_CRITIQUE_FUNCTIONAL_v{attempt + 1}.txt"
        critique_func_file.write_text(critique_functional, encoding="utf-8")
        print(f"             ✓ Functional critique saved: {critique_func_file.name}")

        critique_dir_file = out_dir / f"MODEL_CRITIQUE_DIRECTIVE_v{attempt + 1}.txt"
        critique_dir_file.write_text(critique_directive, encoding="utf-8")
        print(f"             ✓ Directive critique saved: {critique_dir_file.name}")

        both_approved = functional_approved and directive_approved

        if both_approved:
            # Save final approved model
            final_model_file = out_dir / "model.py"
            final_model_file.write_text(model_code, encoding="utf-8")
            print(f"\n            ✓ Final model saved: {final_model_file}")

            # Validate syntax one more time
            is_valid, error_msg = validate_python_syntax(model_code)
            if is_valid:
                print(f"            ✓ Python syntax valid")
                print(f"\n            → Run the model with: python {final_model_file}")
            else:
                print(f"            ⚠ Warning: Syntax error detected:")
                print(f"               {error_msg}")

            return model_code

        # Repair needed
        if attempt < MAX_REPAIR_ATTEMPTS - 1:
            model_code = phase2_repair_model(
                client,
                spec_text,
                model_code,
                critique_functional,
                critique_directive,
                personas['model_repair']
            )

            # Save repaired draft
            draft_file = out_dir / f"model_draft_v{attempt + 2}.py"
            draft_file.write_text(model_code, encoding="utf-8")
            print(f"            ✓ Draft v{attempt + 2} saved: {draft_file.name}")
        else:
            print(f"\n            ⚠ Max repair attempts ({MAX_REPAIR_ATTEMPTS}) reached.")
            print(f"            Saving model anyway - may need manual review.")
            final_model_file = out_dir / "model.py"
            final_model_file.write_text(model_code, encoding="utf-8")

            return model_code

    return model_code


# ---------------------------------------------------------------------------
# Phase 3: Interpretation (Python → Insight)
# ---------------------------------------------------------------------------

def phase3_interpret_results(
    client: Anthropic,
    spec_text: str,
    model_code: str,
    model_interpreter_prompt: str,
    out_dir: Path
) -> None:
    """Generate human-readable interpretation of the model."""
    print("\n[Phase 3] Generating interpretation...")
    print("          Agent: Technical Communicator (model_interpreter)")

    user_message = f"""Please generate a plain-English interpretation of this analytical model.

=== THE SPECIFICATION ===
{spec_text}

=== THE IMPLEMENTATION ===
```python
{model_code}
```

Explain:
1. What the model assumes
2. What it calculates
3. Key findings or potential "magic gaps"
4. Limitations of the analysis
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        temperature=TEMPERATURE,
        system=model_interpreter_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    interpretation = response.content[0].text

    # Save interpretation
    interp_file = out_dir / "INTERPRETATION.md"
    interp_file.write_text(interpretation, encoding="utf-8")
    print(f"          ✓ Saved: {interp_file}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="perf.py — Quantitative Performance Evaluator (3-Phase Pipeline)"
    )
    parser.add_argument("paper_pdf", type=Path,
                        help="research paper PDF to evaluate")
    parser.add_argument("-c", "--config", type=Path, required=True,
                        help="config file specifying personas (e.g., config_perf.toml)")
    parser.add_argument("-o", "--output", type=Path, default=BASE_DIR / "outputs_perf",
                        help="output directory (default: outputs_perf/)")

    args = parser.parse_args()

    # --- Check API key ---
    api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY not set. Check your .env file.")

    client = Anthropic(api_key=api_key, max_retries=MAX_RETRIES)

    # --- Load config ---
    if not args.config.exists():
        sys.exit(f"ERROR: Config file not found: {args.config}")

    import tomllib
    with open(args.config, "rb") as f:
        config = tomllib.load(f)

    # Get persona paths from config
    prime_directive_path = BASE_DIR / config.get(
        "prime_directive",
        "personas/quant_eval/PRIME_DIRECTIVE.md"
    )

    persona_paths = {
        'spec_generator': BASE_DIR / config.get(
            "spec_generator",
            "personas/quant_eval/spec_generator.md"
        ),
        'spec_verifier': BASE_DIR / config.get(
            "spec_verifier",
            "personas/quant_eval/spec_verifier.md"
        ),
        'spec_repair': BASE_DIR / config.get(
            "spec_repair",
            "personas/quant_eval/spec_repair.md"
        ),
        'model_implementer': BASE_DIR / config.get(
            "model_implementer",
            "personas/quant_eval/model_implementer.md"
        ),
        'functional_verifier': BASE_DIR / config.get(
            "functional_verifier",
            "personas/quant_eval/functional_verifier.md"
        ),
        'directive_verifier': BASE_DIR / config.get(
            "directive_verifier",
            "personas/quant_eval/directive_verifier.md"
        ),
        'model_repair': BASE_DIR / config.get(
            "model_repair",
            "personas/quant_eval/model_repair.md"
        ),
        'model_interpreter': BASE_DIR / config.get(
            "model_interpreter",
            "personas/quant_eval/model_interpretter.md"
        ),
    }

    # --- Load paper ---
    print("=" * 80)
    print("QUANTITATIVE PERFORMANCE EVALUATOR")
    print("=" * 80)
    print(f"\n[Setup] Loading paper: {args.paper_pdf.name}")
    paper_text = load_pdf_text(args.paper_pdf)
    print(f"        {len(paper_text):,} characters")

    # --- Load personas (with Prime Directive prepended) ---
    print(f"\n[Setup] Loading personas (with Prime Directive)...")
    print(f"        Constitution: {prime_directive_path.name}")

    personas = {}
    for role, path in persona_paths.items():
        personas[role] = load_persona(path, prime_directive_path)
        print(f"        ✓ {role}: {path.name}")

    # --- Create output directory ---
    args.output.mkdir(parents=True, exist_ok=True)
    print(f"\n[Setup] Output directory: {args.output}")

    # ========================================================================
    # PHASE 1: SPECIFICATION LOOP
    # ========================================================================
    print("\n" + "=" * 80)
    print("PHASE 1: SPECIFICATION LOOP (Text → Math)")
    print("=" * 80)

    spec_text = run_phase1_loop(
        client,
        paper_text,
        personas,
        args.output
    )

    # ========================================================================
    # PHASE 2: IMPLEMENTATION LOOP
    # ========================================================================
    print("\n" + "=" * 80)
    print("PHASE 2: IMPLEMENTATION LOOP (Math → Python)")
    print("=" * 80)

    model_code = run_phase2_loop(
        client,
        paper_text,
        spec_text,
        personas,
        args.output
    )

    # ========================================================================
    # PHASE 3: INTERPRETATION
    # ========================================================================
    print("\n" + "=" * 80)
    print("PHASE 3: INTERPRETATION (Python → Insight)")
    print("=" * 80)

    phase3_interpret_results(
        client,
        spec_text,
        model_code,
        personas['model_interpreter'],
        args.output
    )

    # --- Summary ---
    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)
    print(f"\nGenerated artifacts:")
    print(f"  1. SPECIFICATION.md    — Mathematical specification")
    print(f"  2. model.py            — Analytical model implementation")
    print(f"  3. INTERPRETATION.md   — Plain-English summary")
    print(f"\nNext steps:")
    print(f"  1. Review: {args.output / 'SPECIFICATION.md'}")
    print(f"  2. Run:    python {args.output / 'model.py'}")
    print(f"  3. Check:  {args.output / 'evaluation_plot.png'}")
    print(f"  4. Read:   {args.output / 'INTERPRETATION.md'}")
    print()


if __name__ == "__main__":
    main()
