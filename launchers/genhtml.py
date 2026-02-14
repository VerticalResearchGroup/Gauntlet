#!/usr/bin/env python3
"""
Static HTML generator for Gauntlet synthesis reports.
Scans directories for runs/syntheses subdirectories and generates a single HTML file.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import argparse


def find_paper_directories(parent_dir: Path) -> List[Tuple[str, Path, str, str]]:
    """
    Find all paper directories that contain runs/syntheses subdirectories.
    Returns list of (paper_name, syntheses_path, pdf_filename, idea_kernel_content) tuples.
    """
    papers = []

    if not parent_dir.exists():
        print(f"Error: Directory {parent_dir} does not exist")
        return papers

    # Iterate through all subdirectories in parent_dir
    for item in sorted(parent_dir.iterdir()):
        if item.is_dir():
            syntheses_path = item / "runs" / "syntheses"
            if syntheses_path.exists() and syntheses_path.is_dir():
                # Extract paper name from directory name
                paper_name = item.name

                # Find PDF file in the paper directory
                pdf_filename = None
                for pdf_file in item.glob("*.pdf"):
                    # Prefer the PDF that matches the paper ID pattern (numbers.numbers.pdf)
                    if pdf_file.stem.replace('.', '').isdigit():
                        pdf_filename = pdf_file.name
                        break

                # If no matching PDF found, just take the first PDF
                if not pdf_filename:
                    pdf_files = list(item.glob("*.pdf"))
                    if pdf_files:
                        pdf_filename = pdf_files[0].name

                # Read idea_kernel.md if it exists
                idea_kernel_path = item / "idea_kernel.md"
                idea_kernel_content = read_markdown_file(idea_kernel_path) if idea_kernel_path.exists() else None

                papers.append((paper_name, syntheses_path, pdf_filename, idea_kernel_content))

    return papers


def find_gauntlet_runs(syntheses_path: Path) -> List[str]:
    """
    Find all gauntlet run directories within a syntheses directory.
    Returns sorted list of run directory names.
    """
    runs = []

    for item in sorted(syntheses_path.iterdir()):
        if item.is_dir():
            # Check if it contains any review markdown files or SYNTHESIS.md
            review_files = list(item.glob("*_review.md"))
            synthesis_file = item / "SYNTHESIS.md"

            # If at least one review file or SYNTHESIS.md exists, consider it a valid run
            if review_files or synthesis_file.exists():
                runs.append(item.name)

    return runs


def read_markdown_file(file_path: Path) -> str:
    """
    Read a markdown file and return its contents.
    Returns empty string if file doesn't exist.
    """
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"
    else:
        return f"File not found: {file_path.name}"


def markdown_to_html(md_text: str) -> str:
    """
    Convert markdown to HTML with basic formatting.
    Uses simple replacements for common markdown syntax.
    """
    html = md_text

    # Escape HTML special characters first
    # html = html.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    # Headers
    lines = html.split('\n')
    processed_lines = []
    in_code_block = False

    for line in lines:
        # Handle code blocks
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            if in_code_block:
                processed_lines.append('<pre><code>')
            else:
                processed_lines.append('</code></pre>')
            continue

        if in_code_block:
            processed_lines.append(line)
            continue

        # Headers
        if line.startswith('# '):
            processed_lines.append(f'<h1>{line[2:]}</h1>')
        elif line.startswith('## '):
            processed_lines.append(f'<h2>{line[3:]}</h2>')
        elif line.startswith('### '):
            processed_lines.append(f'<h3>{line[4:]}</h3>')
        elif line.startswith('#### '):
            processed_lines.append(f'<h4>{line[5:]}</h4>')
        # Bold
        elif '**' in line:
            # Simple bold replacement
            import re
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            processed_lines.append(f'<p>{line}</p>')
        # Italic
        elif '*' in line or '_' in line:
            import re
            line = re.sub(r'\*(.+?)\*', r'<em>\1</em>', line)
            line = re.sub(r'_(.+?)_', r'<em>\1</em>', line)
            processed_lines.append(f'<p>{line}</p>')
        # Empty line
        elif line.strip() == '':
            processed_lines.append('<br>')
        # Regular paragraph
        else:
            processed_lines.append(f'<p>{line}</p>')

    return '\n'.join(processed_lines)


def generate_html(papers_data: List[Dict], output_path: Path):
    """
    Generate the final HTML file with all papers and their synthesis reports.
    """
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gauntlet Synthesis Reports</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
        }}

        .container {{
            display: flex;
            min-height: 100vh;
        }}

        .sidebar {{
            width: 300px;
            background: #2c3e50;
            color: #ecf0f1;
            padding: 20px;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }}

        .sidebar h1 {{
            font-size: 24px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #34495e;
        }}

        .paper-link {{
            display: block;
            padding: 10px;
            margin: 5px 0;
            background: #34495e;
            color: #ecf0f1;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s;
            font-size: 14px;
            word-wrap: break-word;
        }}

        .paper-link:hover {{
            background: #4a6278;
        }}

        .content {{
            margin-left: 300px;
            flex: 1;
            padding: 40px;
        }}

        .paper-section {{
            background: white;
            padding: 30px;
            margin-bottom: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .paper-title {{
            font-size: 32px;
            color: #2c3e50;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 3px solid #3498db;
        }}

        .pdf-link-container {{
            margin-bottom: 25px;
            padding: 15px;
            background: #e8f4f8;
            border-left: 4px solid #3498db;
            border-radius: 4px;
        }}

        .pdf-link {{
            display: inline-block;
            padding: 10px 20px;
            background: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 600;
            font-size: 16px;
            transition: background 0.3s;
        }}

        .pdf-link:hover {{
            background: #2980b9;
        }}

        .reviewers-section {{
            margin-bottom: 25px;
            padding: 15px;
            background: #f0fdf4;
            border-left: 4px solid #10b981;
            border-radius: 4px;
        }}

        .reviewers-title {{
            font-size: 16px;
            color: #047857;
            margin-bottom: 10px;
            font-weight: 600;
        }}

        .reviewers-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }}

        .reviewer-badge {{
            display: inline-block;
            padding: 6px 12px;
            background: #d1fae5;
            color: #065f46;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 500;
            border: 1px solid #a7f3d0;
            text-decoration: none;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
        }}

        .reviewer-badge:hover {{
            background: #a7f3d0;
            transform: translateY(-1px);
        }}

        .back-to-top {{
            display: inline-block;
            margin-top: 20px;
            padding: 8px 16px;
            background: #f3f4f6;
            color: #374151;
            text-decoration: none;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 500;
            border: 1px solid #d1d5db;
            transition: background 0.2s;
        }}

        .back-to-top:hover {{
            background: #e5e7eb;
        }}

        .idea-kernel-section {{
            margin-bottom: 30px;
            padding: 20px;
            background: #f0f9ff;
            border: 2px solid #0ea5e9;
            border-radius: 6px;
        }}

        .idea-kernel-title {{
            font-size: 20px;
            color: #0369a1;
            margin-bottom: 15px;
            font-weight: 700;
            display: flex;
            align-items: center;
        }}

        .idea-kernel-title::before {{
            content: "💡";
            margin-right: 10px;
            font-size: 24px;
        }}

        .idea-kernel-content {{
            color: #0c4a6e;
            line-height: 1.8;
        }}

        .run-section {{
            margin-bottom: 40px;
            padding: 20px;
            background: #f8f9fa;
            border-left: 4px solid #3498db;
            border-radius: 4px;
        }}

        .run-title {{
            font-size: 24px;
            color: #2c3e50;
            margin-bottom: 20px;
            font-weight: 600;
        }}

        .review-section {{
            margin-bottom: 30px;
            padding: 20px;
            background: white;
            border-radius: 4px;
            border: 1px solid #e1e4e8;
        }}

        .review-title {{
            font-size: 18px;
            color: #0366d6;
            margin-bottom: 15px;
            font-weight: 600;
            padding: 10px;
            background: #f6f8fa;
            border-left: 3px solid #0366d6;
        }}

        .synthesis-section {{
            margin-top: 20px;
            padding: 20px;
            background: #fffbea;
            border: 2px solid #f6b93b;
            border-radius: 4px;
        }}

        .synthesis-title {{
            font-size: 20px;
            color: #e58e26;
            margin-bottom: 15px;
            font-weight: 700;
        }}

        .review-content {{
            color: #24292e;
            line-height: 1.8;
        }}

        .review-content h1, .review-content h2, .review-content h3 {{
            margin-top: 20px;
            margin-bottom: 10px;
            color: #2c3e50;
        }}

        .review-content h1 {{
            font-size: 24px;
            border-bottom: 2px solid #e1e4e8;
            padding-bottom: 8px;
        }}

        .review-content h2 {{
            font-size: 20px;
        }}

        .review-content h3 {{
            font-size: 18px;
        }}

        .review-content p {{
            margin-bottom: 10px;
        }}

        .review-content pre {{
            background: #f6f8fa;
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
            margin: 15px 0;
        }}

        .review-content code {{
            background: #f6f8fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 14px;
        }}

        .review-content strong {{
            font-weight: 600;
            color: #2c3e50;
        }}

        .review-content em {{
            font-style: italic;
            color: #586069;
        }}

        @media (max-width: 768px) {{
            .sidebar {{
                width: 100%;
                position: relative;
                height: auto;
            }}

            .content {{
                margin-left: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h1>Papers</h1>
            {sidebar_content}
        </div>
        <div class="content">
            {main_content}
        </div>
    </div>
</body>
</html>
"""

    # Build sidebar links
    sidebar_links = []
    for paper in papers_data:
        paper_id = paper['name'].replace(' ', '-').replace('/', '-')
        sidebar_links.append(
            f'<a href="#{paper_id}" class="paper-link">{paper["name"]}</a>'
        )

    sidebar_html = '\n'.join(sidebar_links)

    # Build main content
    main_sections = []
    for paper in papers_data:
        paper_id = paper['name'].replace(' ', '-').replace('/', '-')

        runs_html = []
        for run in paper['runs']:
            reviews_html = []

            # Sort review files: all *_review.md files alphabetically, SYNTHESIS.md last
            review_files = sorted([f for f in run['reviews'].keys() if f != 'SYNTHESIS.md'])

            # Add all review files
            for filename in review_files:
                content = run['reviews'][filename]
                # Create a display title from the filename
                reviewer_name = filename.replace('_review.md', '').replace('_', ' ').title()
                title = reviewer_name + ' Review'
                # Create ID for this review
                review_id = f"{paper_id}-{reviewer_name.lower().replace(' ', '-')}"
                content_html = markdown_to_html(content)
                reviews_html.append(f'''
                <div class="review-section" id="{review_id}">
                    <div class="review-title">{title}</div>
                    <div class="review-content">
                        {content_html}
                        <a href="#{paper_id}" class="back-to-top">↑ Back to top of paper</a>
                    </div>
                </div>
                ''')

            # Add synthesis last
            if 'SYNTHESIS.md' in run['reviews']:
                content = run['reviews']['SYNTHESIS.md']
                content_html = markdown_to_html(content)
                reviews_html.append(f'''
                <div class="synthesis-section" id="{paper_id}-synthesis">
                    <div class="synthesis-title">SYNTHESIS</div>
                    <div class="review-content">
                        {content_html}
                        <a href="#{paper_id}" class="back-to-top">↑ Back to top of paper</a>
                    </div>
                </div>
                ''')

            runs_html.append(f'''
            <div class="run-section">
                <div class="run-title">Run: {run["name"]}</div>
                {''.join(reviews_html)}
            </div>
            ''')

        # Add PDF link if available
        pdf_link_html = ''
        if paper.get('pdf_filename'):
            pdf_url = f"paper_pdfs/{paper['pdf_filename']}"
            pdf_link_html = f'''
            <div class="pdf-link-container">
                <a href="{pdf_url}" class="pdf-link" target="_blank">📄 View Baseline Paper (PDF)</a>
            </div>
            '''

        # Collect all unique reviewers for this paper
        reviewers_html = ''
        all_reviewers = set()
        has_synthesis = False
        for run in paper['runs']:
            for filename in run['reviews'].keys():
                if filename != 'SYNTHESIS.md' and filename.endswith('_review.md'):
                    # Extract reviewer name from filename
                    reviewer_name = filename.replace('_review.md', '').replace('_', ' ').title()
                    all_reviewers.add(reviewer_name)
                elif filename == 'SYNTHESIS.md':
                    has_synthesis = True

        if all_reviewers or has_synthesis:
            # Add reviewer badges in sorted order (as clickable links)
            reviewer_badges = ''.join([
                f'<a href="#{paper_id}-{reviewer.lower().replace(" ", "-")}" class="reviewer-badge">{reviewer}</a>'
                for reviewer in sorted(all_reviewers)
            ])
            # Add Synthesis badge at the end
            if has_synthesis:
                reviewer_badges += f'<a href="#{paper_id}-synthesis" class="reviewer-badge">Synthesis</a>'

            reviewers_html = f'''
            <div class="reviewers-section">
                <div class="reviewers-title">👥 Expert Reviewers for this Paper:</div>
                <div class="reviewers-list">
                    {reviewer_badges}
                </div>
            </div>
            '''

        # Add idea kernel if available
        idea_kernel_html = ''
        if paper.get('idea_kernel'):
            idea_kernel_content_html = markdown_to_html(paper['idea_kernel'])
            idea_kernel_html = f'''
            <div class="idea-kernel-section">
                <div class="idea-kernel-title">Idea Kernel</div>
                <div class="idea-kernel-content">
                    {idea_kernel_content_html}
                </div>
            </div>
            '''

        main_sections.append(f'''
        <div class="paper-section" id="{paper_id}">
            <h2 class="paper-title">{paper["name"]}</h2>
            {pdf_link_html}
            {reviewers_html}
            {idea_kernel_html}
            {''.join(runs_html)}
        </div>
        ''')

    main_html = '\n'.join(main_sections)

    # Generate final HTML
    final_html = html_template.format(
        sidebar_content=sidebar_html,
        main_content=main_html
    )

    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_html)

    print(f"HTML generated successfully: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate HTML from Gauntlet synthesis reports'
    )
    parser.add_argument(
        'parent_dir',
        type=str,
        help='Parent directory containing paper subdirectories'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output HTML file path (default: index.html in parent_dir)'
    )

    args = parser.parse_args()

    parent_dir = Path(args.parent_dir)

    # Set output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = parent_dir / "index.html"

    print(f"Scanning directory: {parent_dir}")

    # Find all paper directories
    papers = find_paper_directories(parent_dir)

    if not papers:
        print("No paper directories with runs/syntheses found!")
        sys.exit(1)

    print(f"Found {len(papers)} paper(s)")

    # Collect all data
    papers_data = []

    for paper_name, syntheses_path, pdf_filename, idea_kernel_content in papers:
        print(f"\nProcessing: {paper_name}")
        if pdf_filename:
            print(f"  PDF: {pdf_filename}")
        if idea_kernel_content:
            print(f"  Idea kernel: Found")

        # Find all gauntlet runs
        runs = find_gauntlet_runs(syntheses_path)

        if not runs:
            print(f"  No gauntlet runs found in {syntheses_path}")
            continue

        print(f"  Found {len(runs)} run(s)")

        runs_data = []
        for run_name in runs:
            run_path = syntheses_path / run_name
            print(f"    Reading: {run_name}")

            # Dynamically find all review files (*_review.md) and SYNTHESIS.md
            reviews = {}

            # Find all *_review.md files
            for review_file in sorted(run_path.glob("*_review.md")):
                content = read_markdown_file(review_file)
                if content:
                    reviews[review_file.name] = content
                    print(f"      - {review_file.name}")

            # Add SYNTHESIS.md if it exists
            synthesis_file = run_path / 'SYNTHESIS.md'
            if synthesis_file.exists():
                content = read_markdown_file(synthesis_file)
                if content:
                    reviews['SYNTHESIS.md'] = content
                    print(f"      - SYNTHESIS.md")

            runs_data.append({
                'name': run_name,
                'reviews': reviews
            })

        papers_data.append({
            'name': paper_name,
            'runs': runs_data,
            'pdf_filename': pdf_filename,
            'idea_kernel': idea_kernel_content
        })

    # Generate HTML
    print(f"\nGenerating HTML...")
    generate_html(papers_data, output_path)
    print(f"\nDone! Open {output_path} in your browser.")


if __name__ == '__main__':
    main()
