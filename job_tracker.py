#!/usr/bin/env python3
"""Simple job application email tracker.

This script can:
- ingest emails from a JSON file
- classify each message into a pipeline state
- track the latest status for each company/role pair
- flag unfamiliar terms from email text
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_DB = "job_tracker.db"


STATUS_PATTERNS: dict[str, list[str]] = {
    "applied": [
        r"thank(s| you) for applying",
        r"application (received|submitted)",
        r"we have received your application",
    ],
    "interview": [
        r"interview",
        r"schedule (a )?(call|screen)",
        r"next round",
    ],
    "offer": [
        r"offer",
        r"compensation package",
        r"background check",
    ],
    "rejected": [
        r"(won'?t|will not) be moving forward",
        r"we (have )?decided to (move )?forward with other candidates",
        r"regret to inform",
    ],
    "needs_info": [
        r"please provide",
        r"additional information",
        r"complete (the )?assessment",
        r"follow-up questions",
    ],
    "unknown": [],
}


DEFAULT_GLOSSARY = {
    "ats",
    "sponsorship",
    "leetcode",
    "take-home",
    "icp",
    "okr",
    "sde",
    "kpi",
}


@dataclass
class EmailRecord:
    sender: str
    subject: str
    body: str
    date: str
    company: str
    role: str


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            detected_status TEXT NOT NULL,
            unknown_terms TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE VIEW IF NOT EXISTS latest_job_status AS
        SELECT e.company,
               e.role,
               e.detected_status,
               e.sent_at,
               e.unknown_terms
        FROM emails e
        JOIN (
            SELECT company, role, MAX(sent_at) AS max_sent_at
            FROM emails
            GROUP BY company, role
        ) latest
        ON latest.company = e.company
           AND latest.role = e.role
           AND latest.max_sent_at = e.sent_at;
        """
    )


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def detect_status(subject: str, body: str) -> str:
    text = normalize_text(f"{subject} {body}")
    for status, patterns in STATUS_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text):
                return status
    return "unknown"


def extract_unknown_terms(body: str, glossary: set[str]) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]{1,}", body.lower())
    candidates = {w for w in words if len(w) > 2 and w not in glossary}
    all_known = glossary | {
        "the",
        "and",
        "for",
        "your",
        "with",
        "this",
        "that",
        "you",
        "are",
        "will",
        "have",
        "our",
        "from",
        "team",
        "application",
        "interview",
        "role",
        "job",
        "candidate",
    }
    return sorted(w for w in candidates if w not in all_known)[:12]


def parse_email_json(path: Path) -> Iterable[EmailRecord]:
    raw = json.loads(path.read_text())
    for item in raw:
        yield EmailRecord(
            sender=item["sender"],
            subject=item["subject"],
            body=item["body"],
            date=item.get("date", datetime.now(timezone.utc).isoformat()),
            company=item["company"],
            role=item["role"],
        )


def load_glossary(path: Path | None) -> set[str]:
    if not path:
        return set(DEFAULT_GLOSSARY)
    terms = {line.strip().lower() for line in path.read_text().splitlines() if line.strip()}
    return set(DEFAULT_GLOSSARY) | terms


def ingest_emails(db_path: Path, emails_path: Path, glossary_path: Path | None) -> None:
    glossary = load_glossary(glossary_path)
    with sqlite3.connect(db_path) as conn:
        init_db(conn)
        for email in parse_email_json(emails_path):
            status = detect_status(email.subject, email.body)
            unknown_terms = extract_unknown_terms(email.body, glossary)
            conn.execute(
                """
                INSERT INTO emails(
                    sender, subject, body, sent_at, company, role,
                    detected_status, unknown_terms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email.sender,
                    email.subject,
                    email.body,
                    email.date,
                    email.company,
                    email.role,
                    status,
                    ", ".join(unknown_terms),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )


def print_dashboard(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        init_db(conn)
        rows = conn.execute(
            """
            SELECT company, role, detected_status, sent_at, unknown_terms
            FROM latest_job_status
            ORDER BY sent_at DESC
            """
        ).fetchall()

    if not rows:
        print("No job-tracking data yet. Ingest emails first.")
        return

    print("\n=== Job Application Dashboard ===")
    for company, role, status, sent_at, unknown in rows:
        unknown_display = unknown if unknown else "-"
        print(f"- {company} | {role} | status={status} | last_email={sent_at}")
        print(f"  unfamiliar_terms: {unknown_display}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track job-application emails")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Ingest emails from JSON")
    ingest.add_argument("--emails", required=True, type=Path, help="JSON array of email objects")
    ingest.add_argument("--db", default=Path(DEFAULT_DB), type=Path, help="SQLite file")
    ingest.add_argument("--glossary", type=Path, help="Optional newline-delimited term list")

    dash = sub.add_parser("dashboard", help="Show current status by company/role")
    dash.add_argument("--db", default=Path(DEFAULT_DB), type=Path, help="SQLite file")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        ingest_emails(args.db, args.emails, args.glossary)
        print(f"Ingested emails from {args.emails} into {args.db}")
    elif args.command == "dashboard":
        print_dashboard(args.db)


if __name__ == "__main__":
    main()
