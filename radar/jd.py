"""Turn a job description into a few bullet points and the interview themes it touches.

No AI service is needed: bullets are the JD's own lines that say what the job does or needs,
boilerplate removed. Themes are matched by keywords and drive the interview-prep questionnaire
(docs/data/questions.json uses the same theme keys).
"""
from __future__ import annotations

import re

THEMES: list[tuple[str, str, re.Pattern]] = [
    ("safe", "SAFe & scaled agile", re.compile(r"\bsafe\b|scaled agile|pi planning|release train|\bart\b|program increment|lean portfolio|big room", re.I)),
    ("scrum", "Scrum ceremonies & team coaching", re.compile(r"ceremon|stand-?ups?|retrospective|sprint|backlog|scrum|coach|servant leader|kanban", re.I)),
    ("risk", "Dependencies, risks & RAID", re.compile(r"dependenc|\braid\b|risks?\b|impediment|blocker|escalat|mitigat", re.I)),
    ("stakeholders", "Stakeholder & executive communication", re.compile(r"stakeholder|executive|senior leader|c-suite|status report|steering|influenc", re.I)),
    ("metrics", "Delivery metrics & predictability", re.compile(r"metric|\bkpis?\b|velocity|burn-?(down|up)|predictab|throughput|cycle time|\bokrs?\b|flow", re.I)),
    ("planning", "Program planning, roadmaps & milestones", re.compile(r"roadmap|milestone|program plan|timeline|\bscope\b|portfolio|end-to-end|release plan|schedule", re.I)),
    ("release", "Release, change & production readiness", re.compile(r"release|deploy|change management|cutover|go-live|production|ci/?cd|devops", re.I)),
    ("ai", "AI / GenAI / ML programs", re.compile(r"\bai\b|genai|generative|\bllms?\b|machine learning|\bml\b|mlops|agentic|\bmodels?\b", re.I)),
    ("data", "Data platforms & governance", re.compile(r"data (platform|governance|quality|pipeline|catalog|management|product)|analytics|lakehouse|warehouse|metadata|tableau|snowflake|databricks", re.I)),
    ("cloud", "Cloud & platform modernisation", re.compile(r"cloud|\baws\b|azure|\bgcp\b|migration|moderni[sz]|microservice|kubernetes|platform", re.I)),
    ("security", "Security, risk & compliance", re.compile(r"security|vulnerab|cyber|\biam\b|identity|compliance|regulat|audit|controls?\b|gdpr", re.I)),
    ("people", "People leadership & hiring", re.compile(r"\bhire\b|hiring|people manag|direct reports|mentor|line manag|performance review|build (the|a) team|manage a team", re.I)),
    ("transformation", "Agile transformation & ways of working", re.compile(r"transformation|ways of working|agile adoption|maturity|change agent|operating model|\blean\b|continuous improvement", re.I)),
    ("resourcing", "Budget, vendors & resourcing", re.compile(r"budget|vendor|\bcosts?\b|financial track|resourc|capacity|forecast", re.I)),
    ("bfsi", "Banking & financial-services domain", re.compile(r"\bbank|financial services|payments|capital market|wealth|insurance|fintech|trading|credit|fraud", re.I)),
    ("tools", "Jira / Confluence / ADO tooling", re.compile(r"\bjira\b|confluence|azure devops|\bado\b|\brally\b|smartsheet|ms project", re.I)),
]
THEME_LABELS = {k: label for k, label, _ in THEMES}

BOILER = re.compile(
    r"equal opportunit|e-verify|accommodation|disabilit|veteran|gender identity|sexual orientation|race, colou?r|"
    r"benefits|insurance cover|paid time off|\bpto\b|wellness|salary range|compensation|apply now|click apply|"
    r"about (us|the company|our company)|founded in|our mission|we are (a|an|the) (leading|global)|headquarter|"
    r"privacy|cookie|recruitment fraud|do not pay|job id|requisition|posted on|work model|hybrid work schedule|"
    r"visa sponsorship|background check|drug test|fortune \d+|great place to work|follow us",
    re.I)
SIGNAL = re.compile(
    r"\b(lead|drive|manage|own|facilitat|coach|coordinat|partner|deliver|define|track|report|ensure|plan|align|"
    r"build|establish|govern|mentor|remove|escalat|communicat|experience|years|certif|knowledge|understanding|"
    r"proficien|ability|skill|familiar|background|degree|must|required|preferred)\w*", re.I)


def _split(desc: str) -> list[str]:
    if "•" in desc:
        parts = desc.split("•")
    else:
        parts = re.split(r"(?<=[.;!?])\s+(?=[A-Z])", desc)
    out = []
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip(" -–:;,.")
        p = re.sub(r"^(responsibilities|requirements|qualifications|what you('| wi)ll (do|bring)|key responsibilities|"
                   r"role & responsibilities|about the role|job description|must-have skills|nice to have|criteria)\s*:?\s*",
                   "", p, flags=re.I)
        if 25 <= len(p) <= 400:
            out.append(p if len(p) <= 220 else p[:217].rsplit(" ", 1)[0] + "…")
    return out


def extract_points(desc: str, limit: int = 7) -> list[str]:
    """The JD's most informative lines, in their original order."""
    if not desc:
        return []
    desc = re.sub(r"\s*Criteria:.*$", "", desc)
    lines = [l for l in _split(desc) if not BOILER.search(l)]
    scored = []
    for i, l in enumerate(lines):
        s = len(SIGNAL.findall(l)) + 2 * sum(1 for _, _, pat in THEMES if pat.search(l))
        if s >= 2:
            scored.append((s, i, l))
    keep = sorted(sorted(scored, key=lambda x: -x[0])[:limit], key=lambda x: x[1])
    seen, out = set(), []
    for _, _, l in keep:
        k = l.lower()[:60]
        if k not in seen:
            seen.add(k)
            out.append(l)
    return out


def themes_of(*texts: str) -> list[str]:
    text = " ".join(t for t in texts if t)
    return [k for k, _, pat in THEMES if pat.search(text)]
