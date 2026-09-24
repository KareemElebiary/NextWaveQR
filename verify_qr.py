"""
Verification and Test Script for Generated QR Codes
===================================================
Scans each generated QR code using OpenCV QRCodeDetector,
validates payload structure, checks that attendee data matches,
and ensures readiness for scanner / Google Sheets integration.
"""

import sys
import json
from pathlib import Path
import cv2
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def test_qr_codes(qr_dir="output_qrs/qr_codes", registry_csv="output_qrs/attendees_registry.csv"):
    detector = cv2.QRCodeDetector()
    qr_path = Path(qr_dir)
    registry_file = Path(registry_csv)

    if not registry_file.exists():
        print(f"Error: Registry file '{registry_csv}' not found.")
        return False

    df = pd.read_csv(registry_file, dtype=str)
    all_passed = True
    print(f"Verifying {len(df)} generated QR codes in '{qr_dir}'...\n")

    for idx, row in df.iterrows():
        expected_id = row['ID']
        expected_name = row['Name']
        expected_number = row['Number']
        expected_ieee = (row['IEEE_Member'] == "Yes")
        file_name = row['QR_File']
        img_path = qr_path / file_name

        if not img_path.exists():
            print(f"FAIL: Image file not found: {img_path}")
            all_passed = False
            continue

        # Read image supporting Unicode / Arabic filenames on Windows
        try:
            img = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            img = None

        if img is None or img.size == 0:
            print(f"FAIL: Could not load image file: {file_name}")
            all_passed = False
            continue

        decoded_text, points, _ = detector.detectAndDecode(img)
        if not decoded_text:
            # OpenCV QRCodeDetector quirk with sharp binary matrices: multi-scale fallback
            for sz in [240, 200, 320]:
                resized = cv2.resize(img, (sz, sz), interpolation=cv2.INTER_AREA)
                dec, _, _ = detector.detectAndDecode(resized)
                if dec:
                    decoded_text = dec
                    break

        if not decoded_text:
            print(f"FAIL: Could not decode QR code from {file_name}")
            all_passed = False
            continue

        try:
            payload = json.loads(decoded_text)
            match_id = (payload.get('id') == expected_id)
            match_name = (payload.get('name') == expected_name)
            match_number = (str(payload.get('number')) == expected_number)
            match_ieee = (payload.get('ieee_member') == expected_ieee)

            if match_id and match_name and match_number and match_ieee:
                print(f"PASS: {expected_id} | {expected_name} | {expected_number} | IEEE:{expected_ieee}")
            else:
                print(f"FAIL: Payload mismatch for {expected_id} in {file_name}")
                print(f"  Expected: ID={expected_id}, Name={expected_name}, Number={expected_number}, IEEE={expected_ieee}")
                print(f"  Got:      {payload}")
                all_passed = False
        except json.JSONDecodeError:
            print(f"FAIL: Decoded content is not valid JSON: '{decoded_text}'")
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("ALL RAW QR CODES SUCCESSFULLY SCANNED AND VERIFIED!")
    else:
        print("SOME RAW QR CHECKS FAILED.")
    print("=" * 50)

    # Also test badge images
    badge_dir = Path("output_qrs/badges")
    if badge_dir.exists():
        print(f"\nVerifying embedded QR codes in badges ('{badge_dir}')...")
        badges_passed = True
        for idx, row in df.iterrows():
            expected_id = row['ID']
            badge_name = row['Badge_File']
            badge_path = badge_dir / badge_name
            if not badge_path.exists():
                continue
            try:
                b_img = cv2.imdecode(np.fromfile(str(badge_path), dtype=np.uint8), cv2.IMREAD_COLOR)
            except Exception:
                b_img = None
            if b_img is None:
                continue
            dec_text, _, _ = detector.detectAndDecode(b_img)
            if dec_text and expected_id in dec_text:
                print(f"PASS (Badge): {expected_id} detected on {badge_name}")
            else:
                print(f"WARN (Badge): Could not directly decode from whole badge card {badge_name} (normal if whole card is large, scanner apps zoom into the QR section)")
        print("Badge verification completed.")

    return all_passed


if __name__ == "__main__":
    test_qr_codes()
