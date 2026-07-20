/**
 * Meal Agent — NDA acceptances + beta feedback → Google Sheet
 *
 * Setup:
 * 1. Create a Google Sheet (or reuse the NDA sheet).
 * 2. Extensions → Apps Script → paste this file → Save.
 * 3. Project Settings → Script properties → NDA_SECRET = <same as Render NDA_SHEETS_SECRET>
 * 4. Deploy → Web app → Execute as: Me; Who has access: Anyone.
 * 5. Render: NDA_SHEETS_WEBHOOK_URL + NDA_SHEETS_SECRET
 * 6. After edits: Deploy → Manage deployments → Edit → New version.
 *
 * Tabs (open these in the spreadsheet):
 * - Acceptances — who signed the NDA (one row per person)
 * - Feedback — questionnaire answers (one row per submit)
 * - Summary — auto counts / % for investors (read this first)
 *
 * One-time cleanup after pasting this script:
 * Run function resetSheetLayout from the Apps Script editor
 * (select resetSheetLayout → Run). That rebuilds headers + Summary
 * without deleting existing Feedback / Acceptances data rows.
 */

var ACCEPTANCES_HEADERS = [
  "Accepted at",
  "Full name",
  "NDA version",
  "Record id",
  "Client IP",
  "Browser",
];

var FEEDBACK_HEADERS = [
  "Submitted at",
  "Record id",
  "Session id",
  "1. Meal plan useful?",
  "2. Most valuable",
  "3. Use again?",
  "4. If never public?",
  "5. Premium NZ$9.99?",
  "6. Improve (optional)",
  "Browser",
];

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

  var type = String(body.type || "nda").toLowerCase();
  if (type === "feedback") {
    return handleFeedback_(body);
  }
  if (type === "reset_layout") {
    resetSheetLayout();
    return jsonOut_({ ok: true, reset: true });
  }
  return handleNda_(body);
}

function handleNda_(body) {
  var name = String(body.full_name || "").trim();
  if (!name) {
    return jsonOut_({ ok: false, error: "full_name required" });
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ensureNamedSheet_(ss, "Acceptances");
  ensureHeaderRow_(sheet, ACCEPTANCES_HEADERS);

  sheet.appendRow([
    body.accepted_at || new Date().toISOString(),
    name,
    body.nda_version || "",
    body.id || "",
    body.client_ip || "",
    shortenUa_(body.user_agent || ""),
  ]);

  return jsonOut_({ ok: true });
}

function handleFeedback_(body) {
  var required = [
    "meal_plan_useful",
    "most_valuable",
    "use_again",
    "if_never_public",
    "premium_subscribe",
  ];
  for (var i = 0; i < required.length; i++) {
    if (!String(body[required[i]] || "").trim()) {
      return jsonOut_({ ok: false, error: required[i] + " required" });
    }
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ensureNamedSheet_(ss, "Feedback");
  ensureHeaderRow_(sheet, FEEDBACK_HEADERS);
  ensureSummarySheet_(ss, true);

  sheet.appendRow([
    body.submitted_at || new Date().toISOString(),
    body.id || "",
    body.session_id || "",
    body.meal_plan_useful || "",
    body.most_valuable || "",
    body.use_again || "",
    body.if_never_public || "",
    body.premium_subscribe || "",
    body.improve || "",
    shortenUa_(body.user_agent || ""),
  ]);

  return jsonOut_({ ok: true });
}

/** Manual / one-time: rebuild headers + Summary without wiping data. */
function resetSheetLayout() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var acceptances = ensureNamedSheet_(ss, "Acceptances");
  var feedback = ensureNamedSheet_(ss, "Feedback");
  ensureHeaderRow_(acceptances, ACCEPTANCES_HEADERS);
  ensureHeaderRow_(feedback, FEEDBACK_HEADERS);
  ensureSummarySheet_(ss, true);
}

function ensureNamedSheet_(ss, name) {
  var sheet = ss.getSheetByName(name);
  if (!sheet) sheet = ss.insertSheet(name);
  return sheet;
}

/**
 * Ensure row 1 is the expected header.
 * If row 1 is missing or wrong, insert a header row above existing data.
 */
function ensureHeaderRow_(sheet, headers) {
  var lastCol = headers.length;
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, lastCol).setValues([headers]);
    sheet.getRange(1, 1, 1, lastCol).setFontWeight("bold");
    sheet.setFrozenRows(1);
    return;
  }

  var existing = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  var matches = true;
  for (var i = 0; i < headers.length; i++) {
    if (String(existing[i] || "") !== headers[i]) {
      matches = false;
      break;
    }
  }
  if (matches) {
    sheet.getRange(1, 1, 1, lastCol).setFontWeight("bold");
    sheet.setFrozenRows(1);
    return;
  }

  // Row 1 is data or an old snake_case header — insert a proper header above it.
  sheet.insertRowBefore(1);
  sheet.getRange(1, 1, 1, lastCol).setValues([headers]);
  sheet.getRange(1, 1, 1, lastCol).setFontWeight("bold");
  sheet.setFrozenRows(1);

  // If the old row 2 looks like a duplicate header (snake_case), remove it.
  var maybeOld = sheet.getRange(2, 1, 1, lastCol).getValues()[0];
  if (String(maybeOld[0] || "").indexOf("submitted") === 0 || String(maybeOld[0] || "") === "accepted_at") {
    sheet.deleteRow(2);
  }
}

