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
 * Tabs:
 * - Acceptances (NDA)
 * - Feedback (questionnaire rows)
 * - Summary (auto tallies from Feedback)
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

  var type = String(body.type || "nda").toLowerCase();
  if (type === "feedback") {
    return handleFeedback_(body);
  }
  return handleNda_(body);
}

function handleNda_(body) {
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
  var sheet = ss.getSheetByName("Feedback");
  if (!sheet) {
    sheet = ss.insertSheet("Feedback");
  }
  ensureFeedbackHeader_(sheet);
  ensureSummarySheet_(ss);

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
    body.user_agent || "",
  ]);

  return jsonOut_({ ok: true });
}

function ensureFeedbackHeader_(sheet) {
  if (sheet.getLastRow() > 0) return;
  sheet.appendRow([
    "submitted_at",
    "id",
    "session_id",
    "meal_plan_useful",
    "most_valuable",
    "use_again",
    "if_never_public",
    "premium_subscribe",
    "improve",
    "user_agent",
  ]);
}

function ensureSummarySheet_(ss) {
  var sheet = ss.getSheetByName("Summary");
  if (sheet && sheet.getRange("A1").getValue() === "Metric") return;
  if (!sheet) sheet = ss.insertSheet("Summary");
  sheet.clear();

  var rows = [
    ["Metric", "Value"],
    ["Total responses", "=COUNTA(Feedback!A:A)-1"],
    [],
    ["Use again — Very likely", '=COUNTIF(Feedback!F:F,"Very likely")'],
    ["Use again — Likely", '=COUNTIF(Feedback!F:F,"Likely")'],
    ["Use again — Unsure", '=COUNTIF(Feedback!F:F,"Unsure")'],
    ["Use again — Unlikely", '=COUNTIF(Feedback!F:F,"Unlikely")'],
    ["Use again — Definitely not", '=COUNTIF(Feedback!F:F,"Definitely not")'],
    ["Use again positive %", '=IF(B2<=0,"", (B4+B5)/B2)'],
    [],
    ["Never public — Very disappointed", '=COUNTIF(Feedback!G:G,"Very disappointed")'],
    ["Never public — Disappointed", '=COUNTIF(Feedback!G:G,"Disappointed")'],
    ["Never public — Unsure", '=COUNTIF(Feedback!G:G,"Unsure")'],
    ["Never public — Not disappointed", '=COUNTIF(Feedback!G:G,"Not disappointed")'],
    ["Never public — Not at all disappointed", '=COUNTIF(Feedback!G:G,"Not at all disappointed")'],
    ["Disappointed if never public %", '=IF(B2<=0,"", (B11+B12)/B2)'],
    [],
    ["Premium — Very likely", '=COUNTIF(Feedback!H:H,"Very likely")'],
    ["Premium — Likely", '=COUNTIF(Feedback!H:H,"Likely")'],
    ["Premium — Unsure", '=COUNTIF(Feedback!H:H,"Unsure")'],
    ["Premium — Unlikely", '=COUNTIF(Feedback!H:H,"Unlikely")'],
    ["Premium — Definitely not", '=COUNTIF(Feedback!H:H,"Definitely not")'],
    ["Premium interest % (NZ$9.99)", '=IF(B2<=0,"", (B18+B19)/B2)'],
    [],
    ["Most valuable — Chef meal plan", '=COUNTIF(Feedback!E:E,"Chef meal plan")'],
    ["Most valuable — Shopping list", '=COUNTIF(Feedback!E:E,"Shopping list")'],
    ["Most valuable — Personalised preferences", '=COUNTIF(Feedback!E:E,"Personalised preferences")'],
    ["Most valuable — Saving time", '=COUNTIF(Feedback!E:E,"Saving time")'],
    ["Most valuable — None", '=COUNTIF(Feedback!E:E,"None")'],
    [],
    ["Meal plan — Very useful", '=COUNTIF(Feedback!D:D,"Very useful")'],
    ["Meal plan — Useful", '=COUNTIF(Feedback!D:D,"Useful")'],
    ["Meal plan — Unsure", '=COUNTIF(Feedback!D:D,"Unsure")'],
    ["Meal plan — Unhelpful", '=COUNTIF(Feedback!D:D,"Unhelpful")'],
    ["Meal plan — Not useful", '=COUNTIF(Feedback!D:D,"Not useful")'],
  ];

  sheet.getRange(1, 1, rows.length, 2).setValues(
    rows.map(function (r) {
      return [r[0] || "", r[1] || ""];
    })
  );
  sheet.getRange("B9").setNumberFormat("0.0%");
  sheet.getRange("B16").setNumberFormat("0.0%");
  sheet.getRange("B23").setNumberFormat("0.0%");
}

function doGet() {
  return jsonOut_({ ok: true, service: "meal-agent-nda-feedback" });
}

function jsonOut_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
