#!/usr/bin/env python3
"""Write digests/YYYY-MM-DD.txt: a readable view of each day's program for an agent to work from.
Each digest indexes every session by start time, then gives talk details for sessions scoring
at or above --min-score, then scored posters and evening events.

    python digest.py
    python digest.py --abstract-chars 800 --min-score 1
"""
import argparse, collections, glob, json, os

from scoring import clock, is_poster, load_interests, score_paper, score_session, surname

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--abstract-chars", type=int, default=500)
ap.add_argument("--min-score", type=float, help="default: min_score in interests.json")
ap.add_argument("--max-posters", type=int, default=60, help="posters listed per time slot")
a = ap.parse_args()

cfg, groups = load_interests()
floor = cfg.get("min_score", 2) if a.min_score is None else a.min_score
paths = sorted(glob.glob(os.path.join("program", "*.json")))
if not paths:
    raise SystemExit("No program files found. Run: python harvest.py")
os.makedirs("digests", exist_ok=True)
for path in paths:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    papers = collections.defaultdict(list)
    for p in data["papers"]:
        if not p["wd"]:
            papers[p["sid"]].append(p)
    slots, posters, events = collections.defaultdict(list), collections.defaultdict(list), []
    for s in data["sessions"]:
        if s["type"] == "Break":
            continue
        if s["type"] == "Event":
            events.append(s)
        elif is_poster(s):
            posters[s["start"]].append(s)
        else:
            slots[s["start"]].append((score_session(s, papers[s["sid"]], groups)[0], s))
    out = [f"PROGRAM DIGEST {os.path.basename(path)[:10]}; harvested {data['harvested']}; times are local", ""]
    out.append("== INDEX: every session by start time, highest keyword score first ==")
    out.append("Scores are only a hint. Judge titles yourself; keywords miss good sessions.")
    for start in sorted(slots):
        out.append(f"\n{clock(start)}")
        for score, s in sorted(slots[start], key=lambda x: -x[0]):
            out.append(f"  [{score:5.1f}] id {s['sid'].split('/')[1]} | {s['type']} | {s['room']} | {clock(s['start'])}-{clock(s['end'])} | {s['title']}")
    out.append("\n== DETAILS: sessions at or above the score floor ==")
    for start in sorted(slots):
        for score, s in sorted(slots[start], key=lambda x: -x[0]):
            if score < floor:
                continue
            out.append(f"\n--- {clock(start)} | id {s['sid'].split('/')[1]} | {s['room']} | {s['title']}")
            if s.get("desc"):
                out.append("Description: " + s["desc"][:a.abstract_chars])
            for p in sorted(papers[s["sid"]], key=lambda p: p["t"] or "99"):
                out.append(f"  {clock(p['t']) if p['t'] else 'TBA'} paper {p['pid']} | {p['title']} | {surname(p['by'])}")
                if p["abs"]:
                    out.append("     " + p["abs"][:a.abstract_chars])
    out.append("\n== POSTERS: best keyword matches per time slot ==")
    for start in sorted(posters):
        ranked = [(score_paper(p, groups)[0], s, p) for s in posters[start] for p in papers[s["sid"]]]
        ranked.sort(key=lambda x: -x[0])
        out.append(f"\n{clock(start)} | {posters[start][0]['room']} | {len(ranked)} posters in total")
        for score, s, p in ranked[:a.max_posters]:
            out.append(f"  [{score:4.1f}] paper {p['pid']} | {p['title']} | {surname(p['by'])} | {p['abs'][:a.abstract_chars // 2]}")
    out.append("\n== EVENTS ==")
    for s in sorted(events, key=lambda s: s["start"]):
        out.append(f"  {clock(s['start'])}-{clock(s['end'])} | id {s['sid'].split('/')[1]} | {s['room']} | {s['title']}")
    name = os.path.join("digests", os.path.basename(path)[:10] + ".txt")
    with open(name, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"Wrote {name} ({os.path.getsize(name) // 1024} KB)")
