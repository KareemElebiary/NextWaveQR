"""
IEEE Event Attendee Email Sender with Anti-Spam Deliverability
=============================================================
Sends personalized event passes/badges to attendees via SMTP (Gmail, Outlook, University, etc.)

Anti-Spam Best Practices Included:
  1. RFC 5322 Compliant Headers (Message-ID, Date, Return-Path, Friendly From)
  2. Dual MIME Multipart (Plain-text fallback + Responsive HTML)
  3. Inline CID Badge Image Embedding (avoids 'image-only' spam triggers)
  4. Balanced text-to-image ratio with professional event instructions
  5. Throttled sending delay (2-3s pacing) to avoid bot/burst detection
  6. Idempotent / Resume support: Updates attendees_registry.csv live
  7. Test Mode: Allows sending a test email to your own address first
"""

import os
import sys
import time
import uuid
import smtplib
import argparse
from pathlib import Path
from email.utils import formatdate, make_msgid, formataddr
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
import pandas as pd

# UTF-8 console output for Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ==============================================================================
# SMTP Configuration Helper
# ==============================================================================
DEFAULT_SMTP_CONFIGS = {
    "gmail": {
        "host": "smtp.gmail.com",
        "port": 587,
        "use_tls": True
    },
    "outlook": {
        "host": "smtp.office365.com",
        "port": 587,
        "use_tls": True
    },
    "ejust": {
        "host": "smtp.gmail.com",  # E-JUST uses Google Workspace
        "port": 587,
        "use_tls": True
    }
}


def load_env_credentials():
    """Attempts to load credentials from a .env file if present."""
    config = {
        "sender_email": os.environ.get("SENDER_EMAIL", ""),
        "sender_password": os.environ.get("SENDER_PASSWORD", ""),
        "smtp_host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": int(os.environ.get("SMTP_PORT", 587)),
        "sender_name": os.environ.get("SENDER_NAME", "Kareem Elebairy | IEEE Computer Society"),
        "event_name": os.environ.get("EVENT_NAME", "Next Wave II")
    }

    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k == "SENDER_EMAIL":
                config["sender_email"] = v
            elif k == "SENDER_PASSWORD":
                config["sender_password"] = v
            elif k == "SMTP_HOST":
                config["smtp_host"] = v
            elif k == "SMTP_PORT":
                config["smtp_port"] = int(v)
            elif k == "SENDER_NAME":
                config["sender_name"] = v
            elif k == "EVENT_NAME":
                config["event_name"] = v

    return config


