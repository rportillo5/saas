import os
import json
from dotenv import load_dotenv

load_dotenv(".env.local")
from concurrent.futures import ThreadPoolExecutor
import requests as http_requests  # type: ignore
from fastapi import FastAPI, Depends  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import StreamingResponse  # type: ignore
from pydantic import BaseModel  # type: ignore
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials  # type: ignore
from openai import OpenAI  # type: ignore
from api.hipaa_deidentify import PHIRedactor, restore_streaming

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
Close the patient email with exactly this signature (do not repeat it):
Dr. Ima Goode Pearson
[specialty] Department
(555) 555-5555
"""


def user_prompt_for(visit: Visit) -> str:
    return f"""Create the summary, next steps and draft email for:
Patient Name: {visit.patient_name}
Date of Visit: {visit.date_of_visit}
Specialty: {visit.specialty}
Notes:
{visit.notes}"""


specialty_check_prompt = """You are a medical specialty classifier.
Given a medical specialty and doctor's consultation notes, determine if the notes
are relevant to the specified specialty.

Reply with ONLY a JSON object in this exact format:
{"match": true} if the notes are relevant to the specialty
{"match": false, "reason": "<one sentence explanation>"} if the notes do NOT match

Be reasonable: General Practice covers a wide range of conditions.
Only flag a mismatch when the notes clearly belong to a different specialty."""


def check_specialty_match(client: OpenAI, specialty: str, notes: str) -> dict:
    resp = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": specialty_check_prompt},
            {"role": "user", "content": f"Specialty: {specialty}\n\nNotes:\n{notes}"},
        ],
    )
    text = resp.choices[0].message.content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"match": True}


@app.post("/api")
def consultation_summary(
    visit: Visit,
    creds: HTTPAuthorizationCredentials = Depends(clerk_guard),
):
    user_id = creds.decoded["sub"]  # Available for tracking/auditing
    client = OpenAI()

    # HIPAA de-identification: redact PHI before any external API call
    redactor = PHIRedactor(patient_name=visit.patient_name)
    redacted_notes, phi_mapping = redactor.redact(visit.notes)
    phi_detected = bool(phi_mapping)

    # Validate notes match the selected specialty (uses redacted notes)
    specialty_result = check_specialty_match(client, visit.specialty, redacted_notes)
    if not specialty_result.get("match", True):
        reason = specialty_result.get("reason", "The consultation notes do not appear to match the selected specialty.")
        def mismatch_stream():
            yield f"data: <!-- SPECIALTY_MISMATCH -->{reason}<!-- /SPECIALTY_MISMATCH -->\n\n"
        return StreamingResponse(mismatch_stream(), media_type="text/event-stream")

    # Build prompt with redacted patient name for external API
    redacted_visit = Visit(
        patient_name=f"[PHI_NAME_1]" if phi_detected else visit.patient_name,
        date_of_visit=visit.date_of_visit,
        specialty=visit.specialty,
        notes=redacted_notes,
    )
    user_prompt = user_prompt_for(redacted_visit)

    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Start billing code extraction and E&M calculation in parallel
    executor = ThreadPoolExecutor(max_workers=2)
    billing_future = executor.submit(lookup_billing_codes, client, redacted_notes)
    em_future = executor.submit(calculate_em_level, client, redacted_notes)

    stream = client.chat.completions.create(
        model="gpt-5-nano",
        messages=prompt,
        stream=True,
    )

    def event_stream():
        carry = ""
        for chunk in stream:
            text = chunk.choices[0].delta.content
            if text:
                # Restore PHI in streamed output
                restored, carry = restore_streaming(text, carry, phi_mapping)
                if restored:
                    lines = restored.split("\n")
                    for line in lines[:-1]:
                        yield f"data: {line}\n\n"
                        yield "data:  \n"
                    yield f"data: {lines[-1]}\n\n"

        # Flush any remaining carry buffer
        if carry:
            from api.hipaa_deidentify import restore
            final = restore(carry, phi_mapping)
            if final:
                yield f"data: {final}\n\n"

        # Append billing codes
        billing_table = billing_future.result(timeout=30)
        if billing_table:
            yield "data: \n\n"
            yield "data: <!-- BILLING_CODES_START -->\n\n"
            yield f"data: {billing_table}\n\n"
            yield "data: <!-- BILLING_CODES_END -->\n\n"

        # Append E&M level
        em_result = em_future.result(timeout=30)
        if em_result:
            yield "data: <!-- EM_LEVEL_START -->\n\n"
            yield f"data: {em_result}\n\n"
            yield "data: <!-- EM_LEVEL_END -->\n\n"

        # Append PHI status
        phi_categories = list({k.split("_")[1] for k in phi_mapping.keys()}) if phi_mapping else []
        phi_status = json.dumps({"phi_detected": phi_detected, "categories_found": phi_categories})
        yield f"data: <!-- PHI_STATUS_START -->\n\n"
        yield f"data: {phi_status}\n\n"
        yield f"data: <!-- PHI_STATUS_END -->\n\n"

        executor.shutdown(wait=False)

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


em_system_prompt = """You are an expert medical billing coder specializing in E&M (Evaluation and Management) coding using the 2021 AMA/CMS MDM (Medical Decision Making) guidelines.

Given consultation notes, determine the appropriate E&M CPT code.

## MDM Guidelines (2 of 3 elements must meet or exceed the level)

### Element 1: Number and Complexity of Problems
- Straightforward: 1 self-limited/minor problem
- Low: 2+ self-limited problems OR 1 stable chronic illness
- Moderate: 1+ chronic illness with mild exacerbation OR 2+ stable chronic illnesses OR 1 undiagnosed new problem with uncertain prognosis
- High: 1+ chronic illness with severe exacerbation OR 1 acute/chronic illness that poses threat to life or bodily function

### Element 2: Amount and Complexity of Data Reviewed
- Straightforward/None: Minimal or no data reviewed
- Limited: Review of prior external notes OR ordering of tests
- Moderate: Review of prior external notes AND ordering of tests OR independent interpretation of tests OR discussion with external physician
- Extensive: Independent interpretation of a test performed by another physician AND discussion with external physician

### Element 3: Risk of Complications, Morbidity, or Mortality
- Minimal: Over-the-counter drugs, minor surgery with no risk factors
- Low: Prescription drug management, minor surgery with risk factors
- Moderate: Prescription drug management requiring monitoring, decision about minor surgery with risk factors, decision about elective major surgery
- High: Drug therapy requiring intensive monitoring, decision about emergency major surgery, decision about hospitalization

## Code Mapping
| MDM Level | New Patient | Established Patient |
|---|---|---|
| Straightforward | 99202 | 99211 |
| Low | 99203 | 99212 |
| Moderate | 99204 | 99213 |
| High | 99205 | 99215 |

Note: Determine new vs established based on context clues in the notes (e.g., "new patient", "follow-up", "established", "returning").
If unclear, default to "Established".

Reply with ONLY a JSON object:
{"code": "99213", "patient_type": "Established", "mdm_level": "Moderate", "problems": "1 chronic illness with mild exacerbation", "data": "Review of lab results ordered", "risk": "Prescription drug management", "justification": "One sentence summary"}"""


def calculate_em_level(client: OpenAI, notes: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": em_system_prompt},
            {"role": "user", "content": notes},
        ],
    )
    text = resp.choices[0].message.content.strip()
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        return ""