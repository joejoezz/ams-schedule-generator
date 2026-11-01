"""Shared helpers for draft.py and digest.py: keyword scoring and text formatting."""
import json, os, re, sys


def pattern(words):
    parts = [re.escape(w[:-1]) if w.endswith("*") else re.escape(w) + r"\b" for w in words]
    return re.compile(r"\b(?:" + "|".join(parts) + ")", re.I)


def load_interests():
    if not os.path.exists("interests.json"):
        sys.exit("No interests.json found. Copy interests.example.json to interests.json and edit it.")
    with open("interests.json", encoding="utf-8") as f:
        cfg = json.load(f)
    groups = [(n, g["weight"], pattern(g["keywords"])) for n, g in cfg["groups"].items()]
    return cfg, groups


def is_poster(s):
    return s["type"] == "Poster Session" or s["title"].lower().startswith("poster")


def clock(t):
    h, m = t.split(":")
    return f"{int(h) % 12 or 12}:{m}"


def surname(by):
    # Lead author formats: "First Last , Org, City, ST; and ..." or "First Last, Org, City, ST; and ..."
    first = by.split(";")[0]
    name, _, rest = first.partition(" , " if " , " in first else ",")
    words = [w for w in name.split() if w.rstrip(".,") not in ("Jr", "Sr", "II", "III", "IV")]
    last = words[-1] if words else "Speaker to be announced"
    org = rest.split(",")[0].strip()
    return f"{last}, {org}" if org else last


def blurb(text):
    if not text:
        return "No abstract published yet."
    first = re.split(r"(?<=[a-z0-9)][.!?])\s+(?=[A-Z])", text)[0]
    return first if len(first) <= 230 else first[:230].rsplit(" ", 1)[0] + "…"


def score_session(s, talks, groups):
    total, hits = 0, {}
    for name, weight, rx in groups:
        share = sum(bool(rx.search(p["title"])) for p in talks) / max(len(talks), 1)
        v = weight * (3 * bool(rx.search(s["title"])) + 3 * share + bool(rx.search(s.get("desc", ""))))
        total += v
        if v > 0:
            hits[name] = v
    return total, sorted(hits, key=hits.get, reverse=True)


def score_paper(p, groups):
    vals = {n: w * (3 * bool(r.search(p["title"])) + bool(r.search(p["abs"]))) for n, w, r in groups}
    return sum(vals.values()), max(vals, key=vals.get)
