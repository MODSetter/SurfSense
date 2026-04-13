#!/usr/bin/env python3
"""Deterministic pre-pass for sanctum architecture scanner.

Extracts structural metadata from a memory agent's sanctum architecture
that the LLM scanner can use instead of reading all files itself. Covers:
- SKILL.md content line count (non-blank, non-frontmatter)
- Template file inventory (which of the 6 standard templates exist)
- CREED template section inventory
- BOND template section inventory
- Capability reference frontmatter fields
- Init script parameter extraction (SKILL_NAME, TEMPLATE_FILES, EVOLVABLE)
- First-breath.md section inventory
- PULSE template presence and sections

Only runs for memory agents (agents with assets/ containing template files).
"""

# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


STANDARD_TEMPLATES = [
    "INDEX-template.md",
    "PERSONA-template.md",
    "CREED-template.md",
    "BOND-template.md",
    "MEMORY-template.md",
    "CAPABILITIES-template.md",
]

OPTIONAL_TEMPLATES = [
    "PULSE-template.md",
]

CREED_REQUIRED_SECTIONS = [
    "The Sacred Truth",
    "Mission",
    "Core Values",
    "Standing Orders",
    "Philosophy",
    "Boundaries",
    "Anti-Patterns",
    "Dominion",
]

FIRST_BREATH_CALIBRATION_SECTIONS = [
    "Save As You Go",
    "Pacing",
    "Chase What Catches",
    "Absorb Their Voice",
    "Show Your Work",
    "Hear the Silence",
    "The Territories",
    "Wrapping Up",
]

FIRST_BREATH_CONFIG_SECTIONS = [
    "Save As You Go",
    "Discovery",
    "Urgency",
    "Wrapping Up",
]


def count_content_lines(file_path: Path) -> int:
    """Count non-blank, non-frontmatter lines in a markdown file."""
    content = file_path.read_text()

    # Strip frontmatter
    stripped = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, count=1, flags=re.DOTALL)

    lines = [line for line in stripped.split("\n") if line.strip()]
    return len(lines)


def extract_h2_h3_sections(file_path: Path) -> list[str]:
    """Extract H2 and H3 headings from a markdown file."""
    sections = []
    if not file_path.exists():
        return sections
    for line in file_path.read_text().split("\n"):
        match = re.match(r"^#{2,3}\s+(.+)", line)
        if match:
            sections.append(match.group(1).strip())
    return sections


