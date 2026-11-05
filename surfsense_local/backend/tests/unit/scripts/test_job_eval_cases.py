"""The job eval's cases: each gold cell named as the runner names its cells, so it is asked and
scored."""

import json

import pytest
from job_eval.cases import load_cases

pytestmark = pytest.mark.unit


def test_a_gold_cell_is_named_as_the_runner_names_it(tmp_path):
    """A gold " b2" is B2, the cell the workbook's layout gives: read as written, its row would
    never be asked and would score as unreached."""
    folder = tmp_path / "cases" / "wisp"
    folder.mkdir(parents=True)
    case = {
        "id": "wisp",
        "title": "A security questionnaire",
        "job": "questionnaire",
        "workbook": "questionnaire.xlsx",
        "sources": ["policy.md"],
        "gold": "gold.json",
    }
    gold = {
        "rows": [
            {
                "sheet": "Security",
                "cell": " b2",
                "question": "Is customer data encrypted at rest?",
                "answer": "Yes",
            }
        ]
    }
    (folder / "case.json").write_text(json.dumps(case), encoding="utf-8")
    (folder / "gold.json").write_text(json.dumps(gold), encoding="utf-8")

    [loaded] = load_cases(tmp_path)

    assert loaded.gold[0].cell == "B2"
    assert loaded.gold_at("security", "B2") is loaded.gold[0]
