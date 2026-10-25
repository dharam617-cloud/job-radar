# Job Match Radar

Every morning (about 7:15 IST) GitHub Actions scans Naukri and LinkedIn for Senior Scrum Master, Agile Coach, Technical Program Manager, Release Train Engineer and AI/Data Program Manager openings in **Bengaluru, Hyderabad, Delhi NCR and remote India**, scores each one against the profile in `profile.json`, emails a digest, and publishes the dashboard on GitHub Pages. Nothing runs on your laptop.

## One-time setup

1. **Gmail app password**: Google Account → Security → 2-Step Verification → App passwords. Create one called "Job Radar".
2. **Repo secrets**: Settings → Secrets and variables → Actions → New repository secret:
   | Name | Value |
   |---|---|
   | `GMAIL_ADDRESS` | the Gmail address that sends the digest |
   | `GMAIL_APP_PASSWORD` | the 16-character app password |
   | `MAIL_TO` | where the digest goes (comma-separate several) |
3. **Pages**: Settings → Pages → Source: **GitHub Actions**.
4. **First run**: Actions → Job Match Radar → Run workflow (set *days* to 7 for a bigger first batch).

Dashboard: `https://<your-github-username>.github.io/<repo-name>/`

## Changing what it looks for

Edit `profile.json`: search phrases, cities, experience band, pay floor (₹ LPA) and the minimum score. Commit, and the next run uses it.

## How scoring works (0–100)

Role fit 35 · experience band 15 · Agile/SAFe tooling 15 · data and AI overlap 15 · BFSI domain 10 · location and pay 10, minus penalties for PMP-mandatory, hands-on coding and narrow engineering stacks. Listings with disclosed pay under the floor are dropped; hidden pay is kept and flagged. Only scores of 60+ are kept.

## Notes

- Shortlisted / Applied / Skipped marks on the dashboard are stored in the browser you use.
- LinkedIn is read through its public job feed; Naukri through a headless browser. Either site can throttle or block cloud servers on some days; the email and dashboard show a warning when that happens.
- History older than 45 days is pruned.
