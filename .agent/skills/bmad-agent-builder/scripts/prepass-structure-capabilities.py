#!/usr/bin/env python3
"""Deterministic pre-pass for agent structure and capabilities scanner.

Extracts structural metadata from a BMad agent skill that the LLM scanner
can use instead of reading all files itself. Covers:
- Frontmatter parsing and validation
- Section inventory (H2/H3 headers)
- Template artifact detection
- Agent name validation (kebab-case, must contain 'agent')
- Required agent sections (stateless vs memory agent bootloader detection)
- Memory path consistency checking
- Language/directness pattern grep
- On Exit / Exiting section detection (invalid)
- Capability file scanning in references/ directory
"""

# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pyyaml>=6.0",
# ]
# ///

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: pyyaml required. Run with: uv run prepass-structure-capabilities.py", file=sys.stderr)
    sys.exit(2)


# Template artifacts that should NOT appear in finalized skills
TEMPLATE_ARTIFACTS = [
    r'\{if-complex-workflow\}', r'\{/if-complex-workflow\}',
    r'\{if-simple-workflow\}', r'\{/if-simple-workflow\}',
    r'\{if-simple-utility\}', r'\{/if-simple-utility\}',
    r'\{if-module\}', r'\{/if-module\}',
    r'\{if-headless\}', r'\{/if-headless\}',
    r'\{if-autonomous\}', r'\{/if-autonomous\}',
    r'\{if-memory\}', r'\{/if-memory\}',
    r'\{if-memory-agent\}', r'\{/if-memory-agent\}',
    r'\{if-stateless-agent\}', r'\{/if-stateless-agent\}',
    r'\{if-evolvable\}', r'\{/if-evolvable\}',
    r'\{if-pulse\}', r'\{/if-pulse\}',
    r'\{displayName\}', r'\{skillName\}',
]
# Runtime variables that ARE expected (not artifacts)
RUNTIME_VARS = {
    '{user_name}', '{communication_language}', '{document_output_language}',
    '{project-root}', '{output_folder}', '{planning_artifacts}',
    '{headless_mode}',
}

# Directness anti-patterns
DIRECTNESS_PATTERNS = [
    (r'\byou should\b', 'Suggestive "you should" — use direct imperative'),
    (r'\bplease\b(?! note)', 'Polite "please" — use direct imperative'),
    (r'\bhandle appropriately\b', 'Ambiguous "handle appropriately" — specify how'),
    (r'\bwhen ready\b', 'Vague "when ready" — specify testable condition'),
]

# Invalid sections
INVALID_SECTIONS = [
    (r'^##\s+On\s+Exit\b', 'On Exit section found — no exit hooks exist in the system, this will never run'),
    (r'^##\s+Exiting\b', 'Exiting section found — no exit hooks exist in the system, this will never run'),
]


def parse_frontmatter(content: str) -> tuple[dict | None, list[dict]]:
    """Parse YAML frontmatter and validate."""
    findings = []
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not fm_match:
        findings.append({
            'file': 'SKILL.md', 'line': 1,
            'severity': 'critical', 'category': 'frontmatter',
            'issue': 'No YAML frontmatter found',
        })
        return None, findings

    try:
        fm = yaml.safe_load(fm_match.group(1))
    except yaml.YAMLError as e:
        findings.append({
            'file': 'SKILL.md', 'line': 1,
            'severity': 'critical', 'category': 'frontmatter',
            'issue': f'Invalid YAML frontmatter: {e}',
        })
        return None, findings

    if not isinstance(fm, dict):
        findings.append({
            'file': 'SKILL.md', 'line': 1,
            'severity': 'critical', 'category': 'frontmatter',
            'issue': 'Frontmatter is not a YAML mapping',
        })
        return None, findings

    # name check
    name = fm.get('name')
    if not name:
        findings.append({
            'file': 'SKILL.md', 'line': 1,
            'severity': 'critical', 'category': 'frontmatter',
            'issue': 'Missing "name" field in frontmatter',
        })
    elif not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
        findings.append({
            'file': 'SKILL.md', 'line': 1,
            'severity': 'high', 'category': 'frontmatter',
            'issue': f'Name "{name}" is not kebab-case',
        })
    elif 'agent' not in name.split('-'):
        findings.append({
            'file': 'SKILL.md', 'line': 1,
            'severity': 'medium', 'category': 'frontmatter',
            'issue': f'Name "{name}" should contain "agent" (e.g., agent-{{name}} or {{code}}-agent-{{name}})',
        })

    # description check
    desc = fm.get('description')
    if not desc:
        findings.append({
            'file': 'SKILL.md', 'line': 1,
            'severity': 'high', 'category': 'frontmatter',
            'issue': 'Missing "description" field in frontmatter',
        })
    elif 'Use when' not in desc and 'use when' not in desc:
        findings.append({
            'file': 'SKILL.md', 'line': 1,
            'severity': 'medium', 'category': 'frontmatter',
            'issue': 'Description missing "Use when..." trigger phrase',
        })

    # Extra fields check — only name and description allowed for agents
    allowed = {'name', 'description'}
    extra = set(fm.keys()) - allowed
    if extra:
        findings.append({
            'file': 'SKILL.md', 'line': 1,
            'severity': 'low', 'category': 'frontmatter',
            'issue': f'Extra frontmatter fields: {", ".join(sorted(extra))}',
        })

    return fm, findings


