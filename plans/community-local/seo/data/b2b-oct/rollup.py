"""Roll the 21 Oct 2026 B2B pulls up into use cases and plays, beside the 29 Sep figures.

Backs ../../08-b2b-artifact-jobs.md. The mapping is use-cases.json; the pulls are the
overview-* and clickstream-* files beside it: one snapshot, Google US, data through
September 2026. The term classes and exclusions are the 29 Sep rules in ../b2b/rollup.py;
what is new is how a term's volume and trend are read (see "How this was counted" in 08).

    python rollup.py               # every table, as markdown
    python rollup.py --top 40      # the use-case table cut to 40 rows
    python rollup.py --json out.json
    python rollup.py --self-check
"""
import argparse
import importlib.util
import json
import pathlib
import re
import statistics
import sys

HERE = pathlib.Path(__file__).parent
sys.dont_write_bytecode = True  # importing parse and the 29 Sep rollup must not leave caches in plans/
sys.path.insert(0, str(HERE.parent))
import parse  # noqa: E402


def _load_sep():
    spec = importlib.util.spec_from_file_location("rollup_sep", HERE.parent / "b2b" / "rollup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sep = _load_sep()  # the 29 Sep rollup: kind(), PROFESSION, and its own run for the comparison

MONTHS = [f"{y}-{m:02d}" for y, m in [(2025, 10), (2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 10)]]
BEFORE, PRE_STEP, SPRING, SUMMER = MONTHS[0:4], MONTHS[3:8], MONTHS[5:8], MONTHS[8:12]
# Oct-Jan, Jan-May, Mar-May, Jun-Sep. RECENT is the folder's usual last three months.
RECENT = MONTHS[9:12]
AI = re.compile(r"\b(ai|llms?|gpt|chatgpt|claude|copilot|gemini|agents?|cowork|notebooklm|genai)\b")
MERGED_RATIO = 10   # Ads at 10x its clickstream or more has absorbed other phrases
STEP_RATIO = 3      # Ads Jul-Sep at 3x its Mar-May while clickstream moved under 1.5x
SPIKE_RATIO = 1.5   # a non-AI term above 1.5x its Mar-May needs clickstream to confirm it


def by_month(info):
    raw = info.get("monthly_searches") or {}
    if isinstance(raw, dict):
        return {k: v or 0 for k, v in raw.items()}
    return {f"{m['year']}-{m['month']:02d}": m.get("search_volume") or 0 for m in raw}


def med(series, months):
    vals = [series[m] for m in months if m in series]
    return statistics.median(vals) if vals else None


def load_ads(paths):
    out = {}
    for path in paths:
        for item in parse.load(path):
            kw, info, props, _serp, _intent = parse.pick(item)
            if kw and info.get("search_volume") is not None:
                out[kw] = {"reported": info.get("search_volume") or 0, "cpc": info.get("cpc") or 0,
                           "kd": props.get("keyword_difficulty"), "months": by_month(info)}
    return out


def load_clickstream(paths):
    out = {}
    for path in paths:
        for item in parse.load(path):
            months = by_month(item)
            if months:
                out[item["keyword"]] = months
    return out


def calibration(ads, cs):
    """Median Ads/clickstream over non-AI, non-profession terms both sources measure."""
    ratios = []
    for kw, d in ads.items():
        c = cs.get(kw)
        a, r = med(d["months"], RECENT), med(c, RECENT) if c else None
        if a and r and not AI.search(kw) and not sep.PROFESSION.search(kw):
            ratios.append(a / r)
    return statistics.median(ratios) if ratios else 1.34


def level(kw, d, c, ratio):
    """(volume to count, basis). See 08, 'How this was counted'."""
    months = d["months"]
    recent = min(med(months, RECENT) or 0, d["reported"] or 0)
    spring, summer = med(months, SPRING), med(months, SUMMER[1:])
    cs_now, cs_spring, cs_pre = (med(c, RECENT), med(c, SPRING), med(c, PRE_STEP)) if c else (None, None, None)
    cs_moved = cs_now / cs_spring if cs_now and cs_spring else None
    stepped = bool(spring and summer and summer >= STEP_RATIO * spring and (cs_moved is None or cs_moved < 1.5))
    if AI.search(kw) or stepped:
        pre = med(months, PRE_STEP) or 0
        if cs_now and cs_pre:
            return round(pre * cs_now / cs_pre), "pre-step x clickstream"
        return round(pre), "pre-step"
    if c and cs_now and recent >= MERGED_RATIO * cs_now:
        return round(cs_now * ratio), "merged"
    if spring and recent > SPIKE_RATIO * spring and not (cs_moved and cs_moved >= 1.3):
        return round(spring), "capped"
    return round(recent), "ads"


def cs_series(c):
    return [c.get(m, 0) for m in MONTHS] if c else None


def panel_drift(cs):
    ratios = []
    for c in cs.values():
        b = sum(c.get(m, 0) for m in BEFORE)
        if b >= 4 * 100:
            ratios.append(sum(c.get(m, 0) for m in SUMMER) / b)
    return statistics.median(ratios) if ratios else 1.0


def trend(members, cs, drift):
    """Clickstream Jun-Sep over Oct-Jan, summed over members, net of the panel's drift.
    None when the members' Oct-Jan clickstream is under 400 searches in all."""
    b = a = 0
    for kw, _d in members:
        c = cs.get(kw)
        if c:
            b += sum(c.get(m, 0) for m in BEFORE)
            a += sum(c.get(m, 0) for m in SUMMER)
    return round((a / b / drift - 1) * 100) if b >= 400 else None


def signature(d):
    return d["cpc"], tuple(sorted(d["months"].items()))


def dedupe(pairs):
    seen, out = set(), []
    for kw, d in pairs:
        if signature(d) not in seen:
            seen.add(signature(d))
            out.append((kw, d))
    return out


def summarise(members, cs, drift):
    vol = sum(d["vol"] for _kw, d in members)
    value = sum(d["vol"] * d["cpc"] for _kw, d in members)
    kds = [d["kd"] for _kw, d in members if d["kd"] is not None]
    clicks = sum(med(cs[kw], RECENT) or 0 for kw, _d in members if kw in cs)
    return {"n": len(members), "vol": vol, "value": round(value), "clicks": round(clicks),
            "cpc": round(value / vol, 2) if vol else 0.0,
            "kd": statistics.median(kds) if kds else None, "trend": trend(members, cs, drift) if members else None}


def kind(kw, config):
    """A judged label in use-cases.json wins; otherwise the 29 Sep wording rules.
    'utility' (free-tool demand) and 'brand' (a vendor's name) are new in October."""
    return config.get("labels", {}).get(kw) or sep.kind(kw, set(config["software"]))


def classify(terms, ads, cs, config, ratio, notes):
    out = {"job": [], "software": [], "profession": [], "utility": [], "brand": []}
    for kw in terms:
        d = ads.get(kw)
        if not d:
            continue
        if kw in config["exclude"]:
            notes[kw] = (d["reported"], 0, config["exclude"][kw])
            continue
        vol, basis = level(kw, d, cs.get(kw), ratio)
        if not vol:
            continue
        if basis != "ads":
            notes[kw] = (d["reported"], vol, basis)
        out[kind(kw, config)].append((kw, dict(d, vol=vol, basis=basis)))
    return out


def play_of_profession(kw, plays):
    for play, pattern in plays.items():
        if pattern and re.search(pattern, kw):
            return play
    return "Other"


def rollup(ads, cs, config, ratio, drift):
    cases, notes, professions = [], {}, []
    for name, spec in config["cases"].items():
        parts = classify(spec["terms"], ads, cs, config, ratio, notes)
        professions += parts["profession"]
        job, software = dedupe(parts["job"]), dedupe(parts["software"])
        utility, brand = dedupe(parts["utility"]), dedupe(parts["brand"])
        top = sorted(job, key=lambda m: -m[1]["vol"] * max(m[1]["cpc"], 0.5))[:3]
        cases.append({"name": name, "play": spec["play"], "new": bool(spec.get("new")),
                      "job": summarise(job, cs, drift), "software": summarise(software, cs, drift),
                      "utility": summarise(utility, cs, drift), "brand": summarise(brand, cs, drift),
                      "top": [(kw, d["vol"], d["cpc"]) for kw, d in top], "members": job, "software_members": software,
                      "utility_members": utility, "brand_members": brand})
    watch = classify(config["professions"], ads, cs, config, ratio, notes)
    professions += watch["profession"] + watch["job"]
    plays = {}
    for play in list(config["plays"]) + ["Other"]:
        mine = [c for c in cases if c["play"] == play]
        prof = dedupe([m for m in professions if play_of_profession(m[0], config["plays"]) == play])
        plays[play] = {"cases": len(mine), "new": sum(c["new"] for c in mine),
                       "job": summarise(dedupe([m for c in mine for m in c["members"]]), cs, drift),
                       "software_value": summarise(dedupe([m for c in mine for m in c["software_members"]]), cs, drift)["value"],
                       "utility": summarise(dedupe([m for c in mine for m in c["utility_members"]]), cs, drift),
                       "brand": summarise(dedupe([m for c in mine for m in c["brand_members"]]), cs, drift),
                       "profession": summarise(prof, cs, drift), "profession_top": sorted(prof, key=lambda m: -m[1]["vol"])[:3]}
    cases.sort(key=lambda c: -c["job"]["value"])
    return cases, plays, notes


def raw_change(members, cs):
    """Clickstream Jun-Sep over Oct-Jan for the members, before the panel's drift is netted out."""
    b = sum(cs[kw].get(m, 0) for kw, _d in members if kw in cs for m in BEFORE)
    a = sum(cs[kw].get(m, 0) for kw, _d in members if kw in cs for m in SUMMER)
    return round((a / b - 1) * 100) if b >= 400 else None


def cores(ads, cs, config, ratio, drift):
    """The narrowed term sets 08's verdicts rest on, counted by the same rules as the cases.
    Every listed term counts unless it is excluded; a core is judged to be job demand as a whole."""
    out = []
    for name, spec in config.get("cores", {}).items():
        members = []
        for kw in spec["terms"]:
            d = ads.get(kw)
            if d and kw not in config["exclude"]:
                vol, basis = level(kw, d, cs.get(kw), ratio)
                if vol:
                    members.append((kw, dict(d, vol=vol, basis=basis)))
        members = dedupe(members)
        top = sorted(members, key=lambda m: -m[1]["vol"] * m[1]["cpc"])[:3]
        out.append({"name": name, "bet": spec.get("bet"), "job": summarise(members, cs, drift),
                    "raw": raw_change(members, cs), "top": [(kw, d["vol"], d["cpc"]) for kw, d in top]})
    return out


def september(config_terms_only=False):
    """The 29 Sep rollup, run on its own pulls, keyed by use-case and play name."""
    folder = HERE.parent / "b2b"
    config = json.loads((folder / "use-cases.json").read_text(encoding="utf-8"))
    by_kw = sep.load_ads(sorted(folder.glob("overview-*.json.gz")) + sorted(folder.glob("suggestions-*.json.gz")))
    clicks = sep.load_clickstream(sorted(folder.glob("clickstream-*.json*")))
    cases, plays, _notes = sep.rollup(by_kw, clicks, config, sep.calibration(by_kw, clicks))
    return {c["name"]: c["job"] for c in cases}, {p: v["job"] for p, v in plays.items()}


def fmt(v, suffix=""):
    return "-" if v is None else f"{v}{suffix}"


def render(cases, plays, notes, ads, cs, config, ratio, drift, top, sep_cases, sep_plays):
    measured = sum(1 for d in ads.values() if d["reported"])
    print(f"<!-- {measured} terms with Ads data, {len(cs)} with clickstream, median Ads/clickstream "
          f"ratio {ratio:.2f}, clickstream panel drift Jun-Sep over Oct-Jan {drift:.2f} -->\n")
    print("## Use cases by job-term ad value\n")
    print("| # | use case | play | new | job searches | clickstream | job ad value | $/click | KD | trend | "
          "software $/click (searches) | biggest job terms |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, c in enumerate(cases[:top] if top else cases, 1):
        j, s = c["job"], c["software"]
        sw = f"{s['cpc']:.0f} ({s['vol']:,})" if s["vol"] else "-"
        terms = "; ".join(f"{kw} {v:,}/${p:.0f}" for kw, v, p in c["top"])
        print(f"| {i} | {c['name']} | {c['play']} | {'new' if c['new'] else ''} | {j['vol']:,} | {j['clicks']:,} | "
              f"{j['value']:,} | {j['cpc']:.2f} | {fmt(j['kd'])} | {fmt(j['trend'], '%')} | {sw} | {terms} |")
    print("\n## Plays\n")
    print("| play | use cases (new) | job searches | clickstream | job ad value | 29 Sep | $/click | trend | "
          "software ad value | profession searches | $/click | biggest profession terms |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for play, p in sorted(plays.items(), key=lambda kv: -kv[1]["job"]["value"]):
        j, f = p["job"], p["profession"]
        before = sep_plays.get(play, {}).get("value")
        names = "; ".join(f"{kw} {d['vol']:,}" for kw, d in p["profession_top"])
        print(f"| {play} | {p['cases']} ({p['new']}) | {j['vol']:,} | {j['clicks']:,} | {j['value']:,} | "
              f"{f'{before:,}' if before is not None else '-'} | {j['cpc']:.2f} | {fmt(j['trend'], '%')} | "
              f"{p['software_value']:,} | {f['vol']:,} | {f['cpc']:.2f} | {names or '-'} |")
    print("\n## Cores the verdicts rest on\n")
    print("| core | terms | searches | clickstream | ad value | $/click | KD | trend | raw clickstream | biggest terms |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for c in cores(ads, cs, config, ratio, drift):
        j = c["job"]
        terms = "; ".join(f"{kw} {v:,}/${p:.0f}" for kw, v, p in c["top"])
        print(f"| {c['name']} | {j['n']} | {j['vol']:,} | {j['clicks']:,} | {j['value']:,} | {j['cpc']:.2f} | "
              f"{fmt(j['kd'])} | {fmt(j['trend'], '%')} | {fmt(c['raw'], '%')} | {terms} |")
    print("\n## Beside the jobs: free-tool and vendor-name demand\n")
    print("| play | utility searches | utility clickstream | utility $/click | brand searches | brand clickstream | "
          "biggest brand terms |")
    print("|---|---|---|---|---|---|---|")
    for play, p in sorted(plays.items(), key=lambda kv: -(kv[1]["utility"]["clicks"] + kv[1]["brand"]["clicks"])):
        u, b = p["utility"], p["brand"]
        if u["n"] or b["n"]:
            brands = dedupe(sorted((m for c in cases if c["play"] == play for m in c["brand_members"]),
                                   key=lambda m: -m[1]["vol"]))[:3]
            names = "; ".join(f"{kw} {d['vol']:,}" for kw, d in brands)
            print(f"| {play} | {u['vol']:,} | {u['clicks']:,} | {u['cpc']:.2f} | {b['vol']:,} | {b['clicks']:,} | "
                  f"{names or '-'} |")
    print("\n## 29 Sep use cases, then and now\n")
    print("| use case | 29 Sep ad value | 21 Oct ad value | change | 21 Oct trend |")
    print("|---|---|---|---|---|")
    old = [c for c in cases if not c["new"] and c["name"] in sep_cases]
    for c in sorted(old, key=lambda c: -sep_cases[c["name"]]["value"])[:30]:
        b, a = sep_cases[c["name"]]["value"], c["job"]["value"]
        ch = f"{round((a / b - 1) * 100):+d}%" if b else "-"
        print(f"| {c['name']} | {b:,} | {a:,} | {ch} | {fmt(c['job']['trend'], '%')} |")
    print("\n## Counted differently from Google Ads\n")
    print("| term | Ads 12-month average | counted | basis |")
    print("|---|---|---|---|")
    for kw, (vol, counted, why) in sorted(notes.items(), key=lambda kv: -kv[1][0])[:60]:
        print(f"| {kw} | {vol:,} | {counted:,} | {why} |")
    print(f"\n{len(notes)} terms in all; `--json` lists every one.")
    for label, terms in config["watch"].items():
        print(f"\n## Watch: {label}\n")
        print("| term | Ads Jul-Sep | clickstream Jul-Sep | $/click | clickstream trend |")
        print("|---|---|---|---|---|")
        rows = [(kw, ads[kw]) for kw in terms if kw in ads]
        for kw, d in sorted(rows, key=lambda r: -(med(cs.get(r[0], {}), RECENT) or 0)):
            c = cs.get(kw)
            print(f"| {kw} | {fmt(med(d['months'], RECENT))} | {fmt(med(c, RECENT) if c else None)} | {d['cpc']:.2f} | "
                  f"{fmt(trend([(kw, d)], cs, drift), '%')} |")


def self_check():
    flat = {m: 100 for m in MONTHS}
    step = dict(flat, **{m: 1000 for m in SUMMER})
    cs_flat = {m: 80 for m in MONTHS}
    d = {"reported": 400, "cpc": 2.0, "kd": 10, "months": step}
    vol, basis = level("private ai", d, cs_flat, 1.34)
    assert basis == "pre-step x clickstream" and vol == 100, (vol, basis)
    vol, basis = level("nda template", d, cs_flat, 1.34)
    assert basis.startswith("pre-step"), "an Ads step clickstream does not show is a step in any term"
    vol, basis = level("sop template", {"reported": 300, "cpc": 1, "kd": 1, "months": dict(flat, **{"2026-08": 1000, "2026-09": 200})}, cs_flat, 1.34)
    assert (vol, basis) == (100, "capped"), (vol, basis)
    vol, basis = level("rfi in construction", {"reported": 3600, "cpc": 1, "kd": 1, "months": {m: 3600 for m in MONTHS}}, {m: 200 for m in MONTHS}, 1.34)
    assert (vol, basis) == (268, "merged"), (vol, basis)
    vol, basis = level("hecvat", {"reported": 2400, "cpc": 1, "kd": 1, "months": {m: 2400 for m in MONTHS}}, {m: 2500 for m in MONTHS}, 1.34)
    assert (vol, basis) == (2400, "ads")
    grow = {m: (100 if m in BEFORE else 150) for m in MONTHS}
    assert trend([("x", d)], {"x": grow}, 1.5) == 0, "panel drift is netted out"
    assert trend([("x", d)], {"x": grow}, 1.0) == 50
    print("self-check ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--top", type=int, default=0, help="rows in the use-case table (0 = all)")
    ap.add_argument("--json", help="write every use case, play and counted-differently term to this file")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    config = json.loads((HERE / "use-cases.json").read_text(encoding="utf-8"))
    ads = load_ads(sorted(HERE.glob("overview-*.json*")))
    cs = load_clickstream(sorted(HERE.glob("clickstream-*.json*")))
    ratio, drift = calibration(ads, cs), panel_drift(cs)
    cases, plays, notes = rollup(ads, cs, config, ratio, drift)
    sep_cases, sep_plays = september()
    render(cases, plays, notes, ads, cs, config, ratio, drift, args.top, sep_cases, sep_plays)
    if args.json:
        strip = lambda c: {k: v for k, v in c.items() if not k.endswith("members")}
        json.dump({"cases": [strip(c) for c in cases],
                   "plays": {k: {kk: vv for kk, vv in v.items() if kk != "profession_top"} for k, v in plays.items()},
                   "notes": {k: list(v) for k, v in notes.items()}, "ratio": ratio, "drift": drift},
                  open(args.json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
