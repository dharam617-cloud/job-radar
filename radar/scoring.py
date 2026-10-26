"""Score a listing 0-100 against the profile.

Weights: role fit 35, experience band 15, Agile/SAFe tooling 15, data/AI overlap 15,
BFSI domain 10, location + pay 10. Penalties for PMP-mandatory, hands-on coding, engineering stacks.
"""
from __future__ import annotations

import re

EXCLUDE_TITLE = re.compile(
    r"\b(developer|software engineer|data engineer|ml engineer|devops engineer|qa engineer|test engineer|"
    r"engineering manager|architect|scientist|designer|recruiter|sales|account executive|business analyst|"
    r"asic|soc\b|firmware|hardware|silicon|cpu|gpu|embedded|mechanical|civil|construction|npi|supply chain|"
    r"intern|trainee|associate program manager|junior|jr\.?)\b", re.I)
RTE = re.compile(r"release train engineer|\brte\b", re.I)

ROLE_RULES = [
    (re.compile(r"release train|\brte\b", re.I), 35, "Release Train Engineer"),
    (re.compile(r"agile coach|agile delivery|agile lead|delivery steward", re.I), 35, "Agile leadership"),
    (re.compile(r"scrum master|scrum lead", re.I), 33, "Scrum Master"),
    (re.compile(r"technical program|technical programme|\btpm\b", re.I), 32, "Technical Program Manager"),
    (re.compile(r"(ai|ml|data|analytics|genai|mlops).{0,25}(program|programme|delivery|portfolio)|"
                r"(program|programme|delivery|portfolio).{0,25}(ai|ml|data|analytics|genai)", re.I), 34, "AI/Data Program"),
    (re.compile(r"program(me)? (manager|management|lead|director)|portfolio (manager|lead)", re.I), 30, "Program Manager"),
    (re.compile(r"delivery (manager|lead|leader|head)", re.I), 30, "Delivery Manager"),
    (re.compile(r"project (manager|lead)|pmo", re.I), 22, "Project Manager"),
]

AGILE = ["safe", "scrum", "agile", "jira", "confluence", "release train", "kanban", "sprint", "azure devops", "rally", "pi planning"]
DATA_AI = ["data", "analytics", "machine learning", "mlops", "genai", "generative", "llm", "agentic", " ai ", "artificial intelligence",
           "tableau", "alteryx", "data governance", "aws", "cloud"]
BFSI_TEXT = ["bank", "banking", "financial services", "fintech", "insurance", "bfsi", "capital market", "payments", "wealth"]
BFSI_CO = ["jpmorgan", "jp morgan", "goldman", "state street", "deutsche", "hsbc", "standard chartered", "barclays", "citi",
           "wells fargo", "ubs", "morgan stanley", "fidelity", "schwab", "american express", "amex", "mastercard", "visa",
           "commonwealth bank", "natwest", "lloyds", "bny", "northern trust", "lseg", "london stock exchange", "nomura",
           "societe generale", "bnp", "hdfc", "icici", "axis bank", "kotak", "paypal", "razorpay", "phonepe", "the standard"]

CITY_PATTERNS = [
    ("Bengaluru", re.compile(r"bengaluru|bangalore", re.I)),
    ("Hyderabad", re.compile(r"hyderabad|secunderabad", re.I)),
    ("Delhi NCR", re.compile(r"delhi|gurugram|gurgaon|noida|ncr|faridabad|ghaziabad", re.I)),
]


def city_of(job: dict) -> str | None:
    """Target city, or "Remote" only when the listing itself says remote / work from home.
    LinkedIn's public feed ignores its remote filter, so a 'remote search' hit alone is not proof."""
    loc = job.get("location", "")
    text = " ".join([loc, job.get("desc", ""), job.get("tags", "")])
    for name, pat in CITY_PATTERNS:
        if pat.search(loc):
            return name
    if re.search(r"\bremote\b|work from home|\bwfh\b|fully remote", text, re.I):
        return "Remote"
    return None


def _years(job: dict, text: str) -> tuple[int | None, int | None]:
    if job.get("exp_min") is not None or job.get("exp_max") is not None:
        return job.get("exp_min"), job.get("exp_max")
    nums = [int(a) for a, _ in re.findall(r"(\d{1,2})\s*\+?\s*(?:-|to|–)?\s*(\d{0,2})\s*\+?\s*years", text, re.I) if 2 <= int(a) <= 30]
    if not nums:
        return None, None
    return max(nums), None


