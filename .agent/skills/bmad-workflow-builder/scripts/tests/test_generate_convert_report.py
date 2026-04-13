#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""Tests for generate-convert-report.py."""

from __future__ import annotations

import json
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

# Load the script as a module
_script_path = Path(__file__).resolve().parent.parent / 'generate-convert-report.py'
_spec = spec_from_file_location('generate_convert_report', _script_path)
_mod = module_from_spec(_spec)
_spec.loader.exec_module(_mod)

measure_skill = _mod.measure_skill
calculate_reductions = _mod.calculate_reductions
build_report_data = _mod.build_report_data
generate_html = _mod.generate_html


def test_measure_skill_single_file():
    """Measure a single .md file."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'SKILL.md'
        p.write_text('## Section One\n\nSome words here.\n\n## Section Two\n\nMore words.\n')
        result = measure_skill(p)
        assert result['lines'] == 7, f"Expected 7 lines, got {result['lines']}"
        assert result['sections'] == 2, f"Expected 2 sections, got {result['sections']}"
        assert result['files'] == 1
        assert result['estimated_tokens'] > 0
        assert result['words'] > 0
        assert result['chars'] > 0


def test_measure_skill_directory():
    """Measure a directory with multiple .md files."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        (td_path / 'SKILL.md').write_text('## Overview\n\nHello world.\n')
        refs = td_path / 'references'
        refs.mkdir()
        (refs / 'ref.md').write_text('## Reference\n\nSome reference content.\n')
        result = measure_skill(td_path)
        assert result['lines'] == 6, f"Expected 6 lines, got {result['lines']}"
        assert result['sections'] == 2
        assert result['files'] == 2


