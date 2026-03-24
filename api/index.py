import os
import json
from concurrent.futures import ThreadPoolExecutor
import requests as http_requests  # type: ignore
from fastapi import FastAPI, Depends  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import StreamingResponse  # type: ignore
from pydantic import BaseModel  # type: ignore
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials  # type: ignore
from openai import OpenAI  # type: ignore

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
clerk_config = ClerkConfig(jwks_url=os.getenv("CLERK_JWKS_URL"), jwks_cache_keys=True)
clerk_guard = ClerkHTTPBearer(clerk_config)


class Visit(BaseModel):
    patient_name: str
    date_of_visit: str
    specialty: str
    notes: str


system_prompt = """
You are provided with notes written by a doctor from a patient's visit.
Your job is to summarize the visit for the doctor and provide an email.
Reply with exactly three sections with the headings:
### Summary of visit for the doctor's records
### Next steps for the doctor
### Draft of email to patient in patient-friendly language
"""


def user_prompt_for(visit: Visit) -> str:
    return f"""Create the summary, next steps and draft email for:
Patient Name: {visit.patient_name}
Date of Visit: {visit.date_of_visit}
Specialty: {visit.specialty}
Notes:
{visit.notes}"""


@app.post("/api")
def consultation_summary(
    visit: Visit,
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
):
    user_id = creds.decoded["sub"]  # Available for tracking/auditing
    client = OpenAI()

    user_prompt = user_prompt_for(visit)

    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Start billing code extraction in parallel with the summary stream
    billing_executor = ThreadPoolExecutor(max_workers=1)
    billing_future = billing_executor.submit(lookup_billing_codes, client, visit.notes)

    stream = client.chat.completions.create(
        model="gpt-5-nano",
        messages=prompt,
        stream=True,
    )

    def event_stream():
        for chunk in stream:
            text = chunk.choices[0].delta.content
            if text:
                lines = text.split("\n")
                for line in lines[:-1]:
                    yield f"data: {line}\n\n"
                    yield "data:  \n"
                yield f"data: {lines[-1]}\n\n"

        billing_table = billing_future.result(timeout=30)
        billing_executor.shutdown(wait=False)
        if billing_table:
            yield "data: \n\n"
            yield "data: <!-- BILLING_CODES_START -->\n\n"
            yield f"data: {billing_table}\n\n"
            yield "data: <!-- BILLING_CODES_END -->\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


extraction_prompt = """You are an experienced ICD-10 and CPT medical billing coder.
Given the doctor's consultation notes below, extract ONLY the specific billable items
that were ACTUALLY PERFORMED or PRESCRIBED during this visit.

Include:
- Procedures performed (e.g., intramuscular injection, wound suture, X-ray)
- Medications administered in-office (e.g., intramuscular corticosteroid injection)
- Diagnostic tests performed (e.g., urinalysis, blood draw)
- E&M service level (e.g., office visit established patient)

Do NOT include:
- Medications prescribed for home use (e.g., "take ibuprofen 400mg twice daily")
- Future referrals or follow-ups not yet performed
- General diagnoses or symptoms without a billable action

Return ONLY a JSON array of short, specific search terms for each billable item.
Example: ["office visit established patient moderate complexity", "intramuscular corticosteroid injection", "chest X-ray 2 views"]
If no billable items are found, return [].
Return ONLY the JSON array, no other text."""


def extract_billable_items(client: OpenAI, notes: str) -> list[str]:
    resp = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": extraction_prompt},
            {"role": "user", "content": notes},
        ],
    )
    text = resp.choices[0].message.content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return []


def lookup_billing_codes(client: OpenAI, notes: str) -> str:
    api_key = os.getenv("SEQUOIA_CODES_API_KEY")
    if not api_key:
        return ""

    billable_items = extract_billable_items(client, notes)
    if not billable_items:
        return ""

    def search_code(item: str):
        resp = http_requests.get(
            "https://api.sequoiacodes.com/v1/cpt/searchCode",
            params={"query": item, "limit": 1},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("data", {}).get("results", [])
        if results:
            return results[0]
        return None

    with ThreadPoolExecutor(max_workers=len(billable_items)) as pool:
        search_results = list(pool.map(search_code, billable_items))

    seen_codes = set()
    codes = []
    for result in search_results:
        if result:
            code = result.get("code", "")
            if code and code not in seen_codes:
                seen_codes.add(code)
                codes.append({
                    "code": code,
                    "description": result.get("short_description", ""),
                })

    if not codes:
        return ""
    return json.dumps(codes)