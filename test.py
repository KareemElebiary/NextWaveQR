import smtplib
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"      # ← your host
SMTP_PORT = 587                   # ← 587 for TLS
USERNAME  = "karim.320240094@ejust.edu.eg"     # ← your address
PASSWORD  = "ghmo kwtt bung uuqs"  # ← app password (if needed)

msg = EmailMessage()
msg["Subject"] = "Test mail from QR‑badge script"
msg["From"] = USERNAME
msg["To"] = USERNAME               # send to yourself
msg.set_content("If you see this, the SMTP config works ✅")

try:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(USERNAME, PASSWORD)
        server.send_message(msg)
    print("✅ Test mail sent")
except Exception as e:
    print("❌ Failed:", e)
