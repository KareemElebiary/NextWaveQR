import { APPS_SCRIPT_URL } from "./config.js";

const statusBox = document.getElementById("status");
let isProcessing = false;

function showStatus(message, type = "info") {
  statusBox.textContent = message;
  statusBox.className = "status-box";
  if (type === "success") statusBox.classList.add("success");
  else if (type === "error") statusBox.classList.add("error");
}

function onScanSuccess(decodedText) {
  if (isProcessing) return;
  isProcessing = true;
  void handleScannedData(decodedText);
}

async function startScanner() {
  try {
    if (!window.isSecureContext) throw new Error("Camera access requires HTTPS or localhost");
    if (!window.Html5Qrcode) throw new Error("QR scanner library failed to load");
    const scanner = new Html5Qrcode("reader");
    await scanner.start({ facingMode: "environment" }, { fps: 10, qrbox: { width: 250, height: 250 } }, onScanSuccess, () => {});
    showStatus("Point the camera at the QR code");
  } catch (error) {
    console.error(error);
    showStatus("Camera error: " + error.message, "error");
  }
}

async function handleScannedData(raw) {
  showStatus("Verifying attendance...");
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (_) {
    const emailMatch = raw.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
    if (!emailMatch) {
      showStatus("Unable to parse QR payload", "error");
      isProcessing = false;
      return;
    }
    payload = { email: emailMatch[0] };
  }
  if (!payload.email) {
    showStatus("QR does not contain an email", "error");
    isProcessing = false;
    return;
  }

  try {
    const response = await fetch(APPS_SCRIPT_URL, { method: "POST", headers: { "Content-Type": "text/plain" }, body: JSON.stringify({ email: payload.email }) });
    const responseText = await response.text();
    let data;
    try { data = JSON.parse(responseText); } catch (_) { throw new Error(`Server returned an invalid response (${response.status})`); }
    if (!response.ok) throw new Error(data.msg || `Server returned ${response.status}`);
    showStatus(data.ok ? "✅ " + data.msg : "⚠️ " + (data.msg || "Attendee was not found"), data.ok ? "success" : "error");
  } catch (error) {
    console.error(error);
    showStatus("Network error: " + error.message, "error");
  }
  setTimeout(() => { isProcessing = false; showStatus("Point the camera at the QR code"); }, 3000);
}

window.addEventListener("DOMContentLoaded", startScanner);