def test_measure_skill_with_non_md_files():
    """Non-.md files count toward file total but not line/word/section counts."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        (td_path / 'SKILL.md').write_text('## Overview\n\nHello.\n')
        scripts = td_path / 'scripts'
        scripts.mkdir()
        (scripts / 'run.py').write_text('print("hello")\n')
        result = measure_skill(td_path)
        assert result['files'] == 2, f"Expected 2 files, got {result['files']}"
        assert result['lines'] == 3, f"Expected 3 lines (only .md), got {result['lines']}"


def test_calculate_reductions():
    """Calculate reduction percentages."""
    original = {'lines': 800, 'words': 5000, 'chars': 30000, 'sections': 30, 'estimated_tokens': 6500}
    rebuilt = {'lines': 80, 'words': 500, 'chars': 3000, 'sections': 6, 'estimated_tokens': 650}
    r = calculate_reductions(original, rebuilt)
    assert r['lines'] == '90%'
    assert r['words'] == '90%'
    assert r['chars'] == '90%'
    assert r['sections'] == '80%'
    assert r['estimated_tokens'] == '90%'


def test_calculate_reductions_zero_original():
    """Handle zero values gracefully."""
    original = {'lines': 0, 'words': 100, 'chars': 500, 'sections': 0, 'estimated_tokens': 130}
    rebuilt = {'lines': 0, 'words': 50, 'chars': 250, 'sections': 0, 'estimated_tokens': 65}
    r = calculate_reductions(original, rebuilt)
    assert r['lines'] == 'N/A'
    assert r['words'] == '50%'
    assert r['sections'] == 'N/A'


def test_calculate_reductions_no_change():
    """No reduction yields 0%."""
    original = {'lines': 100, 'words': 500, 'chars': 3000, 'sections': 5, 'estimated_tokens': 650}
    r = calculate_reductions(original, original)
    assert r['lines'] == '0%'
    assert r['words'] == '0%'


def test_build_report_data():
    """Assemble report data with all fields."""
    analysis = {
        'skill_name': 'test-skill',
        'original_source': '/path/to/original',
        'cuts': [{'category': 'Bloat', 'description': 'Removed bloat', 'examples': ['x'], 'severity': 'high'}],
        'retained': [{'category': 'Core', 'description': 'Kept core'}],
        'verdict': 'Much better now.',
    }
    data = build_report_data(
        {'lines': 100, 'words': 500, 'chars': 3000, 'sections': 10, 'files': 1, 'estimated_tokens': 650},
        {'lines': 20, 'words': 100, 'chars': 600, 'sections': 3, 'files': 1, 'estimated_tokens': 130},
        analysis,
        {'lines': '80%', 'words': '80%', 'chars': '80%', 'sections': '70%', 'estimated_tokens': '80%'},
    )
    assert data['meta']['skill_name'] == 'test-skill'
    assert data['meta']['original_source'] == '/path/to/original'
    assert 'timestamp' in data['meta']
    assert data['metrics']['original']['lines'] == 100
    assert data['metrics']['rebuilt']['lines'] == 20
    assert data['reductions']['lines'] == '80%'
    assert len(data['cuts']) == 1
    assert data['cuts'][0]['category'] == 'Bloat'
    assert len(data['retained']) == 1
    assert data['verdict'] == 'Much better now.'


def test_build_report_data_missing_fields():
    """Handle analysis with missing optional fields."""
    analysis = {'skill_name': 'minimal'}
    data = build_report_data({}, {}, analysis, {})
    assert data['meta']['skill_name'] == 'minimal'
    assert data['cuts'] == []
    assert data['retained'] == []
    assert data['verdict'] == ''


def test_generate_html_structure():
    """Generated HTML is valid and contains key elements."""
    report_data = {
        'meta': {'skill_name': 'test-skill', 'original_source': 'http://example.com', 'timestamp': '2026-01-01T00:00:00Z'},
        'metrics': {
            'original': {'lines': 100, 'words': 500, 'chars': 3000, 'sections': 10, 'files': 1, 'estimated_tokens': 650},
            'rebuilt': {'lines': 20, 'words': 100, 'chars': 600, 'sections': 3, 'files': 1, 'estimated_tokens': 130},
        },
        'reductions': {'lines': '80%', 'words': '80%', 'chars': '80%', 'sections': '70%', 'estimated_tokens': '80%'},
        'cuts': [{'category': 'Waste', 'description': 'Pure waste', 'examples': ['ex1'], 'severity': 'high'}],
        'retained': [{'category': 'Core', 'description': 'Essential'}],
        'verdict': 'Dramatically improved.',
    }
    html = generate_html(report_data)
    assert '<!DOCTYPE html>' in html
    assert 'report-data' in html
    assert 'test-skill' in html
    assert 'BMad Method' in html
    assert 'Skill Conversion' in html
    assert '--convert' in html


def test_generate_html_escapes_data():
    """Verify data is embedded as JSON, not raw HTML."""
    report_data = {
        'meta': {'skill_name': '<script>alert("xss")</script>', 'original_source': '', 'timestamp': ''},
        'metrics': {'original': {}, 'rebuilt': {}},
        'reductions': {},
        'cuts': [],
        'retained': [],
        'verdict': '',
    }
    html = generate_html(report_data)
    # The skill name in the JSON should be escaped by json.dumps
    assert '<script>alert' not in html.split('application/json')[0]


def test_end_to_end():
    """Full pipeline: create files, measure, analyze, generate HTML."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)

        # Original skill — verbose
        orig_dir = td_path / 'original'
        orig_dir.mkdir()
        (orig_dir / 'SKILL.md').write_text(
            '## Section 1\n\n' + 'word ' * 500 + '\n\n'
            '## Section 2\n\nMore verbose content.\n\n'
            '## Section 3\n\nEven more.\n',
        )

        # Rebuilt skill — lean
        rebuilt_dir = td_path / 'rebuilt'
        rebuilt_dir.mkdir()
        (rebuilt_dir / 'SKILL.md').write_text('## Core\n\nLean and effective.\n')

        # Measure
        orig_m = measure_skill(orig_dir)
        rebuilt_m = measure_skill(rebuilt_dir)
        reductions = calculate_reductions(orig_m, rebuilt_m)

        assert orig_m['words'] > rebuilt_m['words']
        assert orig_m['sections'] > rebuilt_m['sections']

        # Analysis
        analysis = {
            'skill_name': 'e2e-test',
            'original_source': str(orig_dir),
            'cuts': [
                {'category': 'Bloat', 'description': 'Removed verbose filler', 'examples': ['500 repeated words'], 'severity': 'high'},
            ],
            'retained': [
                {'category': 'Core Intent', 'description': 'Essential behavioral instructions'},
            ],
            'verdict': 'Converted successfully.',
        }

        report_data = build_report_data(orig_m, rebuilt_m, analysis, reductions)
        html = generate_html(report_data)

        # Write and verify
        out = td_path / 'report.html'
        out.write_text(html, encoding='utf-8')
        assert out.exists()
        assert out.stat().st_size > 1000

        # Verify report data roundtrips
        data_file = td_path / 'report-data.json'
        data_file.write_text(json.dumps(report_data, indent=2), encoding='utf-8')
        loaded = json.loads(data_file.read_text(encoding='utf-8'))
        assert loaded['meta']['skill_name'] == 'e2e-test'
        assert len(loaded['cuts']) == 1
        assert int(reductions['words'].rstrip('%')) > 50


if __name__ == '__main__':
    tests = [name for name in sorted(dir()) if name.startswith('test_')]
    passed = 0
    failed = 0
    for name in tests:
        try:
            globals()[name]()
            print(f'  PASS  {name}')
            passed += 1
        except Exception as e:
            print(f'  FAIL  {name}: {e}')
            failed += 1
    print(f'\n{passed} passed, {failed} failed')
    sys.exit(1 if failed else 0)
