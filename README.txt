CUSTOMER INTERACTION GAP DETECTOR — PYTHON + HTML AI PROTOTYPE

WHAT IT DOES
Upload two CSV files: (1) external interaction records and (2) CRM activity records. Python/Flask compares likely records by customer ID/date. The OpenAI Responses API interprets notes, identifies possible customer commitments, flags possible missing activities/follow-up tasks, and suggests actions.

IMPORTANT
- No demo data is preloaded.
- This version is NOT connected to live Zoho CRM. It uses CSV exports.
- It does not automatically read WhatsApp, emails, or phone calls.
- Findings require human verification.
- Uploaded files are not saved to disk by this app, but record text is sent to the AI API. Use anonymized or synthetic data and only data you are authorized to process.
- API usage may incur charges.
- Prototype limit: 60 external rows and 180 CRM rows per run.

WINDOWS SETUP
1. Install Python 3.10 or newer.
2. Extract this ZIP.
3. Open the extracted folder in File Explorer. Click the address bar, type cmd, press Enter.
4. Run:
   py -m venv .venv
   .venv\Scripts\activate
   py -m pip install -r requirements.txt
5. Create an OpenAI API key in the OpenAI API platform. ChatGPT subscription and API billing are separate.
6. In the same Command Prompt window, set your key (replace placeholder):
   set OPENAI_API_KEY=your_api_key_here
   Do NOT paste the key into app.py or HTML, and do not share it.
7. Start:
   py app.py
8. Open:
   http://127.0.0.1:5000
9. Upload the two CSV files and click "Analyse interactions with AI".
10. Stop with Ctrl+C in the command prompt.

CSV COLUMNS
External CSV: customer_id, interaction_date (or date), channel, interaction_text (or message/notes), deal_id (optional)
CRM CSV: customer_id, activity_date (or date), activity_type, notes (or description/summary), deal_id (optional), follow_up_task (optional), task_due_date (optional)
Use consistent customer IDs and preferably YYYY-MM-DD dates.

MODEL
Default model setting is OPENAI_MODEL=gpt-5.5. If your API account does not have access to that model, set OPENAI_MODEL to a model available to your account in the same terminal before starting the app.

WHAT TO TELL YOUR PROFESSOR
"The prototype uses Python and Flask for the backend, HTML for the dashboard, and the OpenAI Responses API for AI-based interpretation. Python first narrows possible CRM matches by customer ID and date. The AI then evaluates message meaning, identifies potential commitments and follow-up gaps, and recommends actions. This version demonstrates the workflow using CSV uploads; live Zoho CRM integration is a future development step."

TROUBLESHOOTING
OPENAI_API_KEY error: set the environment variable in the same terminal and restart.
Authentication/quota error: verify the API key and API billing/limits.
Model access error: set OPENAI_MODEL to a model enabled for your API account.
CSV error: include customer ID and date columns; interaction text/notes are strongly recommended.