# ==============================================================================
# Email Composition (Anti-Spam Optimized)
# ==============================================================================
def compose_pass_email(
    sender_email: str,
    sender_name: str,
    attendee_name: str,
    attendee_email: str,
    pass_id: str,
    is_ieee: bool,
    badge_image_path: str,
    event_name: str = "Next Wave II"
) -> MIMEMultipart:
    """
    Constructs an RFC-compliant multipart email with:
      - Plain text body alternative
      - Styled responsive HTML body
      - Inline CID embedded pass badge
      - Attached badge PNG file
      - Kareem Elebairy's official IEEE Computer Society signature
    """
    msg_root = MIMEMultipart("related")

    # Anti-spam RFC 5322 Headers
    domain = sender_email.split("@")[-1] if "@" in sender_email else "ieee.org"
    msg_root["Message-ID"] = make_msgid(idstring=f"pass-{pass_id}-{uuid.uuid4().hex[:6]}", domain=domain)
    msg_root["Date"] = formatdate(localtime=True)
    msg_root["From"] = formataddr((sender_name, sender_email))
    msg_root["To"] = formataddr((attendee_name, attendee_email))
    msg_root["Reply-To"] = sender_email
    msg_root["Subject"] = f"{event_name} - Your Official Event Pass (Pass #{pass_id})"
    msg_root["X-Mailer"] = "IEEE-CS-Pass-Mailer/2.0"
    msg_root["MIME-Version"] = "1.0"

    # Encapsulated alternative part (text + html)
    msg_alternative = MIMEMultipart("alternative")
    msg_root.attach(msg_alternative)

    status_str = "IEEE Member" if is_ieee else "Guest / Non-Member"
    first_name = attendee_name.split()[0] if attendee_name else "Attendee"

    # 1. Plain Text Alternative (High-reputation email requirement)
    plain_text = f"""Dear {first_name},

Thank you for registering for {event_name}!

We are pleased to confirm your registration. Your official event pass has been generated and is attached to this email.

EVENT PASS DETAILS:
-------------------
• Attendee Name: {attendee_name}
• Pass ID: {pass_id}
• Status: {status_str}

CHECK-IN INSTRUCTIONS:
Please keep this email or save the attached pass image on your phone. Present the QR code at the registration desk for rapid check-in upon arrival.

If you have any questions, feel free to reply directly to this email.

We look forward to welcoming you!

Best regards,
Kareem Elebairy
IEEE Computer Society Vice Chair
"""
    msg_alternative.attach(MIMEText(plain_text, "plain", "utf-8"))

    # 2. Rich HTML Body with Inline Pass Display
    status_badge_bg = "#00629B" if is_ieee else "#E2E8F0"
    status_badge_fg = "#FFFFFF" if is_ieee else "#334155"
    status_icon = "★" if is_ieee else "•"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{event_name} Event Pass</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1E293B;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #F8FAFC; padding: 30px 10px;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table role="presentation" width="100%" style="max-width: 580px; background-color: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.06); border: 1px solid #E2E8F0;" cellspacing="0" cellpadding="0">
          
          <!-- Banner Header -->
          <tr>
            <td style="background-color: #0B192C; padding: 28px 24px; text-align: center; border-bottom: 4px solid #00629B;">
              <p style="margin: 0; font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; color: #94A3B8; font-weight: 700;">IEEE Computer Society</p>
              <h1 style="margin: 6px 0 0 0; font-size: 24px; color: #FFFFFF; font-weight: 700;">{event_name}</h1>
              <p style="margin: 4px 0 0 0; font-size: 14px; color: #CBD5E1;">Official Registration Confirmation</p>
            </td>
          </tr>

          <!-- Body Content -->
          <tr>
            <td style="padding: 28px 26px;">
              <p style="margin: 0 0 16px 0; font-size: 16px; line-height: 1.5; color: #0F172A;">
                Dear <strong>{attendee_name}</strong>,
              </p>
              <p style="margin: 0 0 20px 0; font-size: 15px; line-height: 1.6; color: #334155;">
                We are excited to confirm your registration for <strong>{event_name}</strong>. Your personalized digital event pass is ready!
              </p>

              <!-- Pass Info Pill Table -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #F1F5F9; border-radius: 8px; margin-bottom: 24px; padding: 14px 16px;">
                <tr>
                  <td style="font-size: 14px; color: #475569; padding: 4px 0;">
                    <strong>Pass ID:</strong> #{pass_id}
                  </td>
                  <td align="right" style="padding: 4px 0;">
                    <span style="display: inline-block; background-color: {status_badge_bg}; color: {status_badge_fg}; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 12px;">
                      {status_icon} {status_str}
                    </span>
                  </td>
                </tr>
              </table>

              <!-- Embedded Badge Card Preview -->
              <div style="text-align: center; margin: 24px 0;">
                <p style="margin: 0 0 12px 0; font-size: 13px; color: #64748B; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Your Official Pass</p>
                <img src="cid:pass_badge" alt="Attendee Pass #{pass_id}" style="width: 100%; max-width: 320px; height: auto; border-radius: 10px; border: 1px solid #CBD5E1; box-shadow: 0 6px 16px rgba(0,0,0,0.08); display: inline-block;" />
              </div>

              <!-- Check-In Instructions Box -->
              <div style="background-color: #EFF6FF; border-left: 4px solid #00629B; border-radius: 4px; padding: 14px 16px; margin: 24px 0;">
                <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #1E3A8A;">
                  <strong>Quick Check-In:</strong> Please present the QR code on this pass (from your mobile screen or printed) at the entrance registration desk to confirm your attendance.
                </p>
              </div>

              <p style="margin: 20px 0 0 0; font-size: 14px; color: #475569; line-height: 1.5;">
                We look forward to seeing you at the event! If you have any questions or require assistance, simply reply to this email.
              </p>

              <!-- Kareem Elebairy's Signature -->
              <div style="margin-top: 32px; padding-top: 18px; border-top: 1px solid #E2E8F0;">
                <p style="margin: 0; font-size: 14px; color: #64748B;">Best regards,</p>
                <p style="margin: 4px 0 2px 0; font-size: 16px; font-weight: 700; color: #0F172A;">Kareem Elebairy</p>
                <p style="margin: 0; font-size: 14px; font-weight: 600; color: #00629B;">IEEE Computer Society Vice Chair</p>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #F1F5F9; padding: 14px 24px; text-align: center; border-top: 1px solid #E2E8F0;">
              <p style="margin: 0; font-size: 12px; color: #94A3B8;">
                This pass is non-transferable and assigned exclusively to {attendee_name}.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    msg_alternative.attach(MIMEText(html_content, "html", "utf-8"))

    # 3. Inline CID Image Attachment (Embedded in HTML)
    badge_path = Path(badge_image_path)
    if badge_path.exists():
        with open(badge_path, "rb") as f:
            img_data = f.read()

        msg_image = MIMEImage(img_data, _subtype="png")
        msg_image.add_header("Content-ID", "<pass_badge>")
        msg_image.add_header("Content-Disposition", "inline", filename=badge_path.name)
        msg_root.attach(msg_image)

        # 4. Also attach as downloadable file
        msg_attach = MIMEApplication(img_data, _subtype="png")
        msg_attach.add_header("Content-Disposition", "attachment", filename=f"Event_Pass_{pass_id}.png")
        msg_root.attach(msg_attach)
    else:
        print(f"Warning: Badge file not found at {badge_image_path}")

    return msg_root


