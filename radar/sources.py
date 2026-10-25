"""Fetch job listings from LinkedIn (public guest feed) and Naukri (via headless browser)."""
from __future__ import annotations

import html
import json
import re
import time
import urllib.parse as up

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


# ---------------------------------------------------------------- LinkedIn
class LinkedIn:
    BASE = "https://www.linkedin.com/jobs-guest/jobs/api"

    def __init__(self, log):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"})
        self.log = log
        self.blocked = False

    def _get(self, url: str) -> str | None:
        for attempt in range(3):
            try:
                r = self.s.get(url, timeout=25)
            except requests.RequestException as e:
                self.log(f"LinkedIn request error: {e}")
                time.sleep(4)
                continue
            if r.status_code == 200:
                return r.text
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            self.log(f"LinkedIn HTTP {r.status_code} for {url[:90]}")
            return None
        self.blocked = True
        return None

    def search(self, keywords: str, location: str, seconds: int, remote=False, pages=2) -> list[dict]:
        out = []
        for start in range(0, pages * 10, 10):
            q = {"keywords": keywords, "location": location, "f_TPR": f"r{seconds}",
                 "f_E": "4,5", "start": start}
            if remote:
                q["f_WT"] = "2"
            text = self._get(f"{self.BASE}/seeMoreJobPostings/search?{up.urlencode(q)}")
            time.sleep(1.5)
            if not text:
                break
            cards = text.split("<li>")[1:]
            for c in cards:
                m = re.search(r"jobPosting:(\d+)", c)
                if not m:
                    continue
                g = lambda pat: _clean((re.search(pat, c, re.S) or [None, ""])[1])
                out.append({
                    "id": "li-" + m.group(1),
                    "source": "LinkedIn",
                    "title": g(r'base-search-card__title[^>]*>(.*?)</h3>'),
                    "company": g(r'base-search-card__subtitle[^>]*>(.*?)</h4>'),
                    "location": g(r'job-search-card__location[^>]*>(.*?)</span>'),
                    "posted": g(r'<time[^>]*>(.*?)</time>'),
                    "salary": g(r'job-search-card__salary-info[^>]*>(.*?)</span>'),
                    "url": f"https://www.linkedin.com/jobs/view/{m.group(1)}",
                    "remote_search": remote,
                })
            if len(cards) < 10:
                break
        return out

    def description(self, job_id: str) -> str | None:
        text = self._get(f"{self.BASE}/jobPosting/{job_id.removeprefix('li-')}")
        if not text:
            return None
        m = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', text, re.S)
        crit = " / ".join(_clean(x) for x in re.findall(r'description__job-criteria-text[^>]*>(.*?)</span>', text, re.S))
        return (_clean(m.group(1)) if m else "") + (" Criteria: " + crit if crit else "")


# ---------------------------------------------------------------- Naukri
class Naukri:
    """Naukri's search API needs tokens the site's own JavaScript creates, so we load the
    real search page in headless Chromium and read the JSON response it receives."""

    def __init__(self, log):
        self.log = log
        self.pw = self.browser = self.ctx = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        self.ctx = self.browser.new_context(user_agent=UA, locale="en-IN", timezone_id="Asia/Kolkata",
                                            viewport={"width": 1366, "height": 900})
        self.ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        return self

    def __exit__(self, *a):
        for x in (self.ctx, self.browser):
            try:
                x and x.close()
            except Exception:
                pass
        if self.pw:
            self.pw.stop()

    def search(self, query: str, city_slug: str, city_l: str, days: int) -> list[dict]:
        slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
        url = (f"https://www.naukri.com/{slug}-jobs-in-{city_slug}?"
               + up.urlencode({"k": query, "l": city_l, "experience": 14, "jobAge": days}))
        page = self.ctx.new_page()
        data = None
        try:
            with page.expect_response(lambda r: "/jobapi/v3/search" in r.url and r.status == 200, timeout=30000) as resp:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
            data = resp.value.json()
        except Exception as e:
            self.log(f"Naukri {query} / {city_slug}: {type(e).__name__}: {str(e)[:120]}")
        finally:
            page.close()
        time.sleep(2)
        if not data:
            return []
        out = []
        for j in data.get("jobDetails", []):
            ph = {p.get("type"): p.get("label", "") for p in j.get("placeholders", [])}
            sd = j.get("salaryDetail") or {}
            max_lpa = None
            if not sd.get("hideSalary") and sd.get("maximumSalary"):
                max_lpa = round(sd["maximumSalary"] / 1e5, 1)
            out.append({
                "id": "nk-" + str(j.get("jobId")),
                "source": "Naukri",
                "title": _clean(j.get("title", "")),
                "company": _clean(j.get("companyName", "")),
                "location": ph.get("location", ""),
                "exp": ph.get("experience", ""),
                "exp_min": _int(j.get("minimumExperience")),
                "exp_max": _int(j.get("maximumExperience")),
                "salary": "" if ph.get("salary", "").lower().startswith("not") else ph.get("salary", ""),
                "max_lpa": max_lpa,
                "posted": j.get("footerPlaceholderLabel", ""),
                "tags": j.get("tagsAndSkills", ""),
                "desc": _clean(j.get("jobDescription", "")),
                "walkin": bool(j.get("walkinJob")),
                "url": "https://www.naukri.com" + j.get("jdURL", ""),
            })
        return out


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
