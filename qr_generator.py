"""
IEEE Event Attendee QR Code Generator
======================================
Reads an attendee CSV file (Name, Number/Phone, IEEE Membership status)
and generates:
  1. Unique high-res QR codes for each person (with embedded JSON or text payload)
  2. Optional stylish digital attendee badges/passes
  3. An updated attendees_registry.csv ready to upload to Google Sheets for the future scanner!
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
import pandas as pd
import qrcode
from PIL import Image, ImageDraw, ImageFont

# Ensure UTF-8 output on Windows console for international/Arabic characters
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ==============================================================================
# Helper: Detect Columns Flexibly
# ==============================================================================
def normalize_col_name(col: str) -> str:
    """Strip whitespace, lowercase, and remove special characters."""
    return re.sub(r'[^a-z0-9]', '', str(col).lower())


def detect_columns(df: pd.DataFrame) -> dict:
    """
    Detects required columns from varied header names.
    Returns a dict mapping standard keys ('name', 'number', 'ieee', 'email', 'id')
    to the actual column names in the DataFrame.
    """
    col_mapping = {}
    normalized_cols = {normalize_col_name(c): c for c in df.columns}

    # Patterns (ordered carefully to avoid false positives)
    patterns = {
        'name': ['name', 'fullname', 'attendename', 'personname', 'studentname', 'firstandlastname'],
        'number': ['phonenumber', 'phone', 'mobilenumber', 'mobile', 'number', 'tel', 'whatsapp', 'contact', 'contactnumber'],
        'ieee': ['ieeemember', 'isieeemember', 'isieee', 'member', 'membership', 'membershiptype', 'status'],
        'email': ['emailaddress', 'email', 'mail'],
        'id': ['ticketid', 'passid', 'registrationid', 'regid', 'attendeeid']
    }

    for key, aliases in patterns.items():
        matched = None
        for alias in aliases:
            for norm_c, orig_c in normalized_cols.items():
                if norm_c == alias or alias in norm_c:
                    matched = orig_c
                    break
            if matched:
                break
        if matched:
            col_mapping[key] = matched

    # Sanity check: name and number are the primary identifiers
    missing = []
    if 'name' not in col_mapping:
        missing.append('Name')
    if 'number' not in col_mapping:
        missing.append('Number/Phone')

    if missing:
        raise ValueError(
            f"Could not automatically detect columns for: {', '.join(missing)}.\n"
            f"Available columns in CSV: {list(df.columns)}"
        )

    return col_mapping


def parse_ieee_status(value) -> bool:
    """Parses various IEEE membership representations into a boolean."""
    if pd.isna(value):
        return False
    val_str = str(value).strip().lower()
    return val_str in {'yes', 'y', 'true', '1', 'member', 'ieee', 't', 'active'}


def sanitize_filename(name: str) -> str:
    """Creates a filesystem-safe filename from a person's name or string."""
    clean = re.sub(r'[^\w\s-]', '', str(name)).strip()
    return re.sub(r'[-\s]+', '_', clean)


