#!/usr/bin/env python3
"""Deterministic pre-pass for prompt craft scanner.

Extracts metrics and flagged patterns from SKILL.md and prompt files
so the LLM scanner can work from compact data instead of reading raw files.

Covers:
- SKILL.md line count and section inventory
- Overview section size
- Inline data detection (tables, fenced code blocks)
- Defensive padding pattern grep
- Meta-explanation pattern grep
- Back-reference detection ("as described above")
- Config header and progression condition presence per prompt
- File-level token estimates (chars / 4 rough approximation)
"""

# /// script
# requires-python = ">=3.9"
# ///

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# Defensive padding / filler patterns
WASTE_PATTERNS = [
    (r'\b[Mm]ake sure (?:to|you)\b', 'defensive-padding', 'Defensive: "make sure to/you"'),
    (r"\b[Dd]on'?t forget (?:to|that)\b", 'defensive-padding', "Defensive: \"don't forget\""),
    (r'\b[Rr]emember (?:to|that)\b', 'defensive-padding', 'Defensive: "remember to/that"'),
    (r'\b[Bb]e sure to\b', 'defensive-padding', 'Defensive: "be sure to"'),
    (r'\b[Pp]lease ensure\b', 'defensive-padding', 'Defensive: "please ensure"'),
    (r'\b[Ii]t is important (?:to|that)\b', 'defensive-padding', 'Defensive: "it is important"'),
    (r'\b[Yy]ou are an AI\b', 'meta-explanation', 'Meta: "you are an AI"'),
    (r'\b[Aa]s a language model\b', 'meta-explanation', 'Meta: "as a language model"'),
    (r'\b[Aa]s an AI assistant\b', 'meta-explanation', 'Meta: "as an AI assistant"'),
    (r'\b[Tt]his (?:workflow|skill|process) is designed to\b', 'meta-explanation', 'Meta: "this workflow is designed to"'),
    (r'\b[Tt]he purpose of this (?:section|step) is\b', 'meta-explanation', 'Meta: "the purpose of this section is"'),
    (r"\b[Ll]et'?s (?:think about|begin|start)\b", 'filler', "Filler: \"let's think/begin\""),
    (r'\b[Nn]ow we(?:\'ll| will)\b', 'filler', "Filler: \"now we'll\""),
]

# Back-reference patterns (self-containment risk)
BACKREF_PATTERNS = [
    (r'\bas described above\b', 'Back-reference: "as described above"'),
    (r'\bper the overview\b', 'Back-reference: "per the overview"'),
    (r'\bas mentioned (?:above|in|earlier)\b', 'Back-reference: "as mentioned above/in/earlier"'),
    (r'\bsee (?:above|the overview)\b', 'Back-reference: "see above/the overview"'),
    (r'\brefer to (?:the )?(?:above|overview|SKILL)\b', 'Back-reference: "refer to above/overview"'),
]


def count_tables(content: str) -> tuple[int, int]:
    """Count markdown tables and their total lines."""
    table_count = 0
    table_lines = 0
    in_table = False
    for line in content.split('\n'):
        if '|' in line and re.match(r'^\s*\|', line):
            if not in_table:
                table_count += 1
                in_table = True
            table_lines += 1
        else:
            in_table = False
    return table_count, table_lines


def count_fenced_blocks(content: str) -> tuple[int, int]:
    """Count fenced code blocks and their total lines."""
    block_count = 0
    block_lines = 0
    in_block = False
    for line in content.split('\n'):
        if line.strip().startswith('```'):
            if in_block:
                in_block = False
            else:
                in_block = True
                block_count += 1
        elif in_block:
            block_lines += 1
    return block_count, block_lines


def extract_overview_size(content: str) -> int:
    """Count lines in the ## Overview section."""
    lines = content.split('\n')
    in_overview = False
    overview_lines = 0
    for line in lines:
        if re.match(r'^##\s+Overview\b', line):
            in_overview = True
            continue
        elif in_overview and re.match(r'^##\s', line):
            break
        elif in_overview:
            overview_lines += 1
    return overview_lines


