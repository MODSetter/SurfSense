"""Roll the B2B keyword pulls in this folder up into artifact use cases and plays.

Backs ../../08-b2b-artifact-jobs.md. The mapping is use-cases.json; the pulls are
the overview-*, suggestions-* and clickstream-* files beside it.

    python rollup.py               # every table, as markdown
    python rollup.py --top 30      # the use-case table cut to 30 rows
    python rollup.py --self-check
"""
import argparse
import json
import pathlib
import re
import statistics
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import parse  # noqa: E402  load(), pick(), monthly(), effective_volume()

# Ads volume over clickstream volume. The median is under 2 (printed on every run);
# at 10x the Ads record has absorbed searches that are not the phrase.
MERGED_RATIO = 10
PROFESSION = re.compile(
    r"^(best )?(ai|chatgpt|claude|copilot|gemini)( tools?| agents?| assistants?)? (for|in) "
    r"(?!(excel|word|powerpoint|pdf|sheets|slides|docs|outlook)\b)"
    r"|^(legal ai|ai legal (assistant|software)|ai lawyer)")
SOFTWARE = re.compile(r"\b(software|platforms?|systems?|apps?|tools?|solutions?)$")


def load_ads(paths):
    by_kw = {}
    for path in paths:
        for item in parse.load(path):
            kw, info, props, _serp, _intent = parse.pick(item)
            if kw and info.get("search_volume"):
                by_kw[kw] = {"vol": parse.effective_volume(info)[1], "cpc": info.get("cpc") or 0,
                             "kd": props.get("keyword_difficulty"), "series": parse.monthly(info)[-12:]}
    return by_kw


def load_clickstream(paths):
    """Clickstream `recent`, the median of the last three months, as parse.py does for Ads."""
    out = {}
    for path in paths:
        for item in parse.load(path):
            series = parse.monthly(item)
            if series:
                out[item["keyword"]] = statistics.median(series[-3:])
    return out


def kind(kw, software_terms):
    if PROFESSION.search(kw):
        return "profession"
    if kw in software_terms or SOFTWARE.search(kw):
        return "software"
    return "job"


def calibration(by_kw, clicks):
    """Median Ads/clickstream ratio over the terms both sources measure."""
    ratios = [by_kw[kw]["vol"] / c for kw, c in clicks.items()
              if c and by_kw.get(kw, {}).get("vol") and not PROFESSION.search(kw)]
    return statistics.median(ratios)


def signature(d):
    """One Ads record reported under several spellings has the same CPC and series."""
    return d["cpc"], tuple(d["series"])


def clicks_by_record(by_kw, clicks):
    """Clickstream summed over every measured spelling of one Ads record."""
    out = {}
    for kw, c in clicks.items():
        if kw in by_kw:
            sig = signature(by_kw[kw])
            out[sig] = out.get(sig, 0) + c
    return out


def vet(kw, d, record_clicks, config, kind_, ratio):
    """(record to count or None, note). `ai for <profession>` records are families of
    variants by design, so the clickstream test skips them."""
    if kw in config["exclude"]:
        return None, config["exclude"][kw]
    c = record_clicks.get(signature(d))
    if kind_ != "profession" and c and d["vol"] >= MERGED_RATIO * c:
        # ponytail: assumes this term's panel bias is the median one; pulling
        # clickstream for every term and counting it directly is the upgrade.
        return dict(d, vol=round(c * ratio), merged=True), f"merged record: clickstream sees {c:,.0f}"
    return d, None


def dedupe(pairs):
    seen, out = set(), []
    for kw, d in pairs:
        sig = signature(d)
        if sig not in seen:
            seen.add(sig)
            out.append((kw, d))
    return out


def trend(members):
    """Jan-May 2026 over Sep-Dec 2025, as monthly means, each term despiked at 3x its
    median. June to August are left out: Ads stepped up then in unrelated AI terms
    and clickstream did not (see 08). A merged record's series is not the phrase's."""
    full = [d["series"] for _kw, d in members if len(d["series"]) == 12 and not d.get("merged")]
    despiked = [[min(v, 3 * (statistics.median(s) or 1)) for v in s] for s in full]
    before = sum(sum(s[0:4]) for s in despiked) / 4
    after = sum(sum(s[4:9]) for s in despiked) / 5
    return round((after / before - 1) * 100) if before else None


