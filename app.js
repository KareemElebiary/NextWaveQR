const statusBox = document.getElementById("status");
const fileInput = document.getElementById("registry-file");
const downloadButton = document.getElementById("download-button");
const fileNameBox = document.getElementById("file-name");
const recordCountBox = document.getElementById("record-count");
const matchCountBox = document.getElementById("match-count");
const recordsHead = document.getElementById("records-head");
const recordsBody = document.getElementById("records-body");
let isProcessing = false;
let scanner = null;
let registryRows = [];
let registryHeaders = [];
let loadedFileName = "attendees.csv";

function showStatus(message, type = "info") {
  statusBox.textContent = message;
  statusBox.className = "status-box";
  if (type === "success") statusBox.classList.add("success");
  else if (type === "error") statusBox.classList.add("error");
}

function normalize(value) {
  return String(value ?? "").trim().toLowerCase();
}

function showTable() {
  recordsHead.replaceChildren();
  recordsBody.replaceChildren();
  registryHeaders.forEach((header) => {
    const cell = document.createElement("th");
    cell.textContent = header;
    recordsHead.appendChild(cell);
  });
  registryRows.slice(0, 25).forEach((row) => {
    const tableRow = document.createElement("tr");
    registryHeaders.forEach((header) => {
      const cell = document.createElement("td");
      cell.textContent = row[header] ?? "";
      tableRow.appendChild(cell);
    });
    recordsBody.appendChild(tableRow);
  });
}

function updateSummary() {
  const checkedCount = registryRows.filter((row) => normalize(row.Attended) === "yes" || normalize(row.Attended) === "true").length;
  fileNameBox.textContent = loadedFileName;
  recordCountBox.textContent = `${registryRows.length} attendees loaded`;
  matchCountBox.textContent = `${checkedCount} checked in`;
  downloadButton.disabled = registryRows.length === 0;
}

function parsePayload(raw) {
  try {
    return JSON.parse(raw);
  } catch (_) {
    const emailMatch = raw.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
    return emailMatch ? { email: emailMatch[0] } : null;
  }
}

function findAttendee(payload) {
  const payloadId = normalize(payload.id);
  const payloadEmail = normalize(payload.email);
  return registryRows.find((row) => payloadId && normalize(row.ID) === payloadId)
    || registryRows.find((row) => payloadEmail && normalize(row.Email) === payloadEmail);
}

function loadRegistry(file) {
  Papa.parse(file, {
    header: true,
    skipEmptyLines: true,
    complete: (results) => {
      if (results.errors.length) {
        showStatus("Could not read the CSV: " + results.errors[0].message, "error");
        return;
      }
      registryRows = results.data;
      registryHeaders = results.meta.fields || [];
      loadedFileName = file.name;
      showTable();
      updateSummary();
      showStatus("CSV loaded. Point the camera at an attendee QR code.");
      startScanner();
    }
  });
}

function onScanSuccess(decodedText) {
  if (isProcessing) return;
  isProcessing = true;
  void handleScannedData(decodedText);
}

async function startScanner() {
  if (scanner || !registryRows.length) return;
  try {
    if (!window.isSecureContext) {
      throw new Error("Camera access requires HTTPS or localhost");
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
    showStatus("Point the camera at the attendee QR code");
  } catch (error) {
    console.error(error);
    showStatus("Camera error: " + error.message, "error");
  }
}

async function handleScannedData(raw) {
  const payload = parsePayload(raw);
  if (!payload) {
    showStatus("Unable to read attendee details from this QR code", "error");
    isProcessing = false;
    return;
  }

  const attendee = findAttendee(payload);
  if (!attendee) {
    showStatus("Attendee was not found in the loaded CSV", "error");
    isProcessing = false;
    return;
  }

  const rowNumber = registryRows.indexOf(attendee) + 2;
  if (normalize(attendee.Attended) === "yes" || normalize(attendee.Attended) === "true") {
    showStatus(`Already checked in: ${attendee.Name || attendee.Email} (row ${rowNumber})`, "success");
  } else {
    attendee.Attended = "Yes";
    attendee.Check_In_Time = new Date().toISOString();
    showTable();
    updateSummary();
    showStatus(`Checked in: ${attendee.Name || attendee.Email} (row ${rowNumber})`, "success");
  }

  setTimeout(() => {
    isProcessing = false;
    showStatus("Point the camera at the attendee QR code");
  }, 3000);
}

function downloadRegistry() {
  const csv = Papa.unparse({ fields: registryHeaders, data: registryRows });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  link.download = loadedFileName.replace(/\.csv$/i, "") + "_attended.csv";
  link.click();
  URL.revokeObjectURL(link.href);
}

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) loadRegistry(fileInput.files[0]);
});
downloadButton.addEventListener("click", downloadRegistry);
window.addEventListener("DOMContentLoaded", startScanner);
