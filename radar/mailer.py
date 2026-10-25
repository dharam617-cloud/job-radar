"""Send the daily digest from the user's own Gmail using an app password."""
from __future__ import annotations

import html
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _band(s: int) -> tuple[str, str, str]:
    if s >= 80:
        return "Strong", "#1e7a4f", "#e2f2ea"
    if s >= 65:
        return "Good", "#9a6a10", "#f7eed9"
    return "Stretch", "#5b6b78", "#eef1f3"


def build_html(new_jobs: list[dict], run: dict, dashboard_url: str, total_active: int) -> str:
    e = html.escape
    top = sorted(new_jobs, key=lambda j: -j["score"])[:15]
    strong = sum(1 for j in new_jobs if j["score"] >= 80)
    rows = []
    for j in top:
        label, fg, bg = _band(j["score"])
        rows.append(f"""
<tr><td style="padding:14px 0;border-top:1px solid #dde3e8;vertical-align:top;width:58px">
  <div style="font:600 18px/1 'IBM Plex Mono',Menlo,monospace;color:{fg};background:{bg};border-radius:8px;padding:10px 0;text-align:center;width:52px">{j['score']}</div>
  <div style="font:600 10px/1.6 Arial,sans-serif;color:{fg};text-transform:uppercase;letter-spacing:.06em;text-align:center;width:52px">{label}</div>
</td><td style="padding:14px 0 14px 14px;border-top:1px solid #dde3e8;vertical-align:top">
  <a href="{e(j['url'])}" style="font:600 16px/1.3 Arial,sans-serif;color:#1f5f8b;text-decoration:none">{e(j['title'])}</a>
  <div style="font:14px/1.5 Arial,sans-serif;color:#152330;margin-top:3px"><b>{e(j['company'])}</b> &middot; {e(j['city'])} &middot; {e(j['source'])}{(' &middot; ' + e(j['exp'])) if j.get('exp') else ''}{(' &middot; ' + e(j['salary'])) if j.get('salary') else ''}</div>
  <div style="font:13.5px/1.5 Arial,sans-serif;color:#5b6b78;margin-top:4px">{e(j['why'])}</div>
</td></tr>""")
    health = []
    for name, s in run["sources"].items():
        if not s.get("ok"):
            health.append(f"{name}: {e(s.get('error') or 'no results')}")
    health_html = (f'<p style="font:13px/1.5 Arial,sans-serif;color:#9a6a10;background:#f7eed9;padding:10px 12px;border-radius:8px">'
                   f'Heads-up: {"; ".join(health)}. Results from that site may be missing today.</p>') if health else ""
    body = (f"<table role='presentation' cellpadding='0' cellspacing='0' width='100%'>{''.join(rows)}</table>"
            if rows else '<p style="font:15px/1.5 Arial,sans-serif;color:#152330">No new openings cleared the bar today. Your earlier matches are still on the dashboard.</p>')
    more = (f'<p style="font:13.5px Arial,sans-serif;color:#5b6b78">Showing the top 15 of {len(new_jobs)} new matches.</p>'
            if len(new_jobs) > 15 else "")
    return f"""<!doctype html><html><body style="margin:0;background:#f3f5f7">
<div style="max-width:640px;margin:0 auto;padding:24px 18px;background:#ffffff">
  <div style="font:12px Arial,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#5b6b78">Job Match Radar &middot; {e(run['date_label'])}</div>
  <h1 style="font:700 24px/1.2 Arial,sans-serif;color:#152330;margin:6px 0 4px">{len(new_jobs)} new match{'es' if len(new_jobs) != 1 else ''}, {strong} strong</h1>
  <p style="font:14px/1.5 Arial,sans-serif;color:#5b6b78;margin:0 0 16px">Naukri + LinkedIn &middot; Bengaluru, Hyderabad, Delhi NCR and remote India &middot; {run['scanned']} listings checked &middot; {total_active} open matches on your dashboard</p>
  {health_html}
  {body}
  {more}
  <p style="margin:22px 0 6px"><a href="{e(dashboard_url)}" style="display:inline-block;background:#1f5f8b;color:#ffffff;font:600 14px Arial,sans-serif;padding:11px 18px;border-radius:8px;text-decoration:none">Open the dashboard</a></p>
  <p style="font:12px/1.5 Arial,sans-serif;color:#8a95a0;margin-top:18px">Scores weigh role fit, experience band, Agile/SAFe and data/AI overlap, BFSI domain, and pay against your &#8377;50 LPA floor. Listings that hide pay are kept.</p>
</div></body></html>"""


def send(sender: str, app_password: str, to: str, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Job Match Radar <{sender}>"
    msg["To"] = to
    msg.attach(MIMEText("Open this email in an HTML-capable client to see your matches.", "plain"))
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(sender, app_password)
        s.sendmail(sender, [a.strip() for a in to.split(",")], msg.as_string())
