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
from collections import Counter

from .gcc import classify
from .jd import extract_points, themes_of
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


PREP_MIN = 65  # Strong (80+) and Good (65-79) matches get JD bullets and interview prep


def attach_jd(job: dict, desc: str | None) -> None:
    """Save the JD's key bullet points and interview themes on a job."""
    if desc:
        pts = extract_points(desc)
        job["jd_points"] = pts
        job["jd_status"] = "ok" if pts else "thin"
        job["themes"] = themes_of(" ".join(pts) or desc, job.get("title", ""))
    else:
        job["jd_tries"] = job.get("jd_tries", 0) + 1
        job["jd_status"] = "unavailable"
        job.setdefault("themes", themes_of(job.get("title", ""), job.get("why", "")))


def retag(jobs: list[dict], profile: dict) -> list[dict]:
    """Re-check saved jobs with the current rules: city buckets, GCC status and sector."""
    out = []
    for j in jobs:
        c = city_of(j)
        j["city"] = c or "Other India"
        flags = [f for f in (j.get("flags") or []) if f not in ("Outside your cities", "Outside first-preference cities")]
        if j["city"] not in ("Bengaluru", "Hyderabad", "Delhi NCR", "Remote"):
            flags.append("Outside first-preference cities")
        if j["city"] != "Remote":
            flags = [f for f in flags if f != "+Remote"]
        j["flags"] = flags
        if j.get("source") != "Curated":
            g = classify(j.get("company", ""))
            if profile.get("gcc_only", False) and not g["gcc"]:
                continue
            j["gcc"], j["sector"] = g["gcc"], (g["sector"] or "Other GCC") if g["gcc"] else ""
            if g["own"] and "Your current employer: apply internally" not in j["flags"]:
                j["flags"].append("Your current employer: apply internally")
        out.append(j)
    return out