def scan_file_patterns(filepath: Path, rel_path: str) -> dict:
    """Extract metrics and pattern matches from a single file."""
    content = filepath.read_text(encoding='utf-8')
    lines = content.split('\n')
    line_count = len(lines)

    # Token estimate (rough: chars / 4)
    token_estimate = len(content) // 4

    # Section inventory
    sections = []
    for i, line in enumerate(lines, 1):
        m = re.match(r'^(#{2,3})\s+(.+)$', line)
        if m:
            sections.append({'level': len(m.group(1)), 'title': m.group(2).strip(), 'line': i})

    # Tables and code blocks
    table_count, table_lines = count_tables(content)
    block_count, block_lines = count_fenced_blocks(content)

    # Pattern matches
    waste_matches = []
    for pattern, category, label in WASTE_PATTERNS:
        for m in re.finditer(pattern, content):
            line_num = content[:m.start()].count('\n') + 1
            waste_matches.append({
                'line': line_num,
                'category': category,
                'pattern': label,
                'context': lines[line_num - 1].strip()[:100],
            })

    backref_matches = []
    for pattern, label in BACKREF_PATTERNS:
        for m in re.finditer(pattern, content, re.IGNORECASE):
            line_num = content[:m.start()].count('\n') + 1
            backref_matches.append({
                'line': line_num,
                'pattern': label,
                'context': lines[line_num - 1].strip()[:100],
            })

    # Config header
    has_config_header = '{communication_language}' in content or '{document_output_language}' in content

    # Progression condition
    prog_keywords = ['progress', 'advance', 'move to', 'next stage',
                     'when complete', 'proceed to', 'transition', 'completion criteria']
    has_progression = any(kw in content.lower() for kw in prog_keywords)

    result = {
        'file': rel_path,
        'line_count': line_count,
        'token_estimate': token_estimate,
        'sections': sections,
        'table_count': table_count,
        'table_lines': table_lines,
        'fenced_block_count': block_count,
        'fenced_block_lines': block_lines,
        'waste_patterns': waste_matches,
        'back_references': backref_matches,
        'has_config_header': has_config_header,
        'has_progression': has_progression,
    }

    return result


def scan_prompt_metrics(skill_path: Path) -> dict:
    """Extract metrics from all prompt-relevant files."""
    files_data = []

    # SKILL.md
    skill_md = skill_path / 'SKILL.md'
    if skill_md.exists():
        data = scan_file_patterns(skill_md, 'SKILL.md')
        content = skill_md.read_text(encoding='utf-8')
        data['overview_lines'] = extract_overview_size(content)
        data['is_skill_md'] = True
        files_data.append(data)

    # Prompt files at skill root (non-SKILL.md .md files)
    for f in sorted(skill_path.iterdir()):
        if f.is_file() and f.suffix == '.md' and f.name != 'SKILL.md':
            data = scan_file_patterns(f, f.name)
            data['is_skill_md'] = False
            files_data.append(data)

    # Resources (just sizes, for progressive disclosure assessment)
    resources_dir = skill_path / 'resources'
    resource_sizes = {}
    if resources_dir.exists():
        for f in sorted(resources_dir.iterdir()):
            if f.is_file() and f.suffix in ('.md', '.json', '.yaml', '.yml'):
                content = f.read_text(encoding='utf-8')
                resource_sizes[f.name] = {
                    'lines': len(content.split('\n')),
                    'tokens': len(content) // 4,
                }

    # Aggregate stats
    total_waste = sum(len(f['waste_patterns']) for f in files_data)
    total_backrefs = sum(len(f['back_references']) for f in files_data)
    total_tokens = sum(f['token_estimate'] for f in files_data)
    prompts_with_config = sum(1 for f in files_data if not f.get('is_skill_md') and f['has_config_header'])
    prompts_with_progression = sum(1 for f in files_data if not f.get('is_skill_md') and f['has_progression'])
    total_prompts = sum(1 for f in files_data if not f.get('is_skill_md'))

    skill_md_data = next((f for f in files_data if f.get('is_skill_md')), None)

    return {
        'scanner': 'prompt-craft-prepass',
        'script': 'prepass-prompt-metrics.py',
        'version': '1.0.0',
        'skill_path': str(skill_path),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'status': 'info',
        'skill_md_summary': {
            'line_count': skill_md_data['line_count'] if skill_md_data else 0,
            'token_estimate': skill_md_data['token_estimate'] if skill_md_data else 0,
            'overview_lines': skill_md_data.get('overview_lines', 0) if skill_md_data else 0,
            'table_count': skill_md_data['table_count'] if skill_md_data else 0,
            'table_lines': skill_md_data['table_lines'] if skill_md_data else 0,
            'fenced_block_count': skill_md_data['fenced_block_count'] if skill_md_data else 0,
            'fenced_block_lines': skill_md_data['fenced_block_lines'] if skill_md_data else 0,
            'section_count': len(skill_md_data['sections']) if skill_md_data else 0,
        },
        'prompt_health': {
            'total_prompts': total_prompts,
            'prompts_with_config_header': prompts_with_config,
            'prompts_with_progression': prompts_with_progression,
        },
        'aggregate': {
            'total_files_scanned': len(files_data),
            'total_token_estimate': total_tokens,
            'total_waste_patterns': total_waste,
            'total_back_references': total_backrefs,
        },
        'resource_sizes': resource_sizes,
        'files': files_data,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Extract prompt craft metrics for LLM scanner pre-pass',
    )
    parser.add_argument(
        'skill_path',
        type=Path,
        help='Path to the skill directory to scan',
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='Write JSON output to file instead of stdout',
    )
    args = parser.parse_args()

    if not args.skill_path.is_dir():
        print(f"Error: {args.skill_path} is not a directory", file=sys.stderr)
        return 2

    result = scan_prompt_metrics(args.skill_path)
    output = json.dumps(result, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == '__main__':
    sys.exit(main())