def summarise(members):
    vol = sum(d["vol"] for _kw, d in members)
    value = sum(d["vol"] * d["cpc"] for _kw, d in members)
    kds = [d["kd"] for _kw, d in members if d["kd"] is not None]
    return {"n": len(members), "vol": vol, "value": round(value),
            "cpc": round(value / vol, 2) if vol else 0.0,
            "kd": statistics.median(kds) if kds else None, "trend": trend(members) if members else None}


def classify(terms, by_kw, record_clicks, config, ratio, notes):
    """Split terms into job, software and profession members; record every drop or rescale in notes."""
    out = {"job": [], "software": [], "profession": []}
    for kw in terms:
        d = by_kw.get(kw)
        if not d or not d["vol"]:
            continue
        k = kind(kw, set(config["software"]))
        counted, why = vet(kw, d, record_clicks, config, k, ratio)
        if why:
            notes[kw] = (d["vol"], counted["vol"] if counted else 0, why)
        if counted:
            out[k].append((kw, counted))
    return out


def play_of_profession(kw, plays):
    for play, pattern in plays.items():
        if pattern and re.search(pattern, kw):
            return play
    return "Other"


def rollup(by_kw, clicks, config, ratio):
    cases, notes, professions = [], {}, []
    clicks = clicks_by_record(by_kw, clicks)
    for name, spec in config["cases"].items():
        parts = classify(spec["terms"], by_kw, clicks, config, ratio, notes)
        professions += parts["profession"]
        job, software = dedupe(parts["job"]), dedupe(parts["software"])
        top = sorted(job, key=lambda m: -m[1]["vol"] * max(m[1]["cpc"], 0.5))[:3]
        cases.append({"name": name, "play": spec["play"], "job": summarise(job), "software": summarise(software),
                      "top": [(kw, d["vol"], d["cpc"]) for kw, d in top], "members": job, "software_members": software})
    watch = classify(config["professions"], by_kw, clicks, config, ratio, notes)
    professions += watch["profession"] + watch["job"]
    plays = {}
    for play in list(config["plays"]) + ["Other"]:
        mine = [c for c in cases if c["play"] == play]
        prof = dedupe([m for m in professions if play_of_profession(m[0], config["plays"]) == play])
        plays[play] = {"cases": len(mine), "job": summarise(dedupe([m for c in mine for m in c["members"]])),
                       "software_value": summarise(dedupe([m for c in mine for m in c["software_members"]]))["value"],
                       "profession": summarise(prof), "profession_top": sorted(prof, key=lambda m: -m[1]["vol"])[:3]}
    cases.sort(key=lambda c: -c["job"]["value"])
    return cases, plays, notes


def fmt(v, suffix=""):
    return "-" if v is None else f"{v}{suffix}"


