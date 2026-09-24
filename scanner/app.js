// QR scanner front-end logic.
import { FIREBASE_CONFIG } from "./config.js?v=7";

firebase.initializeApp(FIREBASE_CONFIG);
const auth = firebase.auth();
const db = firebase.firestore();

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

function cameraErrorMessage(error) {
  const message = typeof error === "string"
    ? error
    : error && (error.message || error.name);
  if (message === "NotAllowedError" || message === "Permission denied") {
    return "Camera permission was denied. Allow Camera for this site in browser settings.";
  }
  if (message === "NotReadableError" || message === "Could not start video source") {
    return "The camera is being used by another app. Close other camera apps and try again.";
  }
  return message || "The browser could not open the camera.";
}

async function requestAttendance(email) {
  const normalizedEmail = String(email || "").trim().toLowerCase();
  if (!normalizedEmail) return { ok: false, msg: "Email is required" };

  await auth.signInAnonymously();
  const matches = await db.collection("attendees")
    .where("email", "==", normalizedEmail)
    .limit(10)
    .get();
  if (matches.empty) return { ok: false, msg: "Attendee not found" };

  return db.runTransaction(async (transaction) => {
    const documents = [];
    for (const document of matches.docs) {
      documents.push({ ref: document.ref, data: (await transaction.get(document.ref)).data() });
    }

    const available = documents.find((document) => {
      const attended = document.data.attended;
      return attended !== true && String(attended).trim().toLowerCase() !== "true";
    });
    const selected = available || documents[0];
    const name = String(selected.data.name || normalizedEmail).trim();
    if (!available) return { ok: true, msg: "Already checked in", name: name };

    transaction.update(selected.ref, {
      attended: true,
      checkInTime: firebase.firestore.FieldValue.serverTimestamp()
    });
    return { ok: true, msg: "Attendance marked", name: name };
  });
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
    showStatus("Camera error: " + cameraErrorMessage(error) + " Tap Start camera to retry.", "error");
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
    showStatus(`✅ ${result.name} found. Attendance confirmed.`, "success");
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
