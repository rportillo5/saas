import os
import json
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

        billing_table = lookup_billing_codes(visit.notes)
        if billing_table:
            yield "data: \n\n"
            yield "data: <!-- BILLING_CODES_START -->\n\n"
            yield f"data: {billing_table}\n\n"
            yield "data: <!-- BILLING_CODES_END -->\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def lookup_billing_codes(notes: str) -> str:
    api_key = os.getenv("SEQUOIA_CODES_API_KEY")
    if not api_key:
        return ""

    resp = http_requests.get(
        "https://api.sequoiacodes.com/v1/cpt/searchCode",
        params={"query": notes, "limit": 10},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    if resp.status_code != 200:
        return ""

    results = resp.json().get("data", {}).get("results", [])
    if not results:
        return ""

    codes = [
        {"code": item.get("code", ""), "description": item.get("short_description", "")}
        for item in results
    ]
    return json.dumps(codes)