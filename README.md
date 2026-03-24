# Job Application Email Tracker (MVP)

Yes — this repo now includes a lightweight Python CLI app that can track job-application email state.

## What it does

- Ingests exported emails from a JSON file.
- Detects status for each email (`applied`, `interview`, `offer`, `rejected`, `needs_info`, `unknown`).
- Stores data in SQLite.
- Shows a dashboard of the most recent status per company/role.
- Flags potentially unfamiliar terms found in email text.

## Quick start

```bash
python3 job_tracker.py ingest --emails sample_emails.json --db job_tracker.db
python3 job_tracker.py dashboard --db job_tracker.db
```

## Input format

`--emails` should be a JSON array with objects like:

```json
{
  "sender": "talent@example.com",
  "subject": "Interview invitation",
  "body": "Please provide your availability for a call.",
  "date": "2026-03-24T08:30:00+00:00",
  "company": "ExampleCo",
  "role": "Backend Engineer"
}
```

## Next steps for Gmail integration

1. Use Google OAuth and Gmail API (`users.messages.list` + `users.messages.get`) to fetch recent messages.
2. Map Gmail sender/subject/body fields into this script's JSON schema.
3. Run the same `ingest` pipeline.
4. Add labels or auto-replies based on detected status.