def extract_sections(content: str) -> list[dict]:
    """Extract all H2/H3 headers with line numbers."""
    sections = []
    for i, line in enumerate(content.split('\n'), 1):
        m = re.match(r'^(#{2,3})\s+(.+)$', line)
        if m:
            sections.append({
                'level': len(m.group(1)),
                'title': m.group(2).strip(),
                'line': i,
            })
    return sections


def detect_memory_agent(skill_path: Path, content: str) -> bool:
    """Detect if this is a memory agent bootloader (vs stateless agent).

    Memory agents have assets/ with sanctum template files and contain
    Three Laws / Sacred Truth in their SKILL.md.
    """
    assets_dir = skill_path / 'assets'
    has_templates = (
        assets_dir.exists()
        and any(f.name.endswith('-template.md') for f in assets_dir.iterdir() if f.is_file())
    )
    has_three_laws = 'First Law:' in content and 'Second Law:' in content
    has_sacred_truth = 'Sacred Truth' in content
    return has_templates or (has_three_laws and has_sacred_truth)


def check_required_sections(sections: list[dict], is_memory_agent: bool) -> list[dict]:
    """Check for required and invalid sections."""
    findings = []
    h2_titles = [s['title'] for s in sections if s['level'] == 2]

    if is_memory_agent:
        # Memory agent bootloaders have a different required structure
        required = ['The Three Laws', 'The Sacred Truth', 'On Activation']
        for req in required:
            if req not in h2_titles:
                findings.append({
                    'file': 'SKILL.md', 'line': 1,
                    'severity': 'high', 'category': 'sections',
                    'issue': f'Missing ## {req} section (required for memory agent bootloader)',
                })
    else:
        # Stateless agents use the traditional full structure
        required = ['Overview', 'Identity', 'Communication Style', 'Principles', 'On Activation']
        for req in required:
            if req not in h2_titles:
                findings.append({
                    'file': 'SKILL.md', 'line': 1,
                    'severity': 'high', 'category': 'sections',
                    'issue': f'Missing ## {req} section',
                })

    # Invalid sections (both types)
    for s in sections:
        if s['level'] == 2:
            for pattern, message in INVALID_SECTIONS:
                if re.match(pattern, f"## {s['title']}"):
                    findings.append({
                        'file': 'SKILL.md', 'line': s['line'],
                        'severity': 'high', 'category': 'invalid-section',
                        'issue': message,
                    })

    return findings


def find_template_artifacts(filepath: Path, rel_path: str) -> list[dict]:
    """Scan for orphaned template substitution artifacts."""
    findings = []
    content = filepath.read_text(encoding='utf-8')

    for pattern in TEMPLATE_ARTIFACTS:
        for m in re.finditer(pattern, content):
            matched = m.group()
            if matched in RUNTIME_VARS:
                continue
            line_num = content[:m.start()].count('\n') + 1
            findings.append({
                'file': rel_path, 'line': line_num,
                'severity': 'high', 'category': 'artifacts',
                'issue': f'Orphaned template artifact: {matched}',
                'fix': 'Resolve or remove this template conditional/placeholder',
            })

    return findings


def extract_memory_paths(skill_path: Path) -> tuple[list[str], list[dict]]:
    """Extract all memory path references across files and check consistency."""
    findings = []
    memory_paths = set()

    # Memory path patterns
    mem_pattern = re.compile(r'memory/[\w\-/]+(?:\.\w+)?')

    files_to_scan = []

    skill_md = skill_path / 'SKILL.md'
    if skill_md.exists():
        files_to_scan.append(('SKILL.md', skill_md))

    for subdir in ['prompts', 'resources', 'references']:
        d = skill_path / subdir
        if d.exists():
            for f in sorted(d.iterdir()):
                if f.is_file() and f.suffix in ('.md', '.json', '.yaml', '.yml'):
                    files_to_scan.append((f'{subdir}/{f.name}', f))

    for rel_path, filepath in files_to_scan:
        content = filepath.read_text(encoding='utf-8')
        for m in mem_pattern.finditer(content):
            memory_paths.add(m.group())

    sorted_paths = sorted(memory_paths)

    # Check for inconsistent formats
    prefixes = set()
    for p in sorted_paths:
        prefix = p.split('/')[0]
        prefixes.add(prefix)

    memory_prefixes = {p for p in prefixes if 'memory' in p.lower()}

    if len(memory_prefixes) > 1:
        findings.append({
            'file': 'multiple', 'line': 0,
            'severity': 'medium', 'category': 'memory-paths',
            'issue': f'Inconsistent memory path prefixes: {", ".join(sorted(memory_prefixes))}',
        })

    return sorted_paths, findings


