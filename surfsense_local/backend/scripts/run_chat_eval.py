"""Score the chat's answers on a curated model, so a change is measured before it ships.

Local runs ask a llama-server started the way the app starts it, normally the
dev app's own, whose port is in the dev console. Featherless reads its key from
FEATHERLESS_API_KEY. The judge is a frontier model on OpenRouter, which reads
its key from OPENROUTER_API_KEY and writes its verdicts and an insights report
beside the run it reviews.

    uv run scripts/run_chat_eval.py run --model qwen3-4b --target local \
        --base-url http://127.0.0.1:PORT --out ../../.progress/eval/baseline/qwen3-4b-local.jsonl
    uv run scripts/run_chat_eval.py judge <result file> --judge-model <OpenRouter id>
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
from chat_eval.judge.openrouter import api_key, complete
from chat_eval.judge.report import report_request
from chat_eval.judge.verdict import VERDICT_FORMAT, verdict_record, verdict_request
from chat_eval.model import eval_model
from chat_eval.request import conversation
from chat_eval.score import score
from chat_eval.send import ask, featherless, local
from chat_eval.summary import read_records, summarize, verdicts_file

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
            sent = target.shape(await conversation(case, model.tier))
            for repeat in range(args.repeats):
                reply = await ask(target, sent, model.sampling)
                record = {
                    "case": case.id,
                    "repeat": repeat,
                    "model": model.id,
                    "target": target.name,
                    "served_as": target.model,
                    "tier": model.tier.value,
                    "runtime": target.runtime,
                    # What the model saw and thought, which the judge reads.
                    "messages": [asdict(message) for message in sent],
                    "reasoning": reply.reasoning,
                    "answer": reply.content,
                    "finish_reason": reply.finish_reason,
                    "usage": reply.usage,
                    "timings": reply.timings,
                    "answer_key": {"supporting": case.supporting, "facts": case.facts},
                    "score": asdict(score(case, reply.content, reply.finish_reason)),
                }
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                out.flush()
                print(
                    f"{case.id} #{repeat}: {reply.finish_reason}, {len(reply.content)} chars"
                )
    print(summarize([args.out]))


async def judge(args: argparse.Namespace) -> None:
    key = api_key()
    results = read_records(args.results)
    if not results or "messages" not in results[0]:
        raise ValueError(f"{args.results} has no messages to judge: run it again")
    verdicts = []
    with verdicts_file(args.results).open("w", encoding="utf-8") as out:
        # ponytail: one reply at a time; judge in parallel once a run takes too long.
        for record in results:
            reply = await complete(
                args.judge_model, verdict_request(record), key, VERDICT_FORMAT
            )
            kept = verdict_record(record, reply, args.judge_model)
            out.write(json.dumps(kept, ensure_ascii=False) + "\n")
            out.flush()
            verdicts.append(kept)
            state = "judged" if "verdict" in kept else "verdict did not fit the schema"
            print(f"{record['case']} #{record['repeat']}: {state}")
    insights = args.results.with_suffix(".insights.md")
    report = await complete(args.judge_model, report_request(results, verdicts), key)
    insights.write_text(report, encoding="utf-8")
    print(summarize([args.results]))
    print(f"insights: {insights}")


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

    judge_command = commands.add_parser(
        "judge", help="have a frontier model review a run and report what to change"
    )
    judge_command.add_argument("results", type=Path, help="a file `run` wrote")
    judge_command.add_argument(
        "--judge-model", required=True, help="an OpenRouter model id"
    )

    summary_command = commands.add_parser("summary", help="compare result files")
    summary_command.add_argument("files", type=Path, nargs="+")

    args = parser.parse_args()
    if args.command == "summary":
        print(summarize(args.files))
        return 0
    if args.command == "run" and args.target == "local" and not args.base_url:
        parser.error("--target local needs --base-url")
    # History is built as stored chat rows, which map only once every model does.
    import_models()
    try:
        asyncio.run(run(args) if args.command == "run" else judge(args))
    except (ValueError, RuntimeError, httpx.HTTPError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
