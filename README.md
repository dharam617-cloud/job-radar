# Job Match Radar + GCC Job Alert

Every morning at **7:00 AM IST** GitHub Actions scans Naukri and LinkedIn for Senior Scrum Master, Agile Coach / Agile Delivery Lead, Technical Program Manager, Release Train Engineer and AI/Data Program Manager openings. It scores each one against the profile in `profile.json`, then publishes two views and sends two emails. Nothing runs on your laptop.

| | Covers | Dashboard |
|---|---|---|
| **Job Match Radar** | All employers in Bengaluru, Hyderabad, Delhi NCR and remote India, plus GCC roles elsewhere | https://dharam617-cloud.github.io/job-radar/ |
| **GCC Job Alert** | Only Global Capability Centres, across India | https://dharam617-cloud.github.io/job-radar/gcc/ |

- **What counts as a GCC:** a multinational's own India centre, such as JPMorgan, Wells Fargo, Walmart Global Tech, Amgen, Target or Vanguard. IT-services vendors (TCS, Infosys, Accenture, Capgemini…), consultancies and recruiters are not GCCs; they appear only on the Job Match Radar. The company list and sectors are in `radar/gcc.py`.
- **GCCs across India, with first preference:** Bengaluru, Hyderabad and Delhi NCR are searched first and score highest. Pune, Chennai and Mumbai come next, and an India-wide search catches smaller hubs such as Kochi, Coimbatore, Ahmedabad/GIFT City and Kolkata.
- To-apply, Shortlisted, Applied and Skipped marks are shared between the two dashboards (in the same browser).

## One-time setup

1. **Gmail app password**: Google Account → Security → 2-Step Verification → App passwords. Create one called "Job Radar".
2. **Repo secrets**: Settings → Secrets and variables → Actions → New repository secret:
   | Name | Value |
   |---|---|
   | `GMAIL_ADDRESS` | the Gmail address that sends the digest |
   | `GMAIL_APP_PASSWORD` | the 16-character app password |
   | `MAIL_TO` | where the digest goes (comma-separate several) |
3. **Pages**: Settings → Pages → Source: **GitHub Actions**.
4. **First run**: Actions → GCC Job Alert → Run workflow (this one workflow updates both dashboards and sends both emails; set *days* to 7 for a bigger first batch).

## Changing what it looks for

Edit `profile.json`:
- `queries`: the job titles searched
- `cities`: the hub cities searched by name
- `first_preference`: the cities that score highest
- `experience_band`, `pay_floor_lpa` (₹ LPA), `min_score`
- `gcc_only`: set to `true` to drop non-GCC employers from everything

Commit the change and the next run uses it.

**A real GCC isn't on the GCC dashboard?** Each run logs the non-GCC employers it found, and the GCC dashboard lists them under the latest scan. Add the company name under its sector in `radar/gcc.py`.

## How scoring works (0–100)

The weights are:
- Role fit: 35
- Experience band: 15
- Agile/SAFe tooling: 15
- Data and AI overlap: 15
- BFSI domain: 10
- Location and pay: 10. First-preference cities get the full location points, then remote, then Pune, Chennai and Mumbai, then other cities.

Penalties apply when a listing requires PMP, asks for hands-on coding or names a narrow engineering stack. Listings with disclosed pay under the floor are dropped; hidden pay is kept and flagged. Only scores of 60+ are kept. The fit bands are Strong (80+), Good (65–79) and Stretch (60–64).

## Notes

- Roles marked **Curated** were researched by hand on 2 Nov 2026. Confirm each one is still open before you apply.
- LinkedIn is read through its public job feed; Naukri through a headless browser. Either site can throttle or block cloud servers on some days; the email and dashboard show a warning when that happens.
- History older than 45 days is pruned.