def check_prompt_basics(skill_path: Path) -> tuple[list[dict], list[dict]]:
    """Check each prompt file for config header and progression conditions."""
    findings = []
    prompt_details = []
    skip_files = {'SKILL.md'}

    prompt_files = [f for f in sorted(skill_path.iterdir())
                    if f.is_file() and f.suffix == '.md' and f.name not in skip_files]

    # Also scan references/ for capability prompts (memory agents keep prompts here)
    refs_dir = skill_path / 'references'
    if refs_dir.exists():
        prompt_files.extend(
            f for f in sorted(refs_dir.iterdir())
            if f.is_file() and f.suffix == '.md'
        )

    if not prompt_files:
        return prompt_details, findings

    for f in prompt_files:
        content = f.read_text(encoding='utf-8')
        rel_path = f.name
        detail = {'file': f.name, 'has_config_header': False, 'has_progression': False}

        # Config header check
        if '{communication_language}' in content or '{document_output_language}' in content:
            detail['has_config_header'] = True
        else:
            findings.append({
                'file': rel_path, 'line': 1,
                'severity': 'medium', 'category': 'config-header',
                'issue': 'No config header with language variables found',
            })

        # Progression condition check
        lower = content.lower()
        prog_keywords = ['progress', 'advance', 'move to', 'next stage', 'when complete',
                         'proceed to', 'transition', 'completion criteria']
        if any(kw in lower for kw in prog_keywords):
            detail['has_progression'] = True
        else:
            findings.append({
                'file': rel_path, 'line': len(content.split('\n')),
                'severity': 'high', 'category': 'progression',
                'issue': 'No progression condition keywords found',
            })

        # Directness checks
        for pattern, message in DIRECTNESS_PATTERNS:
            for m in re.finditer(pattern, content, re.IGNORECASE):
                line_num = content[:m.start()].count('\n') + 1
                findings.append({
                    'file': rel_path, 'line': line_num,
                    'severity': 'low', 'category': 'language',
                    'issue': message,
                })

        # Template artifacts
        findings.extend(find_template_artifacts(f, rel_path))

        prompt_details.append(detail)

    return prompt_details, findings


def scan_structure_capabilities(skill_path: Path) -> dict:
    """Run all deterministic agent structure and capability checks."""
    all_findings = []

    # Read SKILL.md
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return {
            'scanner': 'structure-capabilities-prepass',
            'script': 'prepass-structure-capabilities.py',
            'version': '1.0.0',
            'skill_path': str(skill_path),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'fail',
            'issues': [{'file': 'SKILL.md', 'line': 1, 'severity': 'critical',
                         'category': 'missing-file', 'issue': 'SKILL.md does not exist'}],
            'summary': {'total_issues': 1, 'by_severity': {'critical': 1, 'high': 0, 'medium': 0, 'low': 0}},
        }

    skill_content = skill_md.read_text(encoding='utf-8')

    # Detect agent type
    is_memory_agent = detect_memory_agent(skill_path, skill_content)

    # Frontmatter
    frontmatter, fm_findings = parse_frontmatter(skill_content)
    all_findings.extend(fm_findings)

    # Sections
    sections = extract_sections(skill_content)
    section_findings = check_required_sections(sections, is_memory_agent)
    all_findings.extend(section_findings)

    # Template artifacts in SKILL.md
    all_findings.extend(find_template_artifacts(skill_md, 'SKILL.md'))

    # Directness checks in SKILL.md
    for pattern, message in DIRECTNESS_PATTERNS:
        for m in re.finditer(pattern, skill_content, re.IGNORECASE):
            line_num = skill_content[:m.start()].count('\n') + 1
            all_findings.append({
                'file': 'SKILL.md', 'line': line_num,
                'severity': 'low', 'category': 'language',
                'issue': message,
            })

    # Memory path consistency
    memory_paths, memory_findings = extract_memory_paths(skill_path)
    all_findings.extend(memory_findings)

    # Prompt basics
    prompt_details, prompt_findings = check_prompt_basics(skill_path)
    all_findings.extend(prompt_findings)

    # Build severity summary
    by_severity = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    for f in all_findings:
        sev = f['severity']
        if sev in by_severity:
            by_severity[sev] += 1

    status = 'pass'
    if by_severity['critical'] > 0:
        status = 'fail'
    elif by_severity['high'] > 0:
        status = 'warning'

    return {
        'scanner': 'structure-capabilities-prepass',
        'script': 'prepass-structure-capabilities.py',
        'version': '1.0.0',
        'skill_path': str(skill_path),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'metadata': {
            'frontmatter': frontmatter,
            'sections': sections,
            'is_memory_agent': is_memory_agent,
        },
        'prompt_details': prompt_details,
        'memory_paths': memory_paths,
        'issues': all_findings,
        'summary': {
            'total_issues': len(all_findings),
            'by_severity': by_severity,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Deterministic pre-pass for agent structure and capabilities scanning',
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

    result = scan_structure_capabilities(args.skill_path)
    output = json.dumps(result, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
        print(f"Results written to {args.output}", file=sys.stderr)
    else:
        print(output)

    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