def _salary_max_lpa(job: dict) -> float | None:
    if job.get("max_lpa"):
        return job["max_lpa"]
    s = job.get("salary", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(lac|lakh|lpa)", s, re.I)
    if m:
        return float(m.group(2))
    return None


def score(job: dict, profile: dict) -> dict | None:
    title = job.get("title", "")
    if EXCLUDE_TITLE.search(title) and not RTE.search(title):
        return None
    text = " ".join([title, job.get("tags", ""), job.get("desc", "")]).lower()
    text_sp = f" {re.sub(r'[^a-z0-9+ ]', ' ', text)} "

    # role fit
    role_pts, family = 0, None
    for pat, pts, fam in ROLE_RULES:
        if pat.search(title):
            role_pts, family = pts, fam
            break
    if not family:
        return None

    flags, why = [], [family + " role"]

    # experience
    lo, hi = _years(job, text)
    band_lo, band_hi = profile["experience_band"]
    if hi is not None and hi < 8:
        return None
    if lo is None and hi is None:
        exp_pts = 9
        flags.append("Experience not stated")
    elif hi is None:  # "X+ years" read from a description
        if lo >= band_lo:
            exp_pts = 15
            why.append(f"asks {lo}+ yrs, in line with your {profile['years']}")
        else:
            exp_pts = 10 if lo >= 7 else 6
            flags.append("Lower experience ask")
    elif lo is not None and (lo <= profile["years"] <= hi or band_lo <= lo <= band_hi):
        exp_pts = 15
        why.append(f"{job.get('exp') or f'{lo}–{hi} yrs'} fits your {profile['years']} years")
    elif hi < band_lo:
        exp_pts = 8
        flags.append("Lower experience ask")
    else:
        exp_pts = 10

    # agile tooling
    a_hits = [k for k in AGILE if k in text]
    agile_pts = min(15, 4 * len(a_hits))
    if "safe" in a_hits:
        flags.append("+SAFe")

    # data/AI
    d_hits = [k.strip() for k in DATA_AI if k in text_sp]
    data_pts = min(15, 4 * len(d_hits))
    if any(k in d_hits for k in ["genai", "generative", "llm", "agentic", "machine learning", "mlops", "ai", "artificial intelligence"]):
        flags.append("+AI")
    elif "data" in d_hits or "analytics" in d_hits:
        flags.append("+Data")

    # BFSI
    co = job.get("company", "").lower()
    bfsi = any(k in co for k in BFSI_CO) or any(k in text for k in BFSI_TEXT)
    bfsi_pts = 10 if bfsi else 0
    if bfsi:
        flags.append("+BFSI")
        why.append("BFSI domain like your CBA and JPMorgan work")

    # location + pay
    city = city_of(job)
    if not city:
        return None
    loc_pts = 5
    if city == "Remote":
        flags.append("+Remote")
    pay = _salary_max_lpa(job)
    if pay is not None and pay < profile["pay_floor_lpa"]:
        return None
    pay_pts = 5  # undisclosed pay is never penalised; only a disclosed max below the floor drops a job
    if pay is None:
        flags.append("Pay not disclosed")

    # penalties
    pen = 0
    if re.search(r"pmp\b.{0,40}(mandatory|required|must)|(mandatory|required|must).{0,40}\bpmp\b", text):
        pen += 8
        flags.append("PMP required")
    if re.search(r"hands-on (coding|development|programming)|strong coding|write code", text):
        pen += 8
        flags.append("Hands-on coding")
    if re.search(r"\b(java|\.net|c\+\+|golang|salesforce|sap|oracle|servicenow)\b", title, re.I):
        pen += 6
        flags.append("Specific tech stack")
    if job.get("walkin"):
        flags.append("Walk-in drive")
    if job.get("source") == "LinkedIn" and not job.get("desc"):
        flags.append("JD not read yet")

    total = role_pts + exp_pts + agile_pts + data_pts + bfsi_pts + loc_pts + pay_pts - pen
    # Bonus: title itself mentions data/AI and you have the CDAO background
    if re.search(r"\b(ai|ml|data|analytics|genai)\b", title, re.I):
        total += 4
    total = max(0, min(100, total))
    if total < profile["min_score"]:
        return None

    pretty = {"safe": "SAFe", "jira": "Jira", "ai": "AI", "llm": "LLMs", "genai": "GenAI", "mlops": "MLOps",
              "aws": "AWS", "confluence": "Confluence", "azure devops": "Azure DevOps", "pi planning": "PI planning",
              "artificial intelligence": "AI", "tableau": "Tableau", "alteryx": "Alteryx"}
    overlap = [pretty.get(k, k) for k in a_hits[:3] + [d for d in d_hits if d != "cloud"][:2]]
    if overlap:
        why.append("overlaps on " + ", ".join(dict.fromkeys(overlap)))
    sentence = "; ".join(why)
    sentence = sentence[0].upper() + sentence[1:] + "."

    return {
        "score": int(total),
        "family": family,
        "city": city,
        "why": sentence,
        "flags": list(dict.fromkeys(flags)),
    }
