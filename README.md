# Next Wave II - IEEE Event Pass Generator & Mail Dispatcher

A Python system built for IEEE Computer Society events (Next Wave II) that generates unique attendee QR passes and dispatches them via email with anti-spam deliverability protections.

---

## 🌟 Key Features

1. **Attendee Pass Badges**:
   - **Phone number removed** from the visual card for privacy.
   - **Numeric Pass IDs** (`1001`, `1002`, `1003`...).
   - IEEE Membership status badge:
     - `★ IEEE MEMBER` in vibrant IEEE Blue (`#00629B`).
     - `• GUEST / NON-MEMBER` in clean neutral slate.
   - High-contrast, sharp QR code with ISO standard 4-module quiet zone for instant scanning.
   - Robust support for both English and Arabic attendee names (`احمد عبد الحميد صقر`).

2. **Anti-Spam Email Sender**:
   - **Lands in Primary Inbox (Not Spam/Junk)**:
     - Full RFC 5322 headers (`Message-ID`, `Date`, friendly `From` name, valid `Reply-To`).
     - Dual-part MIME (`text/plain` alternative + responsive HTML body).
     - Inline CID badge embedding (`cid:pass_badge`): attendee sees their pass directly in the email body, plus receives the PNG attachment.
     - Balanced text-to-image ratio with professional registration confirmation & check-in guidelines.
     - Paced delivery delay (2.5s) to avoid bot detection and SMTP rate limiting.
   - **Official Signature**:
     ```
     Best regards,
     Kareem Elebairy
     IEEE Computer Society Vice Chair
     ```
   - **Test Email Mode**: Send a single test pass to your own inbox to inspect before sending to all attendees.
   - **Idempotent / Resume Mode**: Tracks `Email_Sent_Status` and timestamps in `attendees_registry.csv` so interrupted sends can be resumed without sending duplicates.

3. **Desktop GUI (`gui.py`)**:
   - **Tab 1: Generate QR Passes**: Preview attendees, adjust options, and batch generate with one click.
   - **Tab 2: Send Passes by Email**: Configure SMTP credentials, send test emails, and batch dispatch with live logs and progress bar.

---

## 🚀 How to Run

### Option 1: Desktop GUI (Recommended)
```powershell
python gui.py
```

### Option 2: Command Line

#### 1. Generate Passes from CSV:
```powershell
python qr_generator.py --csv "Next Wave II - Form Responses 1.csv"
```

#### 2. Send 1 Test Email to Yourself:
```powershell
python email_sender.py --test your_email@gmail.com
```

#### 3. Send Passes to All Attendees:
```powershell
python email_sender.py --send-all
```

---

## 🔑 Setting Up Gmail SMTP (Google App Password)

For Gmail / Google Workspace (including `@ejust.edu.eg` Google accounts), regular passwords cannot be used with SMTP. You need a **Google App Password**:

1. Go to your [Google Account Security](https://myaccount.google.com/security).
2. Ensure **2-Step Verification** is turned ON.
3. In the search bar at the top of Google Account, type **"App passwords"** (or go to Security -> 2-Step Verification -> App passwords).
4. Enter an App Name (e.g., `IEEE Pass Sender`) and click **Create**.
5. Copy the generated **16-character password** (e.g. `abcd efgh ijkl mnop`).
6. Paste it into the GUI or add it to `.env`:
   ```ini
   SENDER_EMAIL=your_email@gmail.com
   SENDER_PASSWORD=your_16_char_password_without_spaces
   ```

---

## 🧪 Verification & Testing

To test and verify that all generated QR codes decode accurately:
```powershell
python verify_qr.py
```
*(All 82 attendee passes in Next Wave II decoded with 100% accuracy).*

## Google Sheets Attendance Scanner

The scanner uses `google_apps_script/Code.gs` as a web-app endpoint. The Apps Script account, not the 20 volunteers, writes the checkbox.

### One-time Google setup

1. Create or choose a dedicated Google account for the event, such as an event automation account.
2. Share the attendance Google Sheet with that account as **Editor**. Do not share the sheet with all volunteers.
3. Open `google_apps_script/Code.gs` at [script.google.com](https://script.google.com), paste the code into a project, and set `SPREADSHEET_ID` to the ID from the Sheet URL. Leave `SHEET_NAME` empty to use the first tab, or set the exact tab name.
4. In the Apps Script editor, run `authorizeSheetAccess` once and approve the requested Google Sheets permissions while signed in as the automation account.
5. Select **Deploy > New deployment > Web app**.
6. Set **Execute as** to **Me** (the automation account) and **Who has access** to **Anyone**. Deploy and copy the `/exec` URL.
7. Put that URL in both `qr_scanner_web/config.js` and `qr_scanner_web_deploy/config.js` as `APPS_SCRIPT_URL`, then publish the desired folder to GitHub Pages.

The sheet must have a header row containing `Email`, `Attended`, and `Check_In_Time`; a `Name` header is optional. `Attended` must be formatted as a Google Sheets checkbox column. Volunteers only need the GitHub Pages URL and camera permission. They do not need access to the Sheet or Apps Script project.

The endpoint uses a script lock, so simultaneous scans are serialized. If two volunteers scan the same email, one marks the row and the other receives `Already checked in`. If the same email appears on multiple rows, the first unchecked matching row is marked.
