"""Daily run: fetch -> dedupe -> score -> save dashboard data -> email digest."""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import sys
import traceback

from . import mailer
from .scoring import city_of, score
from .sources import LinkedIn, Naukri

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
LOG: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)
    LOG.append(msg)


def load(name, default):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else default


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def main() -> int:
    profile = json.loads((ROOT / "profile.json").read_text())
    days = int(os.environ.get("RADAR_DAYS", "1"))
    now = dt.datetime.now(IST)
    today = now.date().isoformat()
    jobs: list[dict] = load("jobs.json", [])
    for j in jobs:  # re-check city labels with the current rules (e.g. Pune jobs once tagged Remote)
        c = city_of(j)
        j["city"] = c or "Other"
        if not c and j.get("flags") is not None:
            j["flags"] = [f for f in j["flags"] if f != "+Remote"]
            if "Outside your cities" not in j["flags"]:
                j["flags"].append("Outside your cities")
    runs: list[dict] = load("runs.json", [])
    known = {j["id"] for j in jobs}
    known_keys = {(norm(j["company"]), norm(j["title"])) for j in jobs}

    raw: dict[str, dict] = {}
    run = {"at": now.isoformat(timespec="seconds"), "date_label": now.strftime("%a %d %b %Y"),
           "sources": {"LinkedIn": {"ok": False, "fetched": 0}, "Naukri": {"ok": False, "fetched": 0}}}

    # ---- LinkedIn
    li = LinkedIn(log)
    try:
        seconds = 86400 * days
        for q in profile["queries"]:
            for city in profile["cities"].values():
                for loc in city["linkedin"]:
                    for j in li.search(q, loc, seconds):
                        raw.setdefault(j["id"], j)
                    if li.blocked:
                        break
        for j in li.search(profile["remote_query"], "India", 86400 * days, remote=True, pages=3):
            raw.setdefault(j["id"], j)
        n = sum(1 for j in raw.values() if j["source"] == "LinkedIn")
        run["sources"]["LinkedIn"] = {"ok": n > 0, "fetched": n, "error": "rate-limited by LinkedIn" if li.blocked else (None if n else "no results")}
    except Exception as e:
        traceback.print_exc()
        run["sources"]["LinkedIn"]["error"] = f"{type(e).__name__}: {e}"[:160]

    # ---- Naukri
    try:
        before = len(raw)
        with Naukri(log) as nk:
            failures = 0
            for q in profile["queries"]:
                for city in profile["cities"].values():
                    res = nk.search(q, city["naukri_slug"], city["naukri_l"], max(1, days))
                    failures += 0 if res else 1
                    for j in res:
                        raw.setdefault(j["id"], j)
            diag = "; ".join(nk.diag)
        n = len(raw) - before
        run["sources"]["Naukri"] = {"ok": n > 0, "fetched": n,
                                    "error": None if n else "no results (the site may be blocking cloud servers)",
                                    "diag": diag}
    except Exception as e:
        traceback.print_exc()
        run["sources"]["Naukri"]["error"] = f"{type(e).__name__}: {e}"[:160]

    run["scanned"] = len(raw)

    # ---- dedupe against history
    fresh = []
    for j in raw.values():
        key = (norm(j["company"]), norm(j["title"]))
        if j["id"] in known or key in known_keys:
            continue
        known_keys.add(key)
        fresh.append(j)

    # ---- first pass on title/tags, then read LinkedIn JDs for survivors
    prelim = [(j, score(j, profile)) for j in fresh]
    prelim = [(j, s) for j, s in prelim if s]
    jd_budget = int(os.environ.get("RADAR_JD_LIMIT", "40"))
    for j, _ in sorted(prelim, key=lambda x: -x[1]["score"]):
        if j["source"] != "LinkedIn" or jd_budget <= 0 or li.blocked:
            continue
        d = li.description(j["id"])
        jd_budget -= 1
        if d:
            j["desc"] = d
    # also give LinkedIn listings that just missed on title a chance once the JD is read
    added = []
    for j in fresh:
        s = score(j, profile)
        if not s:
            continue
        added.append({
            "id": j["id"], "source": j["source"], "title": j["title"], "company": j["company"],
            "location": j.get("location", ""), "city": s["city"], "exp": j.get("exp", ""),
            "salary": j.get("salary", ""), "posted": j.get("posted", ""), "url": j["url"],
            "score": s["score"], "family": s["family"], "why": s["why"], "flags": s["flags"],
            "first_seen": today,
        })
    run["added"] = len(added)
    log(f"Scanned {run['scanned']}, new {len(fresh)}, kept {len(added)}")

    # ---- save (keep 45 days of history)
    cutoff = (now.date() - dt.timedelta(days=45)).isoformat()
    jobs = [j for j in jobs + added if j.get("first_seen", today) >= cutoff]
    jobs.sort(key=lambda j: (j["first_seen"], j["score"]), reverse=True)
    runs = ([{k: v for k, v in run.items() if k != "date_label"}] + runs)[:60]
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=1))
    (DATA / "runs.json").write_text(json.dumps(runs, ensure_ascii=False, indent=1))

    # ---- email
    sender, pw, to = (os.environ.get(k, "").strip() for k in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "MAIL_TO"))
    repo = os.environ.get("GITHUB_REPOSITORY", "owner/job-radar")
    owner, name = repo.split("/", 1)
    dashboard = os.environ.get("DASHBOARD_URL") or f"https://{owner.lower()}.github.io/{name}/"
    if sender and pw:
        strong = sum(1 for j in added if j["score"] >= 80)
        subject = (f"{len(added)} new job matches ({strong} strong) · {now.strftime('%d %b')}" if added
                   else f"No new job matches today · {now.strftime('%d %b')}")
        try:
            new_ids = {j["id"] for j in added}
            top_open = [j for j in sorted(jobs, key=lambda j: -j["score"]) if j["id"] not in new_ids][:5]
            mailer.send(sender, pw, to or sender, subject,
                        mailer.build_html(added, run, dashboard, len(jobs), top_open))
            log("Email sent")
        except Exception as e:
            log(f"Email failed: {e}")
            return 1
    else:
        log("Email skipped: GMAIL_ADDRESS / GMAIL_APP_PASSWORD secrets not set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
