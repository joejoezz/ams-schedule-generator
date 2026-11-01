#!/usr/bin/env python3
"""Validate schedule.json and pour it into template.html, producing one self-contained page.
Full abstracts come from the program files, using each talk's and poster's paper id.

    python build.py                     # schedule.json -> my-ams-schedule.html
    python build.py --check program     # also compare rooms, talk times and talk counts with the program
"""
import argparse, glob, html, json, os, re, sys

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("schedule", nargs="?", default="schedule.json")
ap.add_argument("-o", "--output", default="my-ams-schedule.html")
ap.add_argument("--check", metavar="PROGRAM_FOLDER", help="cross-check against harvested program files")
a = ap.parse_args()

here = os.path.dirname(os.path.abspath(__file__))
ICONS = {"sun", "cu", "rain", "tcu", "storm", "poster", "moon"}
with open(a.schedule, encoding="utf-8") as f:
    doc = json.load(f)
errors = []


def need(obj, where, *keys):
    for k in keys:
        if obj.get(k) in (None, ""):
            errors.append(f"{where}: missing {k}")


def check_card(c, where):
    need(c, where, "id", "title", "room", "why")
    for t in c.get("talks", []):
        need(t, f"{where} / {t.get('title', '?')}", "time", "title", "by", "blurb")


need(doc, "top level", "title", "eyebrow", "session_url", "footer", "days")
for d in doc.get("days", []):
    w = d.get("key", "?")
    need(d, w, "key", "tab", "date", "iso", "icon", "full", "outlook")
    seen = set()
    for b in d.get("blocks", []):
        bw = f"{w} {b.get('time', '?')}"
        need(b, bw, "id", "icon", "time", "end", "short", "label")
        if b.get("icon") not in ICONS:
            errors.append(f"{bw}: icon must be one of {sorted(ICONS)}")
        if b.get("id") in seen:
            errors.append(f"{bw}: duplicate block id {b.get('id')}")
        seen.add(b.get("id"))
        kinds = [k for k in ("pick", "posters", "evening") if k in b]
        if len(kinds) != 1:
            errors.append(f"{bw}: needs exactly one of pick, posters, evening")
        if "pick" in b:
            check_card(b["pick"], bw)
            for alt in b.get("alts", []):
                check_card(alt, bw)
        if "posters" in b:
            need(b["posters"], bw, "room", "note", "groups")

if a.check:
    sessions, papers = {}, {}
    for path in glob.glob(os.path.join(a.check, "*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for s in data["sessions"]:
            sessions[int(s["sid"].split("/")[1])] = s
        for p in data["papers"]:
            if not p["wd"] and p["t"]:
                papers.setdefault(int(p["sid"].split("/")[1]), []).append(p["t"])

    def clock(t):
        h, m = t.split(":")
        return f"{int(h) % 12 or 12}:{m}"
    checked = talks = 0
    for d in doc["days"]:
        for b in d["blocks"]:
            for c in ([b["pick"]] + b.get("alts", [])) if "pick" in b else []:
                s = sessions.get(c["id"])
                w = f"{d['key']} {c['title'][:50]}"
                if not s:
                    errors.append(f"{w}: session {c['id']} is not in the program")
                    continue
                checked += 1
                if s["room"] != c["room"]:
                    errors.append(f"{w}: room says {c['room']}, program says {s['room']}")
                if clock(s["start"]) != b["time"]:
                    errors.append(f"{w}: block time {b['time']}, program says {clock(s['start'])}")
                have, want = sorted(t["time"] for t in c.get("talks", [])), sorted(clock(t) for t in papers.get(c["id"], []))
                talks += len(have)
                panel = re.search("Panel|Town Hall|Keynote|Lecture", s["type"] or "") or len(want) <= 1
                if have != want and (have or not panel):
                    errors.append(f"{w}: talk times {have} differ from program {want}")
    print(f"Checked {checked} sessions and {talks} talks against {a.check}.")

# Fill in full abstracts from the program, so nobody has to copy them by hand.
source = a.check or "program"
abstracts = {}
for path in glob.glob(os.path.join(source, "*.json")):
    with open(path, encoding="utf-8") as f:
        for p in json.load(f)["papers"]:
            if "pid" not in p:
                sys.exit(f"{path} is from an older download. Rerun: python harvest.py")
            abstracts[p["pid"]] = p
linked = unlinked = 0
for d in doc["days"]:
    for b in d["blocks"]:
        items = []
        for c in ([b["pick"]] + b.get("alts", [])) if "pick" in b else []:
            for t in c.get("talks", []):
                items.append((t, c["id"]))
        for g in b["posters"]["groups"] if "posters" in b else []:
            items.extend((i, None) for i in g["items"])
        for item, sid in items:
            pid = item.get("paper")
            if pid is None:
                unlinked += 1
            elif abstracts:
                p = abstracts.get(pid)
                if not p:
                    errors.append(f"{d['key']} {item['title'][:50]}: paper {pid} is not in the program")
                elif sid and int(p["sid"].split("/")[1]) != sid:
                    errors.append(f"{d['key']} {item['title'][:50]}: paper {pid} belongs to another session")
                elif p["by"] and item["by"].split(",")[0].strip().lower() not in p["by"].lower():
                    errors.append(f"{d['key']} {item['title'][:50]}: speaker {item['by']!r} is not on paper {pid}: {p['by'][:80]}")
                else:
                    item["abstract"] = p["abs"]
                    linked += 1
print(f"Added {linked} full abstracts. {unlinked} talks or posters have no paper id, so they have no abstract or link.")

if errors:
    print(f"{len(errors)} problem(s):")
    print("\n".join("  " + e for e in errors))
    sys.exit(1)

with open(os.path.join(here, "template.html"), encoding="utf-8") as f:
    page = f.read()
page = page.replace("{{TITLE}}", html.escape(doc["title"]))
page = page.replace("{{DATA}}", json.dumps(doc, ensure_ascii=False).replace("</", "<\\/"))
with open(a.output, "w", encoding="utf-8") as f:
    f.write(page)
print(f"Wrote {a.output}. Open it in a browser.")