def parse_frontmatter(file_path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    meta = {}
    content = file_path.read_text()
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return meta
    for line in match.group(1).strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip("'\"")
    return meta


def extract_init_script_params(script_path: Path) -> dict:
    """Extract agent-specific configuration from init-sanctum.py."""
    params = {
        "exists": script_path.exists(),
        "skill_name": None,
        "template_files": [],
        "skill_only_files": [],
        "evolvable": None,
    }
    if not script_path.exists():
        return params

    content = script_path.read_text()

    # SKILL_NAME
    match = re.search(r'SKILL_NAME\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        params["skill_name"] = match.group(1)

    # TEMPLATE_FILES
    tmpl_match = re.search(
        r"TEMPLATE_FILES\s*=\s*\[(.*?)\]", content, re.DOTALL
    )
    if tmpl_match:
        params["template_files"] = re.findall(r'["\']([^"\']+)["\']', tmpl_match.group(1))

    # SKILL_ONLY_FILES
    only_match = re.search(
        r"SKILL_ONLY_FILES\s*=\s*\{(.*?)\}", content, re.DOTALL
    )
    if only_match:
        params["skill_only_files"] = re.findall(r'["\']([^"\']+)["\']', only_match.group(1))

    # EVOLVABLE
    ev_match = re.search(r"EVOLVABLE\s*=\s*(True|False)", content)
    if ev_match:
        params["evolvable"] = ev_match.group(1) == "True"

    return params


def check_section_present(sections: list[str], keyword: str) -> bool:
    """Check if any section heading contains the keyword (case-insensitive)."""
    keyword_lower = keyword.lower()
    return any(keyword_lower in s.lower() for s in sections)


def main():
    parser = argparse.ArgumentParser(
        description="Pre-pass for sanctum architecture scanner"
    )
    parser.add_argument("skill_path", help="Path to the agent skill directory")
    parser.add_argument(
        "-o", "--output", help="Output JSON file path (default: stdout)"
    )
    args = parser.parse_args()

    skill_path = Path(args.skill_path).resolve()
    if not skill_path.is_dir():
        print(f"Error: {skill_path} is not a directory", file=sys.stderr)
        sys.exit(2)

    assets_dir = skill_path / "assets"
    references_dir = skill_path / "references"
    scripts_dir = skill_path / "scripts"
    skill_md = skill_path / "SKILL.md"

    # Check if this is a memory agent (has template files in assets/)
    is_memory_agent = assets_dir.exists() and any(
        f.name.endswith("-template.md") for f in assets_dir.iterdir() if f.is_file()
    )

    if not is_memory_agent:
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "skill_path": str(skill_path),
            "is_memory_agent": False,
            "message": "Not a memory agent — no sanctum templates found in assets/",
        }
        output_json(result, args.output)
        return

    # SKILL.md analysis
    skill_analysis = {
        "exists": skill_md.exists(),
        "content_lines": count_content_lines(skill_md) if skill_md.exists() else 0,
        "sections": extract_h2_h3_sections(skill_md) if skill_md.exists() else [],
    }

    # Template inventory
    template_inventory = {}
    for tmpl in STANDARD_TEMPLATES:
        tmpl_path = assets_dir / tmpl
        template_inventory[tmpl] = {
            "exists": tmpl_path.exists(),
            "sections": extract_h2_h3_sections(tmpl_path) if tmpl_path.exists() else [],
            "content_lines": count_content_lines(tmpl_path) if tmpl_path.exists() else 0,
        }

    for tmpl in OPTIONAL_TEMPLATES:
        tmpl_path = assets_dir / tmpl
        template_inventory[tmpl] = {
            "exists": tmpl_path.exists(),
            "optional": True,
            "sections": extract_h2_h3_sections(tmpl_path) if tmpl_path.exists() else [],
            "content_lines": count_content_lines(tmpl_path) if tmpl_path.exists() else 0,
        }

    # CREED section check
    creed_path = assets_dir / "CREED-template.md"
    creed_sections = extract_h2_h3_sections(creed_path) if creed_path.exists() else []
    creed_check = {}
    for section in CREED_REQUIRED_SECTIONS:
        creed_check[section] = check_section_present(creed_sections, section)

    # First-breath analysis
    first_breath_path = references_dir / "first-breath.md"
    fb_sections = extract_h2_h3_sections(first_breath_path) if first_breath_path.exists() else []

    # Detect style: calibration has "Absorb Their Voice", configuration has "Discovery"
    is_calibration = check_section_present(fb_sections, "Absorb")
    is_configuration = check_section_present(fb_sections, "Discovery") and not is_calibration
    fb_style = "calibration" if is_calibration else ("configuration" if is_configuration else "unknown")

    expected_sections = (
        FIRST_BREATH_CALIBRATION_SECTIONS if is_calibration else FIRST_BREATH_CONFIG_SECTIONS
    )
    fb_check = {}
    for section in expected_sections:
        fb_check[section] = check_section_present(fb_sections, section)

    first_breath_analysis = {
        "exists": first_breath_path.exists(),
        "style": fb_style,
        "sections": fb_sections,
        "section_checks": fb_check,
    }

    # Capability frontmatter scan
    capabilities = []
    if references_dir.exists():
        for md_file in sorted(references_dir.glob("*.md")):
            if md_file.name == "first-breath.md":
                continue
            meta = parse_frontmatter(md_file)
            if meta:
                cap_info = {
                    "file": md_file.name,
                    "has_name": "name" in meta,
                    "has_code": "code" in meta,
                    "has_description": "description" in meta,
                    "sections": extract_h2_h3_sections(md_file),
                }
                # Check for memory agent patterns
                cap_info["has_memory_integration"] = check_section_present(
                    cap_info["sections"], "Memory Integration"
                )
                cap_info["has_after_session"] = check_section_present(
                    cap_info["sections"], "After"
                )
                cap_info["has_success"] = check_section_present(
                    cap_info["sections"], "Success"
                )
                capabilities.append(cap_info)

    # Init script analysis
    init_script_path = scripts_dir / "init-sanctum.py"
    init_params = extract_init_script_params(init_script_path)

    # Cross-check: init TEMPLATE_FILES vs actual templates
    actual_templates = [f.name for f in assets_dir.iterdir() if f.name.endswith("-template.md")] if assets_dir.exists() else []
    init_template_match = set(init_params.get("template_files", [])) == set(actual_templates) if init_params["exists"] else None

    # Cross-check: init SKILL_NAME vs folder name
    skill_name_match = init_params.get("skill_name") == skill_path.name if init_params["exists"] else None

    # Findings
    findings = []

    if skill_analysis["content_lines"] > 40:
        findings.append({
            "severity": "high",
            "file": "SKILL.md",
            "message": f"Bootloader has {skill_analysis['content_lines']} content lines (target: ~30, max: 40)",
        })

    for tmpl in STANDARD_TEMPLATES:
        if not template_inventory[tmpl]["exists"]:
            findings.append({
                "severity": "critical",
                "file": f"assets/{tmpl}",
                "message": f"Missing standard template: {tmpl}",
            })

    for section, present in creed_check.items():
        if not present:
            findings.append({
                "severity": "high",
                "file": "assets/CREED-template.md",
                "message": f"Missing required CREED section: {section}",
            })

    if not first_breath_analysis["exists"]:
        findings.append({
            "severity": "critical",
            "file": "references/first-breath.md",
            "message": "Missing first-breath.md",
        })
    else:
        for section, present in first_breath_analysis["section_checks"].items():
            if not present:
                findings.append({
                    "severity": "high",
                    "file": "references/first-breath.md",
                    "message": f"Missing First Breath section: {section}",
                })

    if not init_params["exists"]:
        findings.append({
            "severity": "critical",
            "file": "scripts/init-sanctum.py",
            "message": "Missing init-sanctum.py",
        })
    else:
        if skill_name_match is False:
            findings.append({
                "severity": "critical",
                "file": "scripts/init-sanctum.py",
                "message": f"SKILL_NAME mismatch: script has '{init_params['skill_name']}', folder is '{skill_path.name}'",
            })
        if init_template_match is False:
            findings.append({
                "severity": "high",
                "file": "scripts/init-sanctum.py",
                "message": "TEMPLATE_FILES does not match actual templates in assets/",
            })

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "skill_path": str(skill_path),
        "is_memory_agent": True,
        "skill_md": skill_analysis,
        "template_inventory": template_inventory,
        "creed_sections": creed_check,
        "first_breath": first_breath_analysis,
        "capabilities": capabilities,
        "init_script": init_params,
        "cross_checks": {
            "skill_name_match": skill_name_match,
            "template_files_match": init_template_match,
        },
        "findings": findings,
        "finding_count": len(findings),
        "critical_count": sum(1 for f in findings if f["severity"] == "critical"),
        "high_count": sum(1 for f in findings if f["severity"] == "high"),
    }

    output_json(result, args.output)


def output_json(data: dict, output_path: str | None) -> None:
    """Write JSON to file or stdout."""
    json_str = json.dumps(data, indent=2)
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json_str + "\n")
        print(f"Wrote: {output_path}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
