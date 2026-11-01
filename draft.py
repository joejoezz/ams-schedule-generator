#!/usr/bin/env python3
"""Turn program/*.json and interests.json into a first-draft schedule.json by keyword scoring.
Blurbs are simply each abstract's first sentence, so this is only a skeleton for the agent to rewrite."""
import collections, datetime as dt, glob, json, os, re

from scoring import blurb, clock, is_poster, load_interests, pattern, score_paper, score_session, surname

BLOCK_LABELS = [(10, "sun", "Clear skies"), (12, "cu", "Fair-weather cumulus"),
                (15, "rain", "Passing showers"), (24, "storm", "Storms firing")]
SKIP_TYPES = ("Event", "Break")

cfg, groups = load_interests()


badges = [(n, pattern(w)) for n, w in cfg.get("badges", {}).items()]
must_see = re.compile(cfg.get("must_see") or r"$^", re.I)
evening = re.compile(cfg.get("evening") or r"$^", re.I)
MIN = cfg.get("min_score", 2)


def shorten(title, limit=48):
    return title if len(title) <= limit else title[:limit].rsplit(" ", 1)[0] + "…"


def talk(p):
    b = next((n for n, r in badges if r.search(p["title"])), None)
    out = dict(time=clock(p["t"]) if p["t"] else "TBA", title=p["title"], by=surname(p["by"]), blurb=blurb(p["abs"]), paper=p["pid"])
    if b:
        out["badge"] = b
    return out


def session_card(s, talks, top):
    why = f"Keyword match: {', '.join(top[:2])}." if top else "On the list as a major program event."
    if not talks and s.get("desc"):
        why += " " + blurb(s["desc"])
    return dict(id=int(s["sid"].split("/")[1]), title=s["title"], room=s["room"], why=why,
                talks=[talk(p) for p in sorted(talks, key=lambda p: p["t"] or "99")])


def poster_block(start, sessions, papers):
    scored = []
    for p in (p for s in sessions for p in papers[s["sid"]]):
        total, group = score_paper(p, groups)
        if total >= 3:
            scored.append((total, group, p))
    scored.sort(key=lambda x: -x[0])
    by_group = collections.defaultdict(list)
    for _, g, p in scored[:cfg.get("posters_per_session", 15)]:
        by_group[g].append(dict(title=p["title"], by=surname(p["by"]), blurb=blurb(p["abs"]), paper=p["pid"]))
    if not by_group:
        return None
    room = collections.Counter(s["room"] for s in sessions).most_common(1)[0][0]
    return dict(id="p" + start.replace(":", ""), icon="poster", time=clock(start), end=clock(sessions[0]["end"]),
                short="Posters", label="Scattered drops",
                posters=dict(title="Posters", room=room, note="Keyword matches from the posters in this time slot.",
                             groups=[dict(name=k, items=v) for k, v in by_group.items()]))


days, meeting, harvested = [], None, None
paths = sorted(p for p in glob.glob(os.path.join("program", "*.json")))
if not paths:
    raise SystemExit("No program files found. Run: python harvest.py")
for path in paths:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    meeting, harvested = data["meeting"], data["harvested"]
    date = dt.date.fromisoformat(os.path.basename(path)[:10])
    papers = collections.defaultdict(list)
    for p in data["papers"]:
        if not p["wd"]:
            papers[p["sid"]].append(p)
    slots, poster_slots, nights = collections.defaultdict(list), collections.defaultdict(list), []
    for s in data["sessions"]:
        if is_poster(s):
            poster_slots[s["start"]].append(s)
        elif s["type"] not in SKIP_TYPES:
            score, top = score_session(s, papers[s["sid"]], groups)
            if must_see.search(s["title"]):
                score = max(score, MIN)
            if score >= MIN:
                slots[s["start"]].append((score, top, s))
        elif s["start"] >= "17:00" and evening.search(s["title"]):
            nights.append(s)
    blocks = []
    for start, found in slots.items():
        found.sort(key=lambda x: -x[0])
        hour = int(start[:2])
        icon, label = next((i, l) for h, i, l in BLOCK_LABELS if hour < h)
        cards = [session_card(s, papers[s["sid"]], top) for _, top, s in found]
        blocks.append((start, dict(id="t" + start.replace(":", ""), icon=icon, time=clock(start),
                                   end=clock(found[0][2]["end"]), short=shorten(found[0][2]["title"]), label=label,
                                   pick=cards[0], alts=cards[1:1 + cfg.get("alternates_per_slot", 3)])))
    for start, sessions in poster_slots.items():
        b = poster_block(start, sessions, papers)
        if b:
            blocks.append((start, b))
    blocks.sort(key=lambda x: x[0])
    blocks = [b for _, b in blocks]
    if nights:
        nights.sort(key=lambda s: s["start"])
        blocks.append(dict(id="eve", icon="moon", time=clock(nights[0]["start"]), end="late", short="Evening",
                           label="Clearing", evening="Evening events",
                           list=[dict(time=clock(s["start"]), title=s["title"], id=int(s["sid"].split("/")[1]),
                                      note=f"{s['room'] or 'Location varies'}, until {clock(s['end'])}.") for s in nights]))
    n = sum(1 for b in blocks if "pick" in b)
    days.append(dict(key=date.strftime("%a").lower(), tab=date.strftime("%a"), date=f"{date:%b} {date.day}",
                     iso=date.isoformat(), icon="storm" if n >= 4 else "rain" if n else "cu",
                     full=f"{date:%A}, {date:%B} {date.day}, {date.year}",
                     outlook=f"Today's outlook: {n} time slot{'s' if n != 1 else ''} with sessions on your radar.",
                     blocks=blocks))

first = cfg["name"].split()[0]
out = dict(title="My AMS schedule" if first == "Your" else f"{first}'s AMS schedule",
           eyebrow="AMS 107th Annual Meeting · Denver · January 10–14, 2027",
           session_url=f"https://ams.confex.com/ams/{meeting}/meetingapp.cgi/Session/{{id}}",
           footer=f"Program pulled from the public AMS Confex listing on {harvested}. Times are Denver time, and rooms and talks "
                  "can still change. Picks come from keyword scoring, and summaries are each abstract's first sentence.",
           days=days)
with open("schedule.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("Wrote schedule.json.")
