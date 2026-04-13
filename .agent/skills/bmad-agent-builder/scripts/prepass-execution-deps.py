#!/usr/bin/env python3
"""Deterministic pre-pass for execution efficiency scanner (agent builder).

Extracts dependency graph data and execution patterns from a BMad agent skill
so the LLM scanner can evaluate efficiency from compact structured data.

Covers:
- Dependency graph from skill structure
- Circular dependency detection
- Transitive dependency redundancy
- Parallelizable stage groups (independent nodes)
- Sequential pattern detection in prompts (numbered Read/Grep/Glob steps)
- Subagent-from-subagent detection
- Loop patterns (read all, analyze each, for each file)
- Memory loading pattern detection (load all memory, read all memory, etc.)
- Multi-source operation detection
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


def detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Detect circular dependencies in a directed graph using DFS."""
    cycles = []
    visited = set()
    path = []
    path_set = set()

    def dfs(node: str) -> None:
        if node in path_set:
            cycle_start = path.index(node)
            cycles.append(path[cycle_start:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        path.append(node)
        path_set.add(node)
        for neighbor in graph.get(node, []):
            dfs(neighbor)
        path.pop()
        path_set.discard(node)

    for node in graph:
        dfs(node)

    return cycles


def find_transitive_redundancy(graph: dict[str, list[str]]) -> list[dict]:
    """Find cases where A declares dependency on C, but A->B->C already exists."""
    redundancies = []

    def get_transitive(node: str, visited: set | None = None) -> set[str]:
        if visited is None:
            visited = set()
        for dep in graph.get(node, []):
            if dep not in visited:
                visited.add(dep)
                get_transitive(dep, visited)
        return visited

    for node, direct_deps in graph.items():
        for dep in direct_deps:
            # Check if dep is reachable through other direct deps
            other_deps = [d for d in direct_deps if d != dep]
            for other in other_deps:
                transitive = get_transitive(other)
                if dep in transitive:
                    redundancies.append({
                        'node': node,
                        'redundant_dep': dep,
                        'already_via': other,
                        'issue': f'"{node}" declares "{dep}" as dependency, but already reachable via "{other}"',
                    })

    return redundancies


def find_parallel_groups(graph: dict[str, list[str]], all_nodes: set[str]) -> list[list[str]]:
    """Find groups of nodes that have no dependencies on each other (can run in parallel)."""
    independent_groups = []

    # Simple approach: find all nodes at each "level" of the DAG
    remaining = set(all_nodes)
    while remaining:
        # Nodes whose dependencies are all satisfied (not in remaining)
        ready = set()
        for node in remaining:
            deps = set(graph.get(node, []))
            if not deps & remaining:
                ready.add(node)
        if not ready:
            break  # Circular dependency, can't proceed
        if len(ready) > 1:
            independent_groups.append(sorted(ready))
        remaining -= ready

    return independent_groups


def scan_sequential_patterns(filepath: Path, rel_path: str) -> list[dict]:
    """Detect sequential operation patterns that could be parallel."""
    content = filepath.read_text(encoding='utf-8')
    patterns = []

    # Sequential numbered steps with Read/Grep/Glob
    tool_steps = re.findall(
        r'^\s*\d+\.\s+.*?\b(Read|Grep|Glob|read|grep|glob)\b.*$',
        content, re.MULTILINE
    )
    if len(tool_steps) >= 3:
        patterns.append({
            'file': rel_path,
            'type': 'sequential-tool-calls',
            'count': len(tool_steps),
            'issue': f'{len(tool_steps)} sequential tool call steps found — check if independent calls can be parallel',
        })

    # "Read all files" / "for each" loop patterns
    loop_patterns = [
        (r'[Rr]ead all (?:files|documents|prompts)', 'read-all'),
        (r'[Ff]or each (?:file|document|prompt|stage)', 'for-each-loop'),
        (r'[Aa]nalyze each', 'analyze-each'),
        (r'[Ss]can (?:through|all|each)', 'scan-all'),
        (r'[Rr]eview (?:all|each)', 'review-all'),
    ]
    for pattern, ptype in loop_patterns:
        matches = re.findall(pattern, content)
        if matches:
            patterns.append({
                'file': rel_path,
                'type': ptype,
                'count': len(matches),
                'issue': f'"{matches[0]}" pattern found — consider parallel subagent delegation',
            })

    # Memory loading patterns (agent-specific)
    memory_loading_patterns = [
        (r'[Ll]oad all (?:memory|memories)', 'load-all-memory'),
        (r'[Rr]ead all (?:memory|agent memory) (?:files|data)', 'read-all-memory'),
        (r'[Ll]oad (?:entire|full|complete) (?:memory|agent memory)', 'load-entire-memory'),
        (r'[Ll]oad all (?:context|state)', 'load-all-context'),
        (r'[Rr]ead (?:entire|full|complete) memory', 'read-entire-memory'),
    ]
    for pattern, ptype in memory_loading_patterns:
        matches = re.findall(pattern, content)
        if matches:
            patterns.append({
                'file': rel_path,
                'type': ptype,
                'count': len(matches),
                'issue': f'"{matches[0]}" pattern found — bulk memory loading is expensive, load specific paths',
            })

    # Multi-source operation detection (agent-specific)
    multi_source_patterns = [
        (r'[Rr]ead all\b', 'multi-source-read-all'),
        (r'[Aa]nalyze each\b', 'multi-source-analyze-each'),
        (r'[Ff]or each file\b', 'multi-source-for-each-file'),
    ]
    for pattern, ptype in multi_source_patterns:
        matches = re.findall(pattern, content)
        if matches:
            # Only add if not already captured by loop_patterns above
            existing_types = {p['type'] for p in patterns}
            if ptype not in existing_types:
                patterns.append({
                    'file': rel_path,
                    'type': ptype,
                    'count': len(matches),
                    'issue': f'"{matches[0]}" pattern found — multi-source operation may be parallelizable',
                })

    # Subagent spawning from subagent (impossible)
    if re.search(r'(?i)spawn.*subagent|launch.*subagent|create.*subagent', content):
        # Check if this file IS a subagent (quality-scan-* or report-* files at root)
        if re.match(r'(?:quality-scan-|report-)', rel_path):
            patterns.append({
                'file': rel_path,
                'type': 'subagent-chain-violation',
                'count': 1,
                'issue': 'Subagent file references spawning other subagents — subagents cannot spawn subagents',
            })

    return patterns


def scan_execution_deps(skill_path: Path) -> dict:
    """Run all deterministic execution efficiency checks."""
    # Build dependency graph from skill structure
    dep_graph: dict[str, list[str]] = {}
    prefer_after: dict[str, list[str]] = {}
    all_stages: set[str] = set()

    # Check for stage definitions in prompt files
    prompts_dir = skill_path / 'prompts'
    if prompts_dir.exists():
        for f in sorted(prompts_dir.iterdir()):
            if f.is_file() and f.suffix == '.md':
                all_stages.add(f.stem)

    # Cycle detection
    cycles = detect_cycles(dep_graph)

    # Transitive redundancy
    redundancies = find_transitive_redundancy(dep_graph)

    # Parallel groups
    parallel_groups = find_parallel_groups(dep_graph, all_stages)

    # Sequential pattern detection across all prompt and agent files
    sequential_patterns = []
    for scan_dir in ['prompts', 'agents']:
        d = skill_path / scan_dir
        if d.exists():
            for f in sorted(d.iterdir()):
                if f.is_file() and f.suffix == '.md':
                    patterns = scan_sequential_patterns(f, f'{scan_dir}/{f.name}')
                    sequential_patterns.extend(patterns)

    # Also scan SKILL.md
    skill_md = skill_path / 'SKILL.md'
    if skill_md.exists():
        sequential_patterns.extend(scan_sequential_patterns(skill_md, 'SKILL.md'))

    # Build issues from deterministic findings
    issues = []
    for cycle in cycles:
        issues.append({
            'severity': 'critical',
            'category': 'circular-dependency',
            'issue': f'Circular dependency detected: {" → ".join(cycle)}',
        })
    for r in redundancies:
        issues.append({
            'severity': 'medium',
            'category': 'dependency-bloat',
            'issue': r['issue'],
        })
    for p in sequential_patterns:
        if p['type'] == 'subagent-chain-violation':
            severity = 'critical'
        elif p['type'] in ('load-all-memory', 'read-all-memory', 'load-entire-memory',
                           'load-all-context', 'read-entire-memory'):
            severity = 'high'
        else:
            severity = 'medium'
        issues.append({
            'file': p['file'],
            'severity': severity,
            'category': p['type'],
            'issue': p['issue'],
        })

    by_severity = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    for issue in issues:
        sev = issue['severity']
        if sev in by_severity:
            by_severity[sev] += 1

    status = 'pass'
    if by_severity['critical'] > 0:
        status = 'fail'
    elif by_severity['high'] > 0 or by_severity['medium'] > 0:
        status = 'warning'

    return {
        'scanner': 'execution-efficiency-prepass',
        'script': 'prepass-execution-deps.py',
        'version': '1.0.0',
        'skill_path': str(skill_path),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'dependency_graph': {
            'stages': sorted(all_stages),
            'hard_dependencies': dep_graph,
            'soft_dependencies': prefer_after,
            'cycles': cycles,
            'transitive_redundancies': redundancies,
            'parallel_groups': parallel_groups,
        },
        'sequential_patterns': sequential_patterns,
        'issues': issues,
        'summary': {
            'total_issues': len(issues),
            'by_severity': by_severity,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Extract execution dependency graph and patterns for LLM scanner pre-pass (agent builder)',
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

    result = scan_execution_deps(args.skill_path)
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
