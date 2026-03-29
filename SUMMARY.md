# MediNotes Pro

AI-powered consultation assistant for healthcare professionals. Transforms doctor's consultation notes into professional summaries, action items, patient communications, E&M service level codes, and CPT billing codes — with automatic HIPAA de-identification.

## Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 16, React 19, Tailwind CSS 4 | Consultation form, real-time streaming UI |
| Backend | Python FastAPI | API endpoint, OpenAI integration, billing code lookup |
| Auth | Clerk | JWT-based authentication, subscription gating |
| AI | OpenAI GPT-5-nano | Summarization, specialty validation, E&M coding, billing extraction |
| Billing API | Sequoia Codes | CPT code lookup |
| Deployment | Vercel | Dual-stack (Next.js + Python serverless) |

## Features

### 1. Consultation Summarization
Generates three sections from doctor's notes via streaming SSE:
- Summary of visit for the doctor's records
- Next steps for the doctor
- Draft email to patient in patient-friendly language

### 2. Specialty Mismatch Validation
Validates that consultation notes match the selected medical specialty before processing. Blocks generation and displays a warning if a mismatch is detected.

### 3. CPT Billing Code Extraction
Extracts billable items from notes (procedures, in-office medications, diagnostic tests) and looks up corresponding CPT codes via the Sequoia Codes API. Runs in parallel with summary generation.

### 4. E&M Service Level Coding
Determines the appropriate Evaluation & Management CPT code (99202–99215) based on 2021 AMA/CMS Medical Decision Making guidelines:
- Number and complexity of problems
- Amount and complexity of data reviewed
- Risk of complications, morbidity, or mortality

Runs in parallel with summary generation and billing code lookup.

### 5. HIPAA De-identification
Automatically redacts Protected Health Information (PHI) from consultation notes before sending to external AI services. Covers the 18 Safe Harbor identifiers including patient names, SSNs, phone numbers, email addresses, dates, and medical record numbers. Original values are restored in the user-facing output.

### 6. Subscription Protection
Product access is gated behind a Clerk-managed premium subscription plan with an integrated pricing table for non-subscribers.

## Data Flow

```
User submits consultation form
  → Clerk JWT authentication
  → HIPAA de-identification (redact PHI)
  → Specialty mismatch validation
  → Parallel processing:
      1. Summary generation (streaming)
      2. CPT billing code extraction + Sequoia API lookup
      3. E&M service level calculation
  → SSE stream to frontend (PHI restored in output)
  → UI renders: summary, E&M card, billing codes table, PHI badge
```

## Project Structure

```
saas/
├── pages/
│   ├── index.tsx          # Landing page with feature cards
│   ├── product.tsx        # Consultation form and results UI
│   ├── _app.tsx           # Clerk provider wrapper
│   └── _document.tsx      # HTML document structure
├── api/
│   ├── index.py           # FastAPI backend (all endpoints)
│   └── hipaa_deidentify.py # PHI redaction/restoration module
├── styles/
│   └── globals.css        # Tailwind imports and custom styles
├── .agents/skills/
│   └── healthcare-data-domain/
│       └── SKILL.md       # Clinical terminology and coding reference
├── vercel.json            # Deployment config (Next.js + Python)
├── package.json           # Frontend dependencies
└── .env.local             # API keys (gitignored)
```

## Local Development

```bash
# Frontend (port 3000)
npm run dev

# Backend (port 8000)
uvicorn api.index:app --reload --port 8000
```

### Required Environment Variables

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk frontend auth |
| `CLERK_SECRET_KEY` | Clerk backend auth |
| `CLERK_JWKS_URL` | JWT verification endpoint |
| `NEXT_PUBLIC_API_URL` | Backend URL (http://localhost:8000 for dev) |
| `OPENAI_API_KEY` | OpenAI API access |
| `SEQUOIA_CODES_API_KEY` | CPT billing code lookup |

## Supported Specialties

General Practice, Cardiology, Dermatology, Endocrinology, Gastroenterology, Neurology, Obstetrics & Gynecology, Oncology, Ophthalmology, Orthopedics, Pediatrics, Psychiatry, Pulmonology, Rheumatology, Urology
