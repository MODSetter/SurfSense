"""A small sealed job pack for tests: the questionnaire runner's shape with stand-in content.

The real job's prompts and mappings live in its private pack, never in this tree. Test packs
are signed with a key made for tests, which the app trusts only while tests run.
"""

import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from modules.jobs.packs.manifest import MANIFEST, SIGNATURE
from modules.jobs.packs.seal import seal_pack
from modules.jobs.packs.signature import signed_payload

# Not a secret: a fixed key so a test pack's signature is the same every run.
TEST_PACK_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
TEST_PACK_PUBLIC_KEY_HEX = (
    TEST_PACK_KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
)

JOB = "test-questionnaire"
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
    folder: Path, *, access: str = "paid", checks: bool = False
) -> Path:
    """A sealed pack in `folder` with one workbook-rows job and its skill."""
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
                "entitlement": "JOB_TEST_QUESTIONNAIRE",
                "config": f"jobs/{JOB}/job.json",
                "skill": f"skills/{SKILL}",
            }
        ],
        "files": {"LICENSE.md": "0" * 64},
    }
    (folder / "job-pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    seal_pack(folder)
    sign_pack(folder)
    return folder


def sign_pack(folder: Path, key: Ed25519PrivateKey = TEST_PACK_KEY) -> None:
    """Sign a sealed pack as SurfSense's script signs a real one, here with `key`."""
    manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
    signature = key.sign(signed_payload(manifest))
    (folder / SIGNATURE).write_bytes(base64.b64encode(signature) + b"\n")