# ==============================================================================
# QR Code Generator
# ==============================================================================
def generate_qr_image(payload_data: str, box_size: int = 10, border: int = 4) -> Image.Image:
    """
    Generates a high-quality QR code image from the payload string.
    Uses ERROR_CORRECT_M with a standard 4-module quiet zone for maximum scanner compatibility.
    """
    qr = qrcode.QRCode(
        version=None,  # Auto-determine size
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF").convert("RGB")
    return img


# ==============================================================================
# Attendee Event Pass / Badge Generator
# ==============================================================================
def get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Attempts to load a clean modern font, falls back gracefully."""
    font_paths = [
        "C:/Windows/Fonts/segoeui.ttf" if not bold else "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arial.ttf" if not bold else "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibri.ttf" if not bold else "C:/Windows/Fonts/calibrib.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def create_attendee_badge(
    attendee_id: str,
    name: str,
    is_ieee: bool,
    qr_img: Image.Image
) -> Image.Image:
    """
    Renders an elegant digital event pass/badge (650 x 920 px) with:
      - Header branding ("IEEE EVENT PASS")
      - Attendee Name (Phone number removed for privacy)
      - IEEE Membership Pill (Vibrant IEEE Blue for members, Neutral Slate for non-members)
      - Centered framed QR Code
      - Purely Numeric Pass ID (e.g. 1001) and instructions
    """
    card_w, card_h = 650, 920
    badge = Image.new("RGB", (card_w, card_h), "#F8FAFC")
    draw = ImageDraw.Draw(badge)

    # 1. Header background banner (Deep Navy)
    header_h = 165
    draw.rectangle([(0, 0), (card_w, header_h)], fill="#0B192C")

    # Header decorative accent line
    accent_color = "#00629B" if is_ieee else "#3B82F6"
    draw.rectangle([(0, header_h - 6), (card_w, header_h)], fill=accent_color)

    # Header typography
    font_header_sub = get_font(13, bold=True)
    font_header_title = get_font(30, bold=True)

    draw.text((card_w // 2, 42), "OFFICIAL EVENT ATTENDANCE PASS", fill="#94A3B8", font=font_header_sub, anchor="mm")
    draw.text((card_w // 2, 92), "IEEE REGISTRATION", fill="#FFFFFF", font=font_header_title, anchor="mm")

    # 2. IEEE Member Pill Badge
    pill_y = header_h + 30
    pill_h = 36
    pill_w = 210 if is_ieee else 230
    pill_x0 = (card_w - pill_w) // 2
    pill_x1 = pill_x0 + pill_w
    pill_bg = "#00629B" if is_ieee else "#E2E8F0"
    pill_fg = "#FFFFFF" if is_ieee else "#475569"
    pill_text = "★ IEEE MEMBER" if is_ieee else "• GUEST / NON-MEMBER"
    font_pill = get_font(14, bold=True)

    draw.rounded_rectangle([(pill_x0, pill_y), (pill_x1, pill_y + pill_h)], radius=18, fill=pill_bg)
    draw.text((card_w // 2, pill_y + (pill_h // 2)), pill_text, fill=pill_fg, font=font_pill, anchor="mm")

    # 3. Attendee Name (Prominent & cleanly centered)
    font_name = get_font(34, bold=True)
    name_y = pill_y + pill_h + 38
    disp_name = name if len(name) <= 30 else name[:28] + "..."
    draw.text((card_w // 2, name_y), disp_name, fill="#0F172A", font=font_name, anchor="mm")

    # 4. QR Code Card Container
    qr_card_w, qr_card_h = 430, 430
    qr_card_x0 = (card_w - qr_card_w) // 2
    qr_card_y0 = name_y + 36
    qr_card_x1 = qr_card_x0 + qr_card_w
    qr_card_y1 = qr_card_y0 + qr_card_h

    # Card background & soft border
    draw.rounded_rectangle(
        [(qr_card_x0, qr_card_y0), (qr_card_x1, qr_card_y1)],
        radius=20,
        fill="#FFFFFF",
        outline="#E2E8F0",
        width=2
    )

    # Resize QR code to fit neatly inside the card container with breathing room
    target_qr_size = 370
    resized_qr = qr_img.resize((target_qr_size, target_qr_size), Image.Resampling.LANCZOS)
    qr_pos_x = qr_card_x0 + (qr_card_w - target_qr_size) // 2
    qr_pos_y = qr_card_y0 + (qr_card_h - target_qr_size) // 2
    badge.paste(resized_qr, (qr_pos_x, qr_pos_y))

    # 5. Footer Info & Purely Numeric Pass ID (e.g. 1001)
    font_id = get_font(18, bold=True)
    font_instruct = get_font(13, bold=False)

    footer_y1 = qr_card_y1 + 34
    draw.text((card_w // 2, footer_y1), f"PASS ID: {attendee_id}", fill="#1E293B", font=font_id, anchor="mm")

    footer_y2 = footer_y1 + 25
    draw.text((card_w // 2, footer_y2), "Present this QR pass at the entrance for attendance verification", fill="#94A3B8", font=font_instruct, anchor="mm")

    # Subtle outer border for the entire badge
    draw.rounded_rectangle([(0, 0), (card_w - 1, card_h - 1)], radius=12, outline="#CBD5E1", width=1)

    return badge


# ==============================================================================
# Main Batch Processing Function
# ==============================================================================
def process_attendees(
    csv_path: str,
    output_dir: str = "output",
    payload_format: str = "json",
    create_badges: bool = True
) -> dict:
    """
    Processes the attendee CSV file:
      1. Generates unique QR code for each attendee with Name, Number, and IEEE status.
      2. Saves high-res QR code PNGs.
      3. (Optional) Generates stylish event pass badges with numeric pass IDs.
      4. Exports an updated registry CSV ready for Google Sheets & Email sending.
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path, dtype=str, index_col=False)
    if df.empty:
        raise ValueError("The provided CSV file is empty.")

    col_map = detect_columns(df)
    out_dir = Path(output_dir)
    qr_dir = out_dir / "qr_codes"
    badge_dir = out_dir / "badges"

    qr_dir.mkdir(parents=True, exist_ok=True)
    if create_badges:
        badge_dir.mkdir(parents=True, exist_ok=True)

    records = []
    total = len(df)

    print(f"\nProcessing {total} attendees from: {csv_file.name}")
    print(f"Detected columns: Name='{col_map['name']}', Number='{col_map['number']}', IEEE='{col_map.get('ieee', 'N/A')}', Email='{col_map.get('email', 'N/A')}'")
    print(f"Output directory: {out_dir.resolve()}\n")

    for i, (_, row) in enumerate(df.iterrows()):
        name = str(row[col_map['name']]).strip()
        number = str(row[col_map['number']]).strip()
        is_ieee = parse_ieee_status(row[col_map['ieee']]) if 'ieee' in col_map else False
        email = str(row[col_map['email']]).strip() if 'email' in col_map and not pd.isna(row[col_map['email']]) else ""

        # Unique ID: Purely numeric (e.g. 1001, 1002...) or use existing numeric ID
        if 'id' in col_map and not pd.isna(row[col_map['id']]) and str(row[col_map['id']]).strip().isdigit():
            attendee_id = str(row[col_map['id']]).strip()
        else:
            attendee_id = str(1001 + i)

        # Clean name for filenames
        clean_name = sanitize_filename(name)
        file_prefix = f"{attendee_id}_{clean_name}"

        # Structured QR Payload
        if payload_format.lower() == "text":
            payload_str = (
                f"ID: {attendee_id}\n"
                f"Name: {name}\n"
                f"Number: {number}\n"
                f"IEEE Member: {'Yes' if is_ieee else 'No'}"
            )
        else:
            # Default: structured JSON (ideal for the future Google Sheets scanner!)
            payload_data = {
                "id": attendee_id,
                "name": name,
                "number": number,
                "ieee_member": is_ieee
            }
            if email:
                payload_data["email"] = email
            payload_str = json.dumps(payload_data, ensure_ascii=False)

        # 1. Generate QR Code
        qr_img = generate_qr_image(payload_str, box_size=10, border=4)
        qr_filename = f"{file_prefix}_qr.png"
        qr_filepath = qr_dir / qr_filename
        qr_img.save(qr_filepath, format="PNG")

        badge_filename = ""
        # 2. Generate Event Badge
        if create_badges:
            badge_img = create_attendee_badge(
                attendee_id=attendee_id,
                name=name,
                is_ieee=is_ieee,
                qr_img=qr_img
            )
            badge_filename = f"{file_prefix}_badge.png"
            badge_filepath = badge_dir / badge_filename
            badge_img.save(badge_filepath, format="PNG")

        # Record for Google Sheets registry and email sender
        records.append({
            "ID": attendee_id,
            "Name": name,
            "Number": number,
            "IEEE_Member": "Yes" if is_ieee else "No",
            "Email": email,
            "QR_File": qr_filename,
            "Badge_File": badge_filename,
            "Attended": "No",              # Ready for Google Sheets attendance marking
            "Check_In_Time": "",           # Ready for scanner timestamp
            "Email_Sent_Status": "Pending",# Ready for Email sender tracking
            "Email_Sent_Time": "",
            "QR_Payload": payload_str
        })

        ieee_label = "[IEEE Member]" if is_ieee else "[Non-Member]"
        print(f" [{i + 1}/{total}] Generated Pass #{attendee_id}: {name} {ieee_label}")

    # 3. Export Registry CSV (Perfect for importing into Google Sheets)
    registry_df = pd.DataFrame(records)
    registry_path = out_dir / "attendees_registry.csv"
    registry_df.to_csv(registry_path, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 60)
    print("Generation Completed Successfully!")
    print(f"Total QR codes generated: {len(records)}")
    print(f"QR images saved to:       {qr_dir.resolve()}")
    if create_badges:
        print(f"Badges saved to:          {badge_dir.resolve()}")
    print(f"Google Sheets Registry:   {registry_path.resolve()}")
    print("=" * 60 + "\n")

    return {
        "total": len(records),
        "qr_dir": str(qr_dir),
        "badge_dir": str(badge_dir) if create_badges else None,
        "registry_csv": str(registry_path)
    }


