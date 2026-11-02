"""A small sealed job pack for tests: the questionnaire runner's shape with stand-in content.

The real job's prompts and mappings live in its private pack, never in this tree.
"""

import json
from pathlib import Path

from modules.jobs.packs.seal import seal_pack

JOB = "test-questionnaire"
SKILL = "surfsense-job-test-questionnaire"
QUESTIONS_SHEET = "Questions"


def write_questionnaire_pack(folder: Path, *, access: str = "paid") -> Path:
    """A sealed pack in `folder` with one workbook-rows job and its skill."""
    files = {
        "LICENSE.md": "Test pack.",
        f"jobs/{JOB}/prompts/system.md": "Answer with one of $answers.",
        f"jobs/{JOB}/prompts/question.md": "$passages\n\nQuestion: $question",
        f"jobs/{JOB}/prompts/repair.md": "$problem",
        f"jobs/{JOB}/job.json": json.dumps(
            {
                "answers": [
                    {"answer": "Yes", "needs_quote": True},
                    {"answer": "No", "needs_quote": True},
                    {
                        "answer": "N/A",
                        "needs_quote": True,
                        "cell_values": ["N/A", "NA"],
                    },
                    {"answer": "Needs review", "needs_quote": False, "fallback": True},
                ],
                "layout": {
                    "question": ["question"],
                    "answer": ["answer"],
                    "comment": ["comments"],
                },
                "prompts": {
                    "system": "prompts/system.md",
                    "question": "prompts/question.md",
                    "repair": "prompts/repair.md",
                },
                "templates": {
                    "comment": {
                        "Needs review": "Needs review: $comment",
                        "*": '$comment "$quote"',
                    },
                    "evidence": "$where",
                },
                "sheets": {
                    "answers": "SurfSense answers",
                    "exceptions": "SurfSense exceptions",
                },
            }
        ),
        f"skills/{SKILL}/SKILL.md": f"---\nname: {SKILL}\ndescription: Test.\n---\nRun it.",
    }
    for relative, text in files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    manifest = {
        "schema": "surfsense-job-pack/1",
        "id": "test-jobs",
        "version": "1.0.0",
        "name": "Test jobs",
        "publisher": "Tests",
        "description": "A test pack.",
        "access": access,
        "license_file": "LICENSE.md",
        "jobs": [
            {
                "key": JOB,
                "name": "Test questionnaire",
                "description": "Fill in a test questionnaire.",
                "runner": "workbook-rows/1",
                "config": f"jobs/{JOB}/job.json",
                "skill": f"skills/{SKILL}",
            }
        ],
        "files": {"LICENSE.md": "0" * 64},
    }
    (folder / "job-pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    seal_pack(folder)
    return folder