def render(cases, plays, notes, by_kw, clicks, config, ratio, top):
    print(f"<!-- {sum(1 for d in by_kw.values() if d['vol'])} terms with data, {len(clicks)} with clickstream, "
          f"median Ads/clickstream ratio {ratio:.2f} -->\n")
    print("## Use cases by job-term ad value\n")
    print("| # | use case | play | job searches | job ad value | $/click | KD | trend | software $/click (searches) | biggest job terms |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for i, c in enumerate(cases[:top] if top else cases, 1):
        j, s = c["job"], c["software"]
        sw = f"{s['cpc']:.0f} ({s['vol']:,})" if s["vol"] else "-"
        terms = "; ".join(f"{kw} {v:,}/${p:.0f}" for kw, v, p in c["top"])
        print(f"| {i} | {c['name']} | {c['play']} | {j['vol']:,} | {j['value']:,} | {j['cpc']:.2f} | "
              f"{fmt(j['kd'])} | {fmt(j['trend'], '%')} | {sw} | {terms} |")
    print("\n## Plays\n")
    print("| play | use cases | job searches | job ad value | $/click | trend | software ad value | profession searches | $/click | biggest profession terms |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for play, p in sorted(plays.items(), key=lambda kv: -kv[1]["job"]["value"]):
        j, f = p["job"], p["profession"]
        names = "; ".join(f"{kw} {d['vol']:,}" for kw, d in p["profession_top"])
        print(f"| {play} | {p['cases']} | {j['vol']:,} | {j['value']:,} | {j['cpc']:.2f} | {fmt(j['trend'], '%')} | "
              f"{p['software_value']:,} | {f['vol']:,} | {f['cpc']:.2f} | {names or '-'} |")
    print("\n## Excluded and rescaled terms\n")
    print("| term | Ads searches | counted | why |")
    print("|---|---|---|---|")
    for kw, (vol, counted, why) in sorted(notes.items(), key=lambda kv: -kv[1][0]):
        print(f"| {kw} | {vol:,} | {counted:,} | {why} |")
    for label, terms in config["watch"].items():
        print(f"\n## Watch: {label}\n")
        print("| term | Ads searches | clickstream | $/click | trend |")
        print("|---|---|---|---|---|")
        rows = [(kw, by_kw[kw]) for kw in terms if kw in by_kw and by_kw[kw]["vol"]]
        for kw, d in sorted(rows, key=lambda r: -r[1]["vol"]):
            c = clicks.get(kw)
            print(f"| {kw} | {d['vol']:,} | {f'{c:,.0f}' if c else '-'} | {d['cpc']:.2f} | {fmt(trend([(kw, d)]), '%')} |")


def self_check():
    flat = [100] * 12
    step = [100] * 9 + [1000] * 3
    merged = {"vol": 5000, "cpc": 5.0, "kd": 60, "series": [100] * 4 + [500] * 8}
    by_kw = {
        "regulatory impact assessments": merged,  # unmeasured spelling of the merged record, listed first
        "nda template": {"vol": 100, "cpc": 2.0, "kd": 10, "series": flat},
        "nda templates": {"vol": 100, "cpc": 2.0, "kd": 10, "series": flat},
        "ai for lawyers": {"vol": 900, "cpc": 30.0, "kd": 40, "series": step},
        "claude for excel": {"vol": 50, "cpc": 5.0, "kd": None, "series": flat},
        "contract management software": {"vol": 200, "cpc": 100.0, "kd": 50, "series": flat},
        "regulatory impact assessment": merged,
        "board book": {"vol": 900, "cpc": 1.0, "kd": 5, "series": flat},
    }
    clicks = {"regulatory impact assessment": 151, "ai for lawyers": 50, "nda template": 60}
    config = {"software": [], "exclude": {"board book": "a children's book format"},
              "plays": {"Legal": "lawyer|legal"}, "professions": [],
              "cases": {"Legal docs": {"play": "Legal", "terms": list(by_kw)}}}
    assert kind("legal ai tools", set()) == "profession"
    assert kind("claude for excel", set()) == "job", "an Office app is a format, not a profession"
    assert kind("contract management software", set()) == "software"
    assert trend([("x", {"series": step})]) == 0, "June to August must not move the trend"
    assert trend([("x", {"series": [100] * 4 + [200] * 8})]) == 100
    assert round(calibration(by_kw, clicks), 2) == 17.39, "profession families stay out of the calibration"
    cases, plays, notes = rollup(by_kw, clicks, config, ratio=1.65)
    job = cases[0]["job"]
    assert job["n"] == 3 and job["vol"] == 100 + 50 + 249, job  # two spellings of one record count once
    assert job["trend"] == 0, "a merged record's series must not move the trend"
    assert notes["regulatory impact assessment"][:2] == (5000, 249), notes
    assert notes["board book"] == (900, 0, "a children's book format")
    assert plays["Legal"]["profession"]["vol"] == 900, "a profession family is not a merged record"
    assert cases[0]["software"]["value"] == 20000
    print("self-check ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--top", type=int, default=0, help="rows in the use-case table (0 = all)")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    config = json.loads((HERE / "use-cases.json").read_text(encoding="utf-8"))
    by_kw = load_ads(sorted(HERE.glob("overview-*.json.gz")) + sorted(HERE.glob("suggestions-*.json.gz")))
    clicks = load_clickstream(sorted(HERE.glob("clickstream-*.json*")))
    ratio = calibration(by_kw, clicks)
    render(*rollup(by_kw, clicks, config, ratio), by_kw, clicks, config, ratio, args.top)


if __name__ == "__main__":
    main()
