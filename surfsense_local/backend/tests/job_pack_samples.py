"""A small sealed job pack for tests: the questionnaire runner's shape with stand-in content.

The real job's prompts and mappings live in its private pack, never in this tree. Test packs
are signed with a key made for tests, which the app trusts only while tests run.
"""

import base64
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from modules.jobs.packs.manifest import MANIFEST, SIGNATURE
from modules.jobs.packs.seal import seal_pack, zip_pack
from modules.jobs.packs.signature import signed_payload

# Not a secret: a fixed key so a test pack's signature is the same every run.
TEST_PACK_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
TEST_PACK_PUBLIC_KEY_HEX = (
    TEST_PACK_KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
)

PACK_ID = "test-jobs"
JOB = "test-questionnaire"
# The test job's licence code; the samples' Business licence carries JOB_QUESTIONNAIRE instead.
ENTITLEMENT = "JOB_TEST_QUESTIONNAIRE"
SKILL = "surfsense-job-test-questionnaire"
QUESTIONS_SHEET = "Questions"


# With `checks`: the second check, a statement gate that suggests an N/A resting on a provider
# or a scope, and the firm setting that writes a provider N/A instead.
CHECKS = {
    "verify": {"prompt": "prompts/verify.md", "answers": ["Yes", "No", "N/A"]},
    "statement_gate": {
        "answers": ["No", "N/A"],
        "quote": r"\b(applies to|hosted by|run by)\b",
        "suggest": ["N/A"],
        "provider": r"\b(hosted by|run by)\b",
        "provider_setting": "provider_na",
    },
    "settings": [
        {
            "key": "provider_na",
            "label": "Treat provider-run controls as N/A",
            "description": "Answer N/A when a provider runs the control.",
            "default": False,
        }
    ],
}


def write_questionnaire_pack(
    folder: Path,
    *,
    access: str = "paid",
    checks: bool = False,
    version: str = "1.0.0",
    entitlement: str | None = ENTITLEMENT,
    other_jobs: Sequence[str] = (),
    signed_by: Sequence[Ed25519PrivateKey] = (TEST_PACK_KEY,),
    sig_lines: Sequence[bytes] | None = None,
) -> Path:
    """A sealed pack in `folder` with one workbook-rows job and its skill, signed by each key of
    `signed_by`, one line each; `sig_lines` writes those lines as its signature instead.
    `other_jobs` adds a job for each of those codes, with the same config and no skill."""
    files = {
        "LICENSE.md": "Test pack.",
        f"jobs/{JOB}/prompts/system.md": "Answer with one of $answers.",
        f"jobs/{JOB}/prompts/question.md": "$passages\n\nQuestion: $question",
        f"jobs/{JOB}/prompts/repair.md": "$problem",
        f"jobs/{JOB}/prompts/verify.md": "Check that the quotes are evidence for $answer.",
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
                **(CHECKS if checks else {}),
            }
        ),
        f"skills/{SKILL}/SKILL.md": f"---\nname: {SKILL}\ndescription: Test.\n---\nRun it.",
    }
    for relative, text in files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    job = {
        "key": JOB,
        "name": "Test questionnaire",
        "description": "Fill in a test questionnaire.",
        "runner": "workbook-rows/1",
        "config": f"jobs/{JOB}/job.json",
        "skill": f"skills/{SKILL}",
    }
    if entitlement is not None:
        job["entitlement"] = entitlement
    manifest = {
        "schema": "surfsense-job-pack/1",
        "id": PACK_ID,
        "version": version,
        "name": "Test jobs",
        "publisher": "Tests",
        "description": "A test pack.",
        "access": access,
        "license_file": "LICENSE.md",
        "jobs": [
            job,
            *(
                {
                    **{k: v for k, v in job.items() if k != "skill"},
                    "key": f"other-job-{n}",
                    "entitlement": code,
                }
                for n, code in enumerate(other_jobs, start=1)
            ),
        ],
        "files": {"LICENSE.md": "0" * 64},
    }
    (folder / "job-pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    seal_pack(folder)
    if sig_lines is None:
        sign_pack(folder, *signed_by)
    else:
        (folder / SIGNATURE).write_bytes(b"\n".join(sig_lines) + b"\n")
    return folder


def zipped_questionnaire_pack(folder: Path, **options: Any) -> bytes:
    """The pack `write_questionnaire_pack` writes in `folder`, zipped as it is published."""
    write_questionnaire_pack(folder, **options)
    return zip_pack(folder, folder.with_name(f"{folder.name}.zip")).read_bytes()


def sign_pack(folder: Path, *keys: Ed25519PrivateKey) -> None:
    """Sign a sealed pack as SurfSense's script signs a real one, one line per key: the test
    key when none is given."""
    manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    payload = signed_payload(manifest)
    lines = [base64.b64encode(key.sign(payload)) for key in keys or (TEST_PACK_KEY,)]
    (folder / SIGNATURE).write_bytes(b"\n".join(lines) + b"\n")


REDLINE_PACK_ID = "test-redline"
REDLINE_JOB = "test-redline"
REDLINE_ENTITLEMENT = "JOB_TEST_REDLINE"
REDLINE_SKILL = "surfsense-job-test-redline"
# Review points the test redline checks, by key and title.
REDLINE_POINTS = {
    "compelled-disclosure": "Compelled disclosure",
    "term": "Term",
}


def write_contract_pack(folder: Path, *, version: str = "1.0.0") -> Path:
    """A sealed, signed pack in `folder` with one word-clauses job, the redline's shape with
    stand-in prompts."""
    files = {
        "LICENSE.md": "Test pack.",
        f"jobs/{REDLINE_JOB}/prompts/system.md": "Review one point. Verdicts: $verdicts.",
        f"jobs/{REDLINE_JOB}/prompts/point.md": "$outline\n\n$passages\n\nPoint: $point",
        f"jobs/{REDLINE_JOB}/prompts/repair.md": "$problem",
        f"jobs/{REDLINE_JOB}/job.json": json.dumps(
            {
                "points": [
                    {"key": key, "title": title, "covers": title, "queries": [title]}
                    for key, title in REDLINE_POINTS.items()
                ],
                "prompts": {
                    "system": "prompts/system.md",
                    "point": "prompts/point.md",
                    "repair": "prompts/repair.md",
                },
                "settings": [
                    {
                        "key": "external_comments",
                        "label": "Explain each change to the other side",
                        "default": True,
                    }
                ],
            }
        ),
        f"skills/{REDLINE_SKILL}/SKILL.md": (
            f"---\nname: {REDLINE_SKILL}\ndescription: Test.\n---\nRun it."
        ),
    }
    for relative, text in files.items():
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    manifest = {
        "schema": "surfsense-job-pack/1",
        "id": REDLINE_PACK_ID,
        "version": version,
        "name": "Test redline",
        "publisher": "Tests",
        "description": "A test pack.",
        "access": "paid",
        "license_file": "LICENSE.md",
        "jobs": [
            {
                "key": REDLINE_JOB,
                "name": "Test redline",
                "description": "Review a test contract (.docx) against a playbook.",
                "runner": "word-clauses/1",
                "config": f"jobs/{REDLINE_JOB}/job.json",
                "skill": f"skills/{REDLINE_SKILL}",
                "entitlement": REDLINE_ENTITLEMENT,
            }
        ],
        "files": {"LICENSE.md": "0" * 64},
    }
    (folder / "job-pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    seal_pack(folder)
    sign_pack(folder)
    return folder
