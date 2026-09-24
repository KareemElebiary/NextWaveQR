"""Import the attendee CSV into the Firebase Firestore attendees collection.

Set GOOGLE_APPLICATION_CREDENTIALS to a downloaded Firebase service-account JSON
file before running this script. Never commit that JSON file.
"""

import csv
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

PROJECT_ID = "ieee-attendance-abd5b"
DEFAULT_CSV = Path(__file__).with_name("Attendees - Attendees.csv")
BATCH_SIZE = 400


def as_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1"}


def main() -> None:
    credential_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not credential_path:
        raise SystemExit(
            "Set GOOGLE_APPLICATION_CREDENTIALS to your Firebase service-account JSON file."
        )
    csv_path = Path(os.environ.get("ATTENDEES_CSV", DEFAULT_CSV))
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")

    firebase_admin.initialize_app(
        credentials.Certificate(credential_path), {"projectId": PROJECT_ID}
    )
    database = firestore.client()
    collection = database.collection("attendees")
    batch = database.batch()
    imported = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            attendee_id = str(row.get("id", "")).strip()
            email = str(row.get("email", "")).strip().lower()
            if not attendee_id or not email:
                continue

            data = {
                "email": email,
                "name": str(row.get("name", "")).strip(),
                "ieeeMember": as_bool(row.get("ieee_member", "false")),
                "attended": as_bool(row.get("attended", "false")),
            }
            batch.set(collection.document(attendee_id), data, merge=True)
            imported += 1

            if imported % BATCH_SIZE == 0:
                batch.commit()
                batch = database.batch()

    if imported % BATCH_SIZE:
        batch.commit()
    print(f"Imported {imported} attendees into Firestore collection 'attendees'.")


if __name__ == "__main__":
    main()