def main() -> int:
    profile = json.loads((ROOT / "profile.json").read_text())
    days = int(os.environ.get("RADAR_DAYS", "1"))
    now = dt.datetime.now(IST)
    today = now.date().isoformat()
    jobs: list[dict] = load("jobs.json", [])
    jobs = retag(jobs, profile)
    runs: list[dict] = load("runs.json", [])
    known = {j["id"] for j in jobs}
    known_keys = {(norm(j["company"]), norm(j["title"])) for j in jobs}

    raw: dict[str, dict] = {}
    run = {"at": now.isoformat(timespec="seconds"), "date_label": now.strftime("%a %d %b %Y"),
           "sources": {"LinkedIn": {"ok": False, "fetched": 0}, "Naukri": {"ok": False, "fetched": 0}}}

    # ---- LinkedIn: each GCC hub city, then India-wide to catch the smaller hubs
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
            if not li.blocked:
                for j in li.search(q, "India", seconds, pages=3):
                    raw.setdefault(j["id"], j)
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
    added, not_gcc = [], Counter()
    for j in fresh:
        s = score(j, profile)
        if not s:
            continue
        if not s["gcc"]:
            not_gcc[j.get("company", "?")] += 1
        added.append({
            "id": j["id"], "source": j["source"], "title": j["title"], "company": j["company"],
            "location": j.get("location", ""), "city": s["city"], "exp": j.get("exp", ""),
            "salary": j.get("salary", ""), "posted": j.get("posted", ""), "url": j["url"],
            "score": s["score"], "family": s["family"], "why": s["why"], "flags": s["flags"],
            "gcc": s["gcc"], "sector": s["sector"],
            "first_seen": today,
        })
        if s["score"] >= PREP_MIN or j.get("desc"):
            attach_jd(added[-1], j.get("desc"))
    run["added"] = len(added)
    run["not_gcc_dropped"] = sum(not_gcc.values())
    run["not_gcc_top"] = [c for c, _ in not_gcc.most_common(12)]
    if not_gcc:
        log("Non-GCC employers (on the main dashboard only; add real GCCs to radar/gcc.py): " + ", ".join(run["not_gcc_top"]))
    log(f"Scanned {run['scanned']}, new {len(fresh)}, kept {len(added)}")

    # ---- backfill JD bullets for earlier Strong/Good matches (a batch per run; two tries each)
    need = [j for j in jobs + added if j["score"] >= PREP_MIN and j.get("source") in ("LinkedIn", "Naukri")
            and j.get("jd_status") not in ("ok", "thin") and j.get("jd_tries", 0) < 2
            and j["id"] not in {a["id"] for a in added if a.get("jd_status") in ("ok", "thin")}]
    need.sort(key=lambda j: -j["score"])
    li_budget, nk_budget, filled = int(os.environ.get("RADAR_JD_BACKFILL", "60")), 30, 0
    for j in [x for x in need if x["source"] == "LinkedIn"][:li_budget]:
        if li.blocked:
            break
        attach_jd(j, li.description(j["id"]))
        filled += j.get("jd_status") == "ok"
    nk_need = [x for x in need if x["source"] == "Naukri"][:nk_budget]
    if nk_need:
        try:
            with Naukri(log) as nk:
                for j in nk_need:
                    attach_jd(j, nk.description(j["url"]))
                    filled += j.get("jd_status") == "ok"
        except Exception as e:
            log(f"Naukri JD backfill failed: {type(e).__name__}: {e}"[:200])
    for j in jobs + added:  # every job gets themes, even without a JD
        if "themes" not in j:
            j["themes"] = themes_of(j.get("title", ""), j.get("why", ""), " ".join(j.get("jd_points", [])))
    run["jd_backfilled"] = filled
    log(f"JD bullets added for {filled} earlier matches; {len(need) - filled} still waiting")

    # ---- save (keep 45 days of history)
    cutoff = (now.date() - dt.timedelta(days=45)).isoformat()
    jobs = [j for j in jobs + added if j.get("first_seen", today) >= cutoff]
    jobs.sort(key=lambda j: (j["first_seen"], j["score"]), reverse=True)
    runs = ([{k: v for k, v in run.items() if k != "date_label"}] + runs)[:60]
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False, indent=1))
    (DATA / "runs.json").write_text(json.dumps(runs, ensure_ascii=False, indent=1))

    # ---- email: the all-employers digest, then the GCC-only alert
    sender, pw, to = (os.environ.get(k, "").strip() for k in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "MAIL_TO"))
    repo = os.environ.get("GITHUB_REPOSITORY", "owner/job-radar")
    owner, name = repo.split("/", 1)
    dashboard = os.environ.get("DASHBOARD_URL") or f"https://{owner.lower()}.github.io/{name}/"
    if not (sender and pw):
        log("Email skipped: GMAIL_ADDRESS / GMAIL_APP_PASSWORD secrets not set")
        return 0
    failed = False
    for mode in ("all", "gcc"):
        pool = jobs if mode == "all" else [j for j in jobs if j.get("gcc")]
        new = added if mode == "all" else [j for j in added if j.get("gcc")]
        strong = sum(1 for j in new if j["score"] >= 80)
        day = now.strftime("%d %b")
        if mode == "all":
            subject = (f"{len(new)} new job matches ({strong} strong) · {day}" if new
                       else f"No new job matches today · {day}")
            url = dashboard
        else:
            subject = (f"GCC job alert: {len(new)} new match{'es' if len(new) != 1 else ''} ({strong} strong) · {day}" if new
                       else f"GCC job alert: no new matches today · {day}")
            url = dashboard + "gcc/"
        try:
            new_ids = {j["id"] for j in new}
            top_open = [j for j in sorted(pool, key=lambda j: -j["score"]) if j["id"] not in new_ids][:5]
            mailer.send(sender, pw, to or sender, subject,
                        mailer.build_html(new, run, url, len(pool), top_open, mode=mode),
                        from_name="Job Match Radar" if mode == "all" else "GCC Job Alert")
            log(f"Email sent ({mode})")
        except Exception as e:
            log(f"Email failed ({mode}): {e}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
