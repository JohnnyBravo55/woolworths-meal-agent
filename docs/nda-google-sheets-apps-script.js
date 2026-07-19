/**
 * Meal Agent — NDA acceptances → Google Sheet
 *
 * Setup:
 * 1. Create a Google Sheet. Optional: rename first tab to "Acceptances".
 * 2. Row 1 headers (optional): accepted_at | full_name | nda_version | id | client_ip | user_agent
 * 3. Extensions → Apps Script → paste this file → Save.
 * 4. Project Settings (gear) → Script properties → Add:
 *      NDA_SECRET = <long random string>   (same value as Render NDA_SHEETS_SECRET)
 * 5. Deploy → New deployment → Type: Web app
 *      Execute as: Me
 *      Who has access: Anyone
 * 6. Copy the web app URL → Render env NDA_SHEETS_WEBHOOK_URL
 *
 * After editing the script, Deploy → Manage deployments → Edit → New version.
 */

function doPost(e) {
  var expected = PropertiesService.getScriptProperties().getProperty("NDA_SECRET");
  if (!expected) {
    return jsonOut_({ ok: false, error: "NDA_SECRET not configured in Script properties" });
  }

  var body;
  try {
    body = JSON.parse((e && e.postData && e.postData.contents) || "{}");
  } catch (err) {
    return jsonOut_({ ok: false, error: "Invalid JSON" });
  }

  if (!body.secret || body.secret !== expected) {
    return jsonOut_({ ok: false, error: "Unauthorized" });
  }

  var name = String(body.full_name || "").trim();
  if (!name) {
    return jsonOut_({ ok: false, error: "full_name required" });
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Acceptances") || ss.getSheets()[0];
  sheet.appendRow([
    body.accepted_at || new Date().toISOString(),
    name,
    body.nda_version || "",
    body.id || "",
    body.client_ip || "",
    body.user_agent || "",
  ]);

  return jsonOut_({ ok: true });
}

function doGet() {
  return jsonOut_({ ok: true, service: "meal-agent-nda" });
}

function jsonOut_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