def create_sample_csv(target_path: str = "sample_attendees.csv") -> str:
    """Creates a sample CSV file to get started quickly."""
    data = """Name,Number,IEEE_Member,Email
Ahmed Hassan,+201012345678,Yes,ahmed.hassan@example.com
Sara Mohamed,+201123456789,No,sara.mohamed@example.com
Omar Khaled,+201234567890,Yes,omar.khaled@example.com
Mariam Ali,+201545678901,No,mariam.ali@example.com
Youssef Ibrahim,+201098765432,Yes,youssef.ibrahim@example.com
Nour El-Din,+201187654321,No,nour.eldin@example.com
"""
    p = Path(target_path)
    p.write_text(data, encoding="utf-8")
    print(f"Created sample CSV: {p.resolve()}")
    return str(p.resolve())


# ==============================================================================
# CLI Entry Point
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Generate unique QR codes and event passes for attendees from a CSV file."
    )
    parser.add_argument(
        "-c", "--csv",
        dest="csv_path",
        help="Path to the attendees .csv file."
    )
    parser.add_argument(
        "-o", "--output",
        dest="output_dir",
        default="output_qrs",
        help="Directory to save generated QR codes and badges (default: output_qrs)."
    )
    parser.add_argument(
        "-f", "--format",
        dest="format",
        choices=["json", "text"],
        default="json",
        help="QR payload format: 'json' (recommended for scanner integration) or 'text'."
    )
    parser.add_argument(
        "--no-badges",
        dest="create_badges",
        action="store_false",
        help="Only generate raw QR codes, skip attendee badge cards."
    )
    parser.add_argument(
        "--create-sample",
        action="store_true",
        help="Generate a sample attendees.csv file in the current directory."
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch graphical user interface."
    )

    args = parser.parse_args()

    if args.create_sample:
        create_sample_csv("sample_attendees.csv")
        return

    if args.gui:
        try:
            import gui
            gui.launch_gui()
            return
        except ImportError:
            from gui_app import launch_gui
            launch_gui()
            return

    # If no CSV path is specified, check if event CSV or sample_attendees.csv exists
    csv_path = args.csv_path
    if not csv_path:
        for candidate in ["Next Wave II - Form Responses 1.csv", "attendees.csv", "sample_attendees.csv"]:
            if os.path.exists(candidate):
                csv_path = candidate
                print(f"No --csv specified, auto-detected: {candidate}")
                break

    if not csv_path:
        print("Error: Please provide a CSV file using --csv <filename> or run with --gui.")
        print("Example: python qr_generator.py --csv sample_attendees.csv")
        print("Or generate a sample CSV with: python qr_generator.py --create-sample")
        sys.exit(1)

    process_attendees(
        csv_path=csv_path,
        output_dir=args.output_dir,
        payload_format=args.format,
        create_badges=args.create_badges
    )


if __name__ == "__main__":
    main()
