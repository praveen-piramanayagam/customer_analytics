import os, json, re
import pandas as pd
from flask import Flask, render_template, request
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MAX_EXTERNAL, MAX_CRM = 60, 180

def normcols(df):
    df = df.copy()
    df.columns = [re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in df.columns]
    return df

def val(row, names):
    for n in names:
        v = row.get(n, "")
        if pd.notna(v) and str(v).strip():
            return str(v).strip()
    return ""

def load_csv(file, kind):
    if not file or not file.filename:
        raise ValueError(f"Please upload the {kind} CSV.")
    try:
        df = normcols(pd.read_csv(file, dtype=str, keep_default_na=False))
    except Exception as e:
        raise ValueError(f"Could not read {kind} CSV: {e}")
    if df.empty:
        raise ValueError(f"The {kind} CSV has no data rows.")
    common = {
        "customer_id": ["customer_id","contact_id","account_id","customerid","contactid"],
        "date": ["interaction_date","activity_date","date","timestamp","created_time","call_date"],
        "channel": ["channel","activity_type","interaction_type","type","source","subject"],
        "text": ["interaction_text","message","notes","description","summary","activity_notes","call_notes"],
        "deal_id": ["deal_id","opportunity_id","deal","opportunity"],
    }
    if kind == "CRM activity":
        common["follow_up_task"] = ["follow_up_task","next_task","task","next_step","followup_task"]
        common["task_due_date"] = ["task_due_date","due_date","follow_up_date","next_follow_up_date"]
    rows = []
    for idx, row in df.iterrows():
        item = {k: val(row, names) for k, names in common.items()}
        item["source_row"] = int(idx) + 2
        rows.append(item)
    return rows

def parse_date(s):
    if not s: return None
    d = pd.to_datetime(s, errors="coerce")
    return None if pd.isna(d) else d

def candidates(e, crm, window):
    cid = e["customer_id"].casefold().replace(" ", "")
    d1 = parse_date(e["date"])
    found = []
    for c in crm:
        if not cid or cid != c["customer_id"].casefold().replace(" ", ""):
            continue
        d2 = parse_date(c["date"])
        if d1 is None or d2 is None or abs((d1-d2).days) <= window:
            found.append(c)
    return found[:5]

def analyse(external, crm, window):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Check that your .env file is in the same folder as app.py, then restart the app.")
    if len(external) > MAX_EXTERNAL or len(crm) > MAX_CRM:
        raise ValueError(f"Prototype limit: upload at most {MAX_EXTERNAL} external interactions and {MAX_CRM} CRM activities per run.")
    cases = []
    for e in external:
        cs = candidates(e, crm, window)
        cases.append({
            "external_interaction": {k:e.get(k,"") for k in ["customer_id","date","channel","text","deal_id","source_row"]},
            "possible_crm_matches": [
                {k:c.get(k,"") for k in ["customer_id","date","channel","text","deal_id","follow_up_task","task_due_date","source_row"]}
                for c in cs
            ]
        })
    instructions = """You are a careful customer-operations analytics assistant. Compare each external interaction with supplied possible CRM activities. Use meaning, not just dates, to judge whether a CRM activity is a plausible match. Identify customer commitments or requested next steps and check whether a related follow-up task is recorded.
Return ONLY valid JSON with this structure:
{"summary":"short plain-English summary","results":[{"source_row":2,"status":"matched | potential_missing | follow_up_gap | needs_review","matched_crm_row":2,"commitment":"short description or None identified","reason":"brief evidence-based explanation","recommended_action":"specific next action","confidence":"high | medium | low"}]}
Include one result for each external interaction and preserve source_row. matched_crm_row must be null if no suitable match. Use potential_missing only when no plausible activity is present. Use follow_up_gap if a commitment exists but no related task appears. Ambiguous records or missing IDs/dates should be needs_review. Never claim a gap is proven. Do not invent facts."""
    payload = {"date_matching_window_days":window,"records":cases}
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=MODEL,
            contents=instructions + "\n\nAnalyze these records and return only the requested JSON:\n" + json.dumps(payload, ensure_ascii=False),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )
    except Exception as e:
        # Keep the demo usable when Gemini is unavailable, rate-limited, or temporarily overloaded.
        msg = str(e)
        fallback_results = []
        for case in cases:
            ext_item = case["external_interaction"]
            matches = case["possible_crm_matches"]
            if not ext_item.get("customer_id") or not ext_item.get("date"):
                status = "needs_review"
                reason = "Customer ID or date is missing, so matching is uncertain."
                matched_row = None
            elif not matches:
                status = "potential_missing"
                reason = "No CRM activity with the same customer ID was found within the selected date window."
                matched_row = None
            else:
                matched_row = matches[0].get("source_row")
                ext_text = (ext_item.get("text", "") + " " + ext_item.get("channel", "")).lower()
                crm_text = " ".join(
                    str(m.get(k, "")) for m in matches
                    for k in ("text", "channel", "follow_up_task", "task_due_date")
                ).lower()
                commitment_words = ("follow up", "follow-up", "call back", "callback", "send", "share", "schedule", "book", "demo", "proposal", "quote", "next week", "tomorrow")
                commitment = any(word in ext_text for word in commitment_words)
                task_present = any(str(m.get("follow_up_task", "")).strip() for m in matches)
                if commitment and not task_present:
                    status = "follow_up_gap"
                    reason = "A possible commitment keyword appears in the external interaction, but no follow-up task is recorded in the candidate CRM rows."
                else:
                    status = "matched"
                    reason = "A CRM activity for the same customer was found within the selected date window. Confirm that its content refers to this interaction."
            fallback_results.append({
                "source_row": ext_item.get("source_row"),
                "status": status,
                "matched_crm_row": matched_row,
                "commitment": "Possible commitment keyword detected; verify manually." if status == "follow_up_gap" else "Not determined by local rules.",
                "reason": reason,
                "recommended_action": "Review the external record and candidate CRM activity; confirm or correct the CRM entry manually.",
                "confidence": "low" if status in ("potential_missing", "follow_up_gap", "needs_review") else "medium",
            })
        return {
            "summary": "Gemini AI was temporarily unavailable, so the system completed this run using its built-in local rule-based analysis. Results are preliminary and should be verified by a human reviewer.",
            "results": fallback_results,
        }
    raw = (response.text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    try:
        data = json.loads(raw)
    except Exception:
        raise RuntimeError("Gemini returned an unreadable result. Try fewer rows or run again.")
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise RuntimeError("The Gemini response did not contain the expected results.")
    return data

@app.route("/", methods=["GET","POST"])
def index():
    result = None; error = ""; summary = ""; ext_n = crm_n = 0
    counts = {"matched":0,"potential_missing":0,"follow_up_gap":0,"needs_review":0}
    if request.method == "POST":
        try:
            window = max(0, min(int(request.form.get("date_window","1")), 7))
            ext = load_csv(request.files.get("external_file"), "external interaction")
            crm = load_csv(request.files.get("crm_file"), "CRM activity")
            ext_n, crm_n = len(ext), len(crm)
            result = analyse(ext, crm, window)
            summary = str(result.get("summary","Analysis completed."))
            result = result["results"]
            for r in result:
                if r.get("status") not in counts: r["status"] = "needs_review"
                counts[r["status"]] += 1
        except Exception as e:
            error = str(e)
    return render_template("index.html", results=result, error=error, summary=summary,
        ext_n=ext_n, crm_n=crm_n, counts=counts, model="Gemini AI + Local Rule-Based Fallback")

@app.errorhandler(413)
def too_big(_e):
    return "Upload too large. Keep total CSV upload size under 8 MB.", 413

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
