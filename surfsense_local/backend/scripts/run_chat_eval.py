"""Score the chat's answers on a curated model, so a change is measured before it ships.

Local runs ask a llama-server started the way the app starts it, normally the
dev app's own, whose port is in the dev console. Featherless reads its key from
FEATHERLESS_API_KEY.

    uv run scripts/run_chat_eval.py run --model qwen3-4b --target local \
        --base-url http://127.0.0.1:PORT --out ../../.progress/eval/baseline/qwen3-4b-local.jsonl
    uv run scripts/run_chat_eval.py summary <result files>

The design is docs/proposals/chat-eval.md.
"""

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

import httpx
from chat_eval.cases import load_cases
from chat_eval.model import eval_model
from chat_eval.request import conversation
from chat_eval.score import score
from chat_eval.send import ask, featherless, local
from chat_eval.summary import summarize

from shared.db import import_models


async def run(args: argparse.Namespace) -> None:
    model = eval_model(args.model)
    if args.target == "local":
        target = await local(args.base_url, model)
    else:
        target = featherless(model)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as out:
        for case in load_cases():
            messages = await conversation(case, model.tier)
            for repeat in range(args.repeats):
                reply = await ask(target, messages, model.sampling)
                record = {
                    "case": case.id,
                    "repeat": repeat,
                    "model": model.id,
                    "target": target.name,
                    "served_as": target.model,
                    "tier": model.tier.value,
                    "runtime": target.runtime,
                    "answer": reply.content,
                    "reasoning_chars": reply.reasoning_chars,
                    "finish_reason": reply.finish_reason,
                    "usage": reply.usage,
                    "timings": reply.timings,
                    "score": asdict(score(case, reply.content, reply.finish_reason)),
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                print(
                    f"{case.id} #{repeat}: {reply.finish_reason}, {len(reply.content)} chars"
                )
    print(summarize([args.out]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    run_command = commands.add_parser("run", help="answer every case and score it")
    run_command.add_argument("--model", required=True, help="a curated chat model id")
    run_command.add_argument(
        "--target", choices=("local", "featherless"), required=True
    )
    run_command.add_argument("--base-url", help="the llama-server, for --target local")
    run_command.add_argument(
        "--out", type=Path, required=True, help="one JSON line per reply"
    )
    run_command.add_argument(
        "--repeats", type=int, default=1, help="answers per case, since sampling varies"
    )

    summary_command = commands.add_parser("summary", help="compare result files")
    summary_command.add_argument("files", type=Path, nargs="+")

    args = parser.parse_args()
    if args.command == "summary":
        print(summarize(args.files))
        return 0
    if args.target == "local" and not args.base_url:
        parser.error("--target local needs --base-url")
    # History is built as stored chat rows, which map only once every model does.
    import_models()
    try:
        asyncio.run(run(args))
    except (ValueError, RuntimeError, httpx.HTTPError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
