#!/usr/bin/env python3
"""Download the public AMS program from the Confex meeting API, one JSON file per day.
Uses only the Python standard library. Takes about an hour the first time because the
API allows roughly one request per second. Rerun safely: finished requests are cached.

    python harvest.py
    python harvest.py --fresh      # discard the cache and pick up program changes
"""
import argparse, datetime as dt, html, json, os, re, shutil, time, urllib.error, urllib.request

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--meeting", default="107ANNUAL", help="Confex meeting code")
ap.add_argument("--first", default="2027-01-10", help="first day, YYYY-MM-DD")
ap.add_argument("--last", default="2027-01-14", help="last day, YYYY-MM-DD")
ap.add_argument("--out", default="program", help="output folder")
ap.add_argument("--cache", help="cache folder (default: <out>/cache)")
ap.add_argument("--fresh", action="store_true", help="delete the cache first")
a = ap.parse_args()

BASE = f"https://ams.confex.com/ams/{a.meeting}/meetingapi.cgi"
cache = a.cache or os.path.join(a.out, "cache")
if a.fresh and os.path.isdir(cache):
    shutil.rmtree(cache)
os.makedirs(cache, exist_ok=True)
os.makedirs(a.out, exist_ok=True)


def get(path):
    name = os.path.join(cache, re.sub(r"[^A-Za-z0-9_.-]+", "_", path) + ".json")
    if os.path.exists(name):
        with open(name, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(f"{BASE}/{path}", headers={
        "Accept": "application/json", "Content-Type": "application/json",
        "User-Agent": "ams-schedule-generator (personal conference planning)"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8"))
            with open(name, "w", encoding="utf-8") as f:
                json.dump(data, f)
            time.sleep(1.0)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            wait = 15 * 2 ** attempt
            print(f"  HTTP {e.code} on {path}; waiting {wait} s", flush=True)
        except OSError as e:
            wait = 15 * 2 ** attempt
            print(f"  {e} on {path}; waiting {wait} s", flush=True)
        time.sleep(wait)
    raise SystemExit(f"Gave up on {path}. Rerun later; finished requests are cached.")


def clean(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()


programs = get("Program")
day = dt.date.fromisoformat(a.first)
while day <= dt.date.fromisoformat(a.last):
    iso = day.isoformat()
    slots = {}
    for p in programs:
        for s in get(f"Day/Program{p['id']}_{iso}/ChildList_SlotData") or []:
            slots[s["Entryid"]] = s
    print(iso, "sessions and events:", len(slots), flush=True)
    sessions, papers = [], []
    for sid, s in slots.items():
        info = dict(sid=sid, title=clean(s["Entry_Title"]), type=s.get("Entry_Type"),
                    room=s.get("Room_Name", ""), start=s["Slot_StartTime"][:5], end=s["Slot_EndTime"][:5])
        if s.get("Entry_Type") not in ("Event", "Break"):
            detail = get(sid) or {}
            info["top"] = clean(detail.get("TopDisplay"))
            info["desc"] = " ".join(clean(detail.get(k)) for k in
                                    ("Abstract", "Description", "Summary", "SessionDescription") if detail.get(k))
            for p in get(sid + "/ChildList_Paper") or []:
                m = re.match(r".*_(\d\d:\d\d):\d\d_(\d\d:\d\d)", p.get("SortableTimeString") or "")
                papers.append(dict(sid=sid, pid=int(p["id"]), num=p.get("FinalNumber", ""), title=clean(p.get("Title")),
                                   by=clean(p.get("TopDisplay")), abs=clean(p.get("Abstract")),
                                   t=m.group(1) if m else "", wd=p.get("Withdrawn", "")))
        sessions.append(info)
    with open(os.path.join(a.out, f"{iso}.json"), "w", encoding="utf-8") as f:
        json.dump(dict(meeting=a.meeting, harvested=dt.date.today().isoformat(),
                       sessions=sessions, papers=papers), f, ensure_ascii=False)
    print(iso, "saved", len(sessions), "sessions,", len(papers), "papers", flush=True)
    day += dt.timedelta(days=1)
print("Done.")
