  const SPREADSHEET_ID = "1Kkz5IP3cIKZCfFwXYzLAephPOzLHRxbR0W1bMI-ySwc";
  // Use the first tab so the deployment does not depend on a tab name.
  const SHEET_NAME = "";

  // Run this function once from the Apps Script editor to authorize sheet access.
  function authorizeSheetAccess() {
    const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
    const sheet = SHEET_NAME
      ? spreadsheet.getSheetByName(SHEET_NAME)
      : spreadsheet.getSheets()[0];
    if (!sheet) throw new Error("No sheet tab was found");
    Logger.log("Authorized sheet: " + sheet.getName());
  }

  function doGet(event) {
    const callback = event && event.parameter ? event.parameter.callback : "";
    try {
      const email = event && event.parameter ? event.parameter.email : "";
      const result = email
        ? processAttendance(email)
        : { ok: true, msg: "Attendance endpoint is online" };
      return callback && /^[A-Za-z_$][\w$]*$/.test(callback)
        ? jsonpResponse(callback, result)
        : jsonResponse(result);
    } catch (error) {
      const result = { ok: false, msg: error.message };
      return callback && /^[A-Za-z_$][\w$]*$/.test(callback)
        ? jsonpResponse(callback, result)
        : jsonResponse(result);
    }
  }

  function doPost(event) {
    try {
      const body = JSON.parse(event.postData.contents || "{}");
      return jsonResponse(processAttendance(body.email));
    } catch (error) {
      return jsonResponse({ ok: false, msg: error.message });
    }
  }

  function processAttendance(rawEmail) {
    const email = String(rawEmail || "").trim().toLowerCase();
    if (!email) return { ok: false, msg: "Email is required" };

    const lock = LockService.getScriptLock();
    if (!lock.tryLock(10000)) {
      return { ok: false, msg: "The sheet is busy. Please scan again." };
    }

    try {
      const spreadsheet = SpreadsheetApp.openById(SPREADSHEET_ID);
      const sheetInfo = findAttendanceSheet(spreadsheet);
      if (!sheetInfo) {
        return { ok: false, msg: "No tab contains Email, Attended, and Check_In_Time headers" };
      }

      const { sheet, headers, emailColumn, attendedColumn, checkInColumn } = sheetInfo;
      const lastRow = sheet.getLastRow();
      const rows = lastRow > 1
        ? sheet.getRange(2, emailColumn, lastRow - 1, 1).getValues()
        : [];
      const matchingRows = rows
        .map((row, index) => ({ value: row[0], row: index + 2 }))
        .filter((item) => String(item.value).trim().toLowerCase() === email);
      if (!matchingRows.length) return { ok: false, msg: "Attendee not found" };

      const nameColumn = headers.indexOf("name") + 1;
      for (const match of matchingRows) {
        const currentValue = sheet.getRange(match.row, attendedColumn).getValue();
        const alreadyChecked = currentValue === true
          || String(currentValue).trim().toLowerCase() === "true"
          || String(currentValue).trim().toLowerCase() === "yes";
        if (alreadyChecked) continue;

        const name = nameColumn
          ? String(sheet.getRange(match.row, nameColumn).getValue()).trim()
          : email;
        sheet.getRange(match.row, attendedColumn).check();
        sheet.getRange(match.row, checkInColumn).setValue(new Date());
        SpreadsheetApp.flush();
        return { ok: true, msg: "Attendance marked", name: name, row: match.row };
      }

      const firstRow = matchingRows[0].row;
      const name = nameColumn
        ? String(sheet.getRange(firstRow, nameColumn).getValue()).trim()
        : email;
      return { ok: true, msg: "Already checked in", name: name, row: firstRow };
    } finally {
      lock.releaseLock();
    }
  }

  function findAttendanceSheet(spreadsheet) {
    const sheets = SHEET_NAME
      ? [spreadsheet.getSheetByName(SHEET_NAME)].filter(Boolean)
      : spreadsheet.getSheets();

    for (const sheet of sheets) {
      const lastColumn = sheet.getLastColumn();
      if (!lastColumn) continue;
      const headers = sheet
        .getRange(1, 1, 1, lastColumn)
        .getValues()[0]
        .map(normalizeHeader);
      const emailColumn = headers.indexOf("email") + 1;
      const attendedColumn = headers.indexOf("attended") + 1;
      const checkInColumn = headers.indexOf("check_in_time") + 1;
      if (emailColumn && attendedColumn && checkInColumn) {
        return { sheet, headers, emailColumn, attendedColumn, checkInColumn };
      }
    }
    return null;
  }

  function normalizeHeader(value) {
    return String(value)
      .trim()
      .toLowerCase()
      .replace(/[\s-]+/g, "_");
  }

  function jsonResponse(value) {
    return ContentService
      .createTextOutput(JSON.stringify(value))
      .setMimeType(ContentService.MimeType.JSON);
  }

  function jsonpResponse(callback, value) {
    return ContentService
      .createTextOutput(callback + "(" + JSON.stringify(value) + ");")
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
