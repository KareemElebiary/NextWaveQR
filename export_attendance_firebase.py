"""Export Firestore attendees and attendance status to a CSV file.

Set GOOGLE_APPLICATION_CREDENTIALS to a downloaded Firebase service-account JSON
file before running this script. Never commit that JSON file.
"""

import csv
import os
from datetime import datetime
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

PROJECT_ID = "ieee-attendance-abd5b"
OUTPUT_CSV = Path(__file__).with_name("attendance_export.csv")


def format_timestamp(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return "" if value is None else str(value)


def main() -> None:
    credential_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not credential_path:
        raise SystemExit(
            "Set GOOGLE_APPLICATION_CREDENTIALS to your Firebase service-account JSON file."
        )

    firebase_admin.initialize_app(
        credentials.Certificate(credential_path), {"projectId": PROJECT_ID}
    )
    database = firestore.client()
    rows = []

    for document in database.collection("attendees").stream():
        data = document.to_dict()
        rows.append({
            "id": document.id,
            "email": data.get("email", ""),
            "name": data.get("name", ""),
            "ieee_member": data.get("ieeeMember", ""),
            "attended": data.get("attended", False),
            "check_in_time": format_timestamp(data.get("checkInTime")),
        })

    rows.sort(key=lambda row: (str(row["name"]).lower(), str(row["email"]).lower()))
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=rows[0].keys() if rows else [
            "id", "email", "name", "ieee_member", "attended", "check_in_time"
        ])
        writer.writeheader()
        writer.writerows(rows)

    attended = sum(1 for row in rows if row["attended"] is True)
    print(f"Exported {len(rows)} attendees to {OUTPUT_CSV}")
    print(f"Attended: {attended}; Not attended: {len(rows) - attended}")


if __name__ == "__main__":
    main()
