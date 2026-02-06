"""Persona Factory — generates expert personas from templates.

Given a template persona file and a list of topics, this script uses Claude
to instantiate customized expert personas for each topic. Useful for rapidly
creating domain-specific reviewers for different research areas.
"""

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MODEL = "claude-opus-4-5-20251101"
GENERATION_TEMP: float = 0.7

# Rate limiting: pause between API calls to avoid throttling.
RATE_LIMIT_DELAY: float = 2.0


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_file(filepath: Path) -> Optional[str]:
    """Read content from a file."""
    if not filepath.exists():
        print(f"❌ Error: File not found: {filepath}")
        return None
    return filepath.read_text(encoding="utf-8").strip()


def load_topics(filepath: Path) -> list[str]:
    """Read topics from a text file, one per line. Ignore empty lines and comments."""
    if not filepath.exists():
        print(f"❌ Error: File not found: {filepath}")
        return []

    text = filepath.read_text(encoding="utf-8")
    # Filter out empty lines and comments
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    return lines


def sanitize_filename(name: str) -> str:
    """Convert a topic string into a clean filename."""
    name = name.lower()
    name = re.sub(r'[^a-z0-9]', '_', name)
    name = re.sub(r'_+', '_', name)
    return name.strip('_') + ".md"


# ---------------------------------------------------------------------------
# Persona generation
# ---------------------------------------------------------------------------

def generate_persona(client: Anthropic, topic: str, template_content: str) -> str:
    """Call Claude to instantiate the template for a specific topic."""
    print(f"   ...Synthesizing expert for: {topic}...")

    prompt = f"""
You are an expert creative writer for technical roleplay.

**YOUR TASK:**
I will provide you a "Persona Template" with placeholders (e.g., [Insert Name], [Insert Field]).
You must generate a specific, realistic, and highly technical persona file for the research topic: "{topic}".

**INSTRUCTIONS:**
1. Fill in ALL placeholders in the template with creative, domain-specific details relevant to "{topic}".
2. Invent a fictional but realistic name (e.g., Dr. Archi, Prof. Q).
3. Use real technical jargon, real corner cases, and real baseline examples for this field.
4. Output ONLY the final Markdown content. Do not output the "System Prompt" wrapper text.

**THE TEMPLATE:**
{template_content}
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        temperature=GENERATION_TEMP,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Persona Factory — generate expert personas from templates"
    )
    parser.add_argument("--template", type=Path, required=True,
                        help="Path to the .md template file")
    parser.add_argument("--topics", type=Path, required=True,
                        help="Path to the .txt file containing topics (one per line)")
    parser.add_argument("-o", "--output", type=Path, default=BASE_DIR / "generated_personas",
                        help="Output directory (default: <script dir>/generated_personas)")

    args = parser.parse_args()

    # --- Check API key ---
    api_key: Optional[str] = None
    try:
        import os
        api_key = os.getenv("ANTHROPIC_API_KEY")
    except Exception:
        pass

    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY not set. Check your .env file.")

    client = Anthropic(api_key=api_key)

    # --- Load inputs ---
    template_content = load_file(args.template)
    topics = load_topics(args.topics)

    if not template_content or not topics:
        sys.exit("ERROR: Failed to load template or topics.")

    print(f"🏭 Persona Factory Initialized")
    print(f"   📄 Template: {args.template}")
    print(f"   📚 Topics: {len(topics)}")
    print(f"   📂 Output: {args.output}\n")

    args.output.mkdir(parents=True, exist_ok=True)

    # --- Generate personas ---
    for topic in topics:
        try:
            persona_content = generate_persona(client, topic, template_content)

            filename = sanitize_filename(topic)
            filepath = args.output / filename

            filepath.write_text(persona_content, encoding="utf-8")

            print(f"   ✅ Saved: {filepath}\n")

            # Rate limiting politeness
            time.sleep(RATE_LIMIT_DELAY)

        except Exception as e:
            print(f"   ❌ Error generating {topic}: {e}")

    print("[done] Generated personas successfully.")


if __name__ == "__main__":
    main()