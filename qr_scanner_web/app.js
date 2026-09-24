// app.js - QR scanner front-end logic
// Uses html5-qrcode library (loaded via CDN in index.html)
import { APPS_SCRIPT_URL } from "./config.js";

const statusBox = document.getElementById("status");
let html5QrCode = null;
let isProcessing = false;

function showStatus(message, type = "info") {
  statusBox.textContent = message;
  statusBox.className = "status-box";
  if (type === "success") statusBox.classList.add("success");
  else if (type === "error") statusBox.classList.add("error");
}

function requestAttendanceJsonp(email) {
  return new Promise((resolve, reject) => {
    const callbackName = "attendanceCallback_" + Date.now();
    const script = document.createElement("script");
    const cleanup = () => { delete window[callbackName]; script.remove(); };
    const timeout = setTimeout(() => { cleanup(); reject(new Error("Attendance server timed out")); }, 10000);
    window[callbackName] = (data) => { clearTimeout(timeout); cleanup(); resolve(data); };
    script.onerror = () => { clearTimeout(timeout); cleanup(); reject(new Error("Attendance server could not be reached")); };
    script.src = `${APPS_SCRIPT_URL}?email=${encodeURIComponent(email)}&callback=${callbackName}`;
    document.body.appendChild(script);
  });
}

async function requestAttendance(email) {
  return requestAttendanceJsonp(email);
}

function onScanSuccess(decodedText) {
  if (isProcessing) return;
  isProcessing = true;
  void handleScannedData(decodedText);
}

async function startScanner() {
  try {
    if (!window.isSecureContext) {
      throw new Error("Camera access requires HTTPS or localhost");
    }
    if (!window.Html5Qrcode) {
      throw new Error("QR scanner library failed to load");
    }

    html5QrCode = new Html5Qrcode("reader");
    await html5QrCode.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: { width: 250, height: 250 } },
      onScanSuccess,
      () => {} // ignore errors during continuous scanning
    );
    showStatus("📸 Point the camera at the QR code");
  } catch (e) {
    console.error(e);
    showStatus("❌ Camera error: " + e.message, "error");
  }
}

async function handleScannedData(raw) {
  showStatus("🔎 Verifying attendance...");
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (_) {
    // fallback: treat raw string as plain email
    const emailMatch = raw.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
    if (!emailMatch) {
      showStatus("❌ Unable to parse QR payload", "error");
      isProcessing = false;
      return;
    }
    payload = { email: emailMatch[0] };
  }
  if (!payload.email) {
    showStatus("❌ QR does not contain an email", "error");
    isProcessing = false;
    return;
  }

  try {
    const result = await requestAttendance(payload.email);
    if (!result.ok) throw new Error(result.msg || "Attendance was not accepted");
    showStatus(`✅ ${result.name} found in row ${result.row}. Attendance confirmed.`, "success");
  } catch (err) {
    console.error(err);
    showStatus("❌ Network error: " + err.message, "error");
  }

  // Allow scanning again after 3 seconds
  setTimeout(() => {
    isProcessing = false;
    showStatus("📸 Point the camera at the QR code");
  }, 3000);
}

// Initialize on page load
window.addEventListener("DOMContentLoaded", startScanner);
