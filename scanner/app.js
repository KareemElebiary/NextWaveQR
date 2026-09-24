// QR scanner front-end logic.
import { APPS_SCRIPT_URL } from "./config.js?v=4";

const statusBox = document.getElementById("status");
const startButton = document.getElementById("start-camera");
let isProcessing = false;
let scanner = null;
let isStarting = false;

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
    const cleanup = () => {
      delete window[callbackName];
      script.remove();
    };
    const timeout = setTimeout(() => {
      cleanup();
      reject(new Error("Attendance server timed out"));
    }, 10000);

    window[callbackName] = (data) => {
      clearTimeout(timeout);
      cleanup();
      resolve(data);
    };
    script.onerror = () => {
      clearTimeout(timeout);
      cleanup();
      reject(new Error("Attendance server could not be reached"));
    };
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
  if (isStarting || scanner) return;
  isStarting = true;
  startButton.disabled = true;
  showStatus("Requesting camera permission...");
  try {
    if (!window.isSecureContext) {
      throw new Error("Camera access requires HTTPS or localhost");
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("This browser does not support camera access");
    }
    if (!window.Html5Qrcode) {
      throw new Error("QR scanner library failed to load");
    }

    scanner = new Html5Qrcode("reader");
    await scanner.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: { width: 250, height: 250 } },
      onScanSuccess,
      () => {}
    );
    showStatus("Point the camera at the QR code");
  } catch (error) {
    console.error(error);
    scanner = null;
    startButton.disabled = false;
    showStatus("Camera error: " + error.message + ". Tap Start camera and allow permission.", "error");
  } finally {
    isStarting = false;
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
    const result = await requestAttendance(payload.email);
    if (!result.ok) throw new Error(result.msg || "Attendance was not accepted");
    showStatus(`✅ ${result.name} found in row ${result.row}. Attendance confirmed.`, "success");
  } catch (error) {
    console.error(error);
    showStatus("Network error: " + error.message, "error");
  }

  setTimeout(() => {
    isProcessing = false;
    showStatus("Point the camera at the QR code");
  }, 3000);
}

startButton.addEventListener("click", startScanner);
window.addEventListener("DOMContentLoaded", startScanner);