# ==============================================================================
# SMTP Dispatcher
# ==============================================================================
def connect_smtp(host: str, port: int, user: str, password: str, use_tls: bool = True) -> smtplib.SMTP:
    """Establishes an authenticated SMTP connection."""
    print(f"Connecting to SMTP server {host}:{port}...")
    server = smtplib.SMTP(host, port, timeout=30)
    server.ehlo()
    if use_tls:
        server.starttls()
        server.ehlo()
    server.login(user, password)
    print("SMTP authentication successful.")
    return server


def send_single_email(
    smtp_server: smtplib.SMTP,
    sender_email: str,
    sender_name: str,
    attendee_name: str,
    attendee_email: str,
    pass_id: str,
    is_ieee: bool,
    badge_path: str,
    event_name: str = "Next Wave II"
) -> bool:
    """Sends a single attendee pass email."""
    msg = compose_pass_email(
        sender_email=sender_email,
        sender_name=sender_name,
        attendee_name=attendee_name,
        attendee_email=attendee_email,
        pass_id=pass_id,
        is_ieee=is_ieee,
        badge_image_path=badge_path,
        event_name=event_name
    )
    smtp_server.send_message(msg)
    return True


def batch_send_passes(
    registry_csv: str = "output_qrs/attendees_registry.csv",
    badge_dir: str = "output_qrs/badges",
    sender_email: str = "",
    sender_password: str = "",
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
    sender_name: str = "Kareem Elebairy | IEEE Computer Society",
    event_name: str = "Next Wave II",
    delay_seconds: float = 2.5,
    skip_already_sent: bool = True,
    test_mode_email: str = None,
    progress_callback = None
) -> dict:
    """
    Batch sends event passes to all attendees in the registry CSV.
    Updates attendees_registry.csv in real time with Email_Sent_Status.
    """
    csv_file = Path(registry_csv)
    if not csv_file.exists():
        raise FileNotFoundError(f"Registry file not found: {registry_csv}")

    df = pd.read_csv(registry_csv, dtype=str, index_col=False)
    if df.empty:
        raise ValueError("Registry is empty.")

    # Ensure tracking columns exist
    if "Email_Sent_Status" not in df.columns:
        df["Email_Sent_Status"] = "Pending"
    if "Email_Sent_Time" not in df.columns:
        df["Email_Sent_Time"] = ""

    b_dir = Path(badge_dir)

    # If running in test mode: only send 1 email to the test address!
    if test_mode_email:
        print(f"\n[TEST MODE] Sending 1 sample pass to: {test_mode_email}")
        requested_email = test_mode_email.strip().lower()
        email_matches = df[
            df["Email"].fillna("").astype(str).str.strip().str.lower() == requested_email
        ]
        test_row = email_matches.iloc[0] if not email_matches.empty else df.iloc[0]
        if email_matches.empty:
            print("[TEST MODE] Recipient is not in the registry; using the first pass as a sample.")

        pass_id = str(test_row.get("ID", "1001"))
        attendee_name = str(test_row.get("Name", "Test Attendee")).strip()
        is_ieee = str(test_row.get("IEEE_Member", "")).strip().lower() in {"yes", "true", "1"}
        badge_name = str(test_row.get("Badge_File", ""))
        badge_path = b_dir / badge_name

        server = connect_smtp(smtp_host, smtp_port, sender_email, sender_password)
        try:
            send_single_email(
                smtp_server=server,
                sender_email=sender_email,
                sender_name=sender_name,
                attendee_name=attendee_name,
                attendee_email=test_mode_email,
                pass_id=pass_id,
                is_ieee=is_ieee,
                badge_path=str(badge_path),
                event_name=event_name
            )
            print(f"[TEST SUCCESS] Test email sent to {test_mode_email}!")
            print("Please check your inbox (and spam folder to confirm it arrived in Primary Inbox).")
            return {"success": 1, "failed": 0, "total": 1}
        finally:
            server.quit()

    # Batch sending to all attendees
    total = len(df)
    sent_count = 0
    failed_count = 0
    skipped_count = 0

    print(f"\nStarting batch email dispatch to {total} attendees...")
    print(f"Anti-spam throttling: {delay_seconds}s pause between emails.")

    server = connect_smtp(smtp_host, smtp_port, sender_email, sender_password)

    try:
        for i, (idx, row) in enumerate(df.iterrows()):
            pass_id = str(row.get("ID", ""))
            name = str(row.get("Name", "")).strip()
            email = str(row.get("Email", "")).strip()
            is_ieee = (str(row.get("IEEE_Member", "")).lower() in ["yes", "true", "1"])
            badge_name = str(row.get("Badge_File", ""))
            badge_path = b_dir / badge_name
            current_status = str(row.get("Email_Sent_Status", "")).strip()

            if skip_already_sent and current_status == "Sent":
                print(f" [{i + 1}/{total}] Skipping {pass_id} ({name}) - already sent.")
                skipped_count += 1
                continue

            if not email or "@" not in email:
                print(f" [{i + 1}/{total}] Skipping {pass_id} ({name}) - invalid/missing email: '{email}'")
                df.at[idx, "Email_Sent_Status"] = "No_Email"
                skipped_count += 1
                continue

            try:
                send_single_email(
                    smtp_server=server,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    attendee_name=name,
                    attendee_email=email,
                    pass_id=pass_id,
                    is_ieee=is_ieee,
                    badge_path=str(badge_path),
                    event_name=event_name
                )
                sent_count += 1
                df.at[idx, "Email_Sent_Status"] = "Sent"
                df.at[idx, "Email_Sent_Time"] = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f" [{i + 1}/{total}] Sent Pass #{pass_id} to: {name} <{email}>")
            except Exception as e:
                failed_count += 1
                df.at[idx, "Email_Sent_Status"] = f"Failed: {str(e)[:40]}"
                print(f" [{i + 1}/{total}] ERROR sending to {email}: {e}")

            # Save registry checkpoint after each send (prevents lost progress)
            df.to_csv(registry_csv, index=False, encoding="utf-8-sig")

            if progress_callback:
                progress_callback(i + 1, total, name, email)

            # Anti-spam delay pacing
            if i + 1 < total:
                time.sleep(delay_seconds)

    finally:
        try:
            server.quit()
        except Exception:
            pass

    print("\n" + "=" * 60)
    print("Batch Email Dispatch Finished!")
    print(f"Successfully sent: {sent_count}")
    print(f"Skipped:           {skipped_count}")
    print(f"Failed:            {failed_count}")
    print(f"Registry updated:  {csv_file.resolve()}")
    print("=" * 60 + "\n")

    return {
        "success": sent_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "total": total
    }