function ensureSummarySheet_(ss, force) {
  var sheet = ss.getSheetByName("Summary");
  if (!force && sheet && sheet.getRange("A1").getValue() === "Question / metric") return;
  if (!sheet) sheet = ss.insertSheet("Summary");
  sheet.clear();

  // Feedback columns after human headers:
  // D = meal plan useful, E = most valuable, F = use again,
  // G = if never public, H = premium
  var rows = [
    ["Question / metric", "Count or %", "Notes"],
    ["Total feedback responses", "=COUNTA(Feedback!A:A)-1", "Read this tab for investor rollups"],
    [],
    ["1. Meal plan useful?", "", ""],
    ["  Very useful", '=COUNTIF(Feedback!D:D,"Very useful")', ""],
    ["  Useful", '=COUNTIF(Feedback!D:D,"Useful")', ""],
    ["  Unsure", '=COUNTIF(Feedback!D:D,"Unsure")', ""],
    ["  Unhelpful", '=COUNTIF(Feedback!D:D,"Unhelpful")', ""],
    ["  Not useful", '=COUNTIF(Feedback!D:D,"Not useful")', ""],
    [],
    ["2. Most valuable part", "", ""],
    ["  Chef meal plan", '=COUNTIF(Feedback!E:E,"Chef meal plan")', ""],
    ["  Shopping list", '=COUNTIF(Feedback!E:E,"Shopping list")', ""],
    ["  Personalised preferences", '=COUNTIF(Feedback!E:E,"Personalised preferences")', ""],
    ["  Saving time", '=COUNTIF(Feedback!E:E,"Saving time")', ""],
    ["  None", '=COUNTIF(Feedback!E:E,"None")', ""],
    [],
    ["3. Use again?", "", ""],
    ["  Very likely", '=COUNTIF(Feedback!F:F,"Very likely")', ""],
    ["  Likely", '=COUNTIF(Feedback!F:F,"Likely")', ""],
    ["  Unsure", '=COUNTIF(Feedback!F:F,"Unsure")', ""],
    ["  Unlikely", '=COUNTIF(Feedback!F:F,"Unlikely")', ""],
    ["  Definitely not", '=COUNTIF(Feedback!F:F,"Definitely not")', ""],
    ["  Positive % (Very likely + Likely)", '=IF(B2<=0,"",(B19+B20)/B2)', ""],
    [],
    ["4. If never public?", "", ""],
    ["  Very disappointed", '=COUNTIF(Feedback!G:G,"Very disappointed")', ""],
    ["  Disappointed", '=COUNTIF(Feedback!G:G,"Disappointed")', ""],
    ["  Unsure", '=COUNTIF(Feedback!G:G,"Unsure")', ""],
    ["  Not disappointed", '=COUNTIF(Feedback!G:G,"Not disappointed")', ""],
    ["  Not at all disappointed", '=COUNTIF(Feedback!G:G,"Not at all disappointed")', ""],
    ["  Disappointed % (Very + Disappointed)", '=IF(B2<=0,"",(B27+B28)/B2)', ""],
    [],
    ["5. Premium NZ$9.99/month?", "", ""],
    ["  Very likely", '=COUNTIF(Feedback!H:H,"Very likely")', ""],
    ["  Likely", '=COUNTIF(Feedback!H:H,"Likely")', ""],
    ["  Unsure", '=COUNTIF(Feedback!H:H,"Unsure")', ""],
    ["  Unlikely", '=COUNTIF(Feedback!H:H,"Unlikely")', ""],
    ["  Definitely not", '=COUNTIF(Feedback!H:H,"Definitely not")', ""],
    ["  Interest % (Very likely + Likely)", '=IF(B2<=0,"",(B35+B36)/B2)', ""],
    [],
    ["Tips", "", ""],
    ["  Feedback tab", "", "One row per survey — read column I for free-text"],
    ["  Acceptances tab", "", "Who signed the NDA"],
  ];

  sheet.getRange(1, 1, rows.length, 3).setValues(
    rows.map(function (r) {
      return [r[0] || "", r[1] || "", r[2] || ""];
    })
  );
  sheet.getRange(1, 1, 1, 3).setFontWeight("bold");
  sheet.setColumnWidth(1, 360);
  sheet.setColumnWidth(2, 120);
  sheet.setColumnWidth(3, 280);
  sheet.getRange("B24").setNumberFormat("0.0%");
  sheet.getRange("B32").setNumberFormat("0.0%");
  sheet.getRange("B40").setNumberFormat("0.0%");
  sheet.setFrozenRows(1);
}

function shortenUa_(ua) {
  ua = String(ua || "");
  if (!ua) return "";
  if (ua.indexOf("Edg/") >= 0) return "Edge";
  if (ua.indexOf("Chrome/") >= 0) return "Chrome";
  if (ua.indexOf("Firefox/") >= 0) return "Firefox";
  if (ua.indexOf("Safari/") >= 0) return "Safari";
  return ua.substring(0, 40);
}

function doGet() {
  return jsonOut_({ ok: true, service: "meal-agent-nda-feedback" });
}

function jsonOut_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