# ==============================================================================
# CLI Entry Point
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Send personalized event pass badges to attendees via email with anti-spam deliverability."
    )
    parser.add_argument(
        "--test",
        dest="test_email",
        help="Send a single test email to the specified address to verify inbox delivery."
    )
    parser.add_argument(
        "--send-all",
        action="store_true",
        help="Send passes to all attendees in the registry CSV."
    )
    parser.add_argument(
        "--csv",
        default="output_qrs/attendees_registry.csv",
        help="Path to attendees registry CSV."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.5,
        help="Delay in seconds between emails (anti-spam pacing, default 2.5s)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-send even if already marked as 'Sent'."
    )

    args = parser.parse_args()
    config = load_env_credentials()

    sender_email = config["sender_email"]
    sender_password = config["sender_password"]

    # Prompt if credentials are not in .env
    if not sender_email:
        sender_email = input("Enter your sender email (e.g., your_email@gmail.com): ").strip()
    if not sender_password:
        import getpass
        sender_password = getpass.getpass("Enter your email App Password: ").strip()

    if not sender_email or not sender_password:
        print("Error: Sender email and password are required.")
        sys.exit(1)

    if args.test_email:
        batch_send_passes(
            registry_csv=args.csv,
            sender_email=sender_email,
            sender_password=sender_password,
            smtp_host=config["smtp_host"],
            smtp_port=config["smtp_port"],
            sender_name=config["sender_name"],
            event_name=config["event_name"],
            test_mode_email=args.test_email
        )
    elif args.send_all:
        batch_send_passes(
            registry_csv=args.csv,
            sender_email=sender_email,
            sender_password=sender_password,
            smtp_host=config["smtp_host"],
            smtp_port=config["smtp_port"],
            sender_name=config["sender_name"],
            event_name=config["event_name"],
            delay_seconds=args.delay,
            skip_already_sent=not args.force
        )
    else:
        print("Please specify an action:")
        print("  Test Send: python email_sender.py --test your_email@gmail.com")
        print("  Send All:  python email_sender.py --send-all")
        print("  Or run the GUI: python gui.py")


if __name__ == "__main__":
    main()
