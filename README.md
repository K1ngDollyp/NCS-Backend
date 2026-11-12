# VITALIS — The Intelligent Healthcare Coordination Network (Backend)

Competition Prototype & Production Foundation for the **16th Edition Information Technology Development Contest (ITDC 2026)**.

Theme: *Innovative Digital Solutions for Accessible and Intelligent Healthcare Delivery* (Chrisland University, Abeokuta, Ogun State).

---

## 🏥 Architecture & Key Modules

The backend is built as a typed, production-grade **FastAPI** modular service with **SQLAlchemy**, **Argon2** password hashing, **JWT RBAC**, and **SQLite/PostgreSQL** support.

1. **Centralized Hospital Workflow (VITALIS HOSPITAL)**
   - **Reception:** Patient search, assisted registration, unique encounter issuance, walk-in/referral intake, emergency priority bypass.
   - **Nursing:** Vital signs logging (`systolic_bp`, `diastolic_bp`, `temperature`, `spo2`, `pulse_rate`, etc.), clinician-reviewed threshold warnings, queue handover to Doctor.
   - **Doctor:** Consolidated patient timeline, clinical consultation notes, differential diagnosis review, investigation ordering.
   - **Laboratory & Radiology:** Diagnostic work queue, status transitions (`requested` -> `acknowledged` -> `in_progress` -> `result_entered` -> `verified`), verified result publication.
2. **Deterministic Triage & Red-Flag Safeguards (VITALIS AI)**
   - Clinician-approved deterministic rules for life-threatening emergencies (`EMERGENCY_RED`, `URGENT_YELLOW`, `ROUTINE_GREEN`).
   - Emergency guidance displayed immediately without waiting for LLM or external calls.
3. **Facility Suitability Matching (VITALIS ROUTE)**
   - Algorithm: \(S = 0.40C + 0.25A + 0.20D + 0.15V\) (Service Compatibility, Reported Availability, Distance, Verification & Freshness).
4. **Consent & Secure QR Identity (VITALIS CONNECT)**
   - High-entropy, short-lived (5-10 min) single-use tokens; server stores only the SHA-256 hash.
   - Zero medical history or PII encoded into the QR code.
   - Automatic revocation, expiry enforcement, and scoped record disclosure.
5. **Clinical Decision Support (VITALIS INTELLIGENCE)**
   - Longitudinal history analysis, evidence-based differential suggestions with source citations.
   - Pre-computation medication safety checker (drug-allergy conflicts and major drug-drug interactions).
   - Non-diagnostic drafting: explicit clinician review, edit, and sign-off required.
   - Family history risk tracking.
6. **Inter-Hospital Record Exchange (VITALIS TRANSFER)**
   - Referral package generation, patient consent recording, secure token dispatch, and Hospital B receipt/access logging without overwriting source records.
7. **Audit & Governance (VITALIS ADMIN)**
   - Immutable audit logging for all clinical, diagnostic, consent, and authentication events.

---

## 🚀 Quickstart & Setup

### 1. Requirements
- Python 3.10+ (tested with Python 3.14)
- Dependencies in `requirements.txt`

### 2. Installation
```powershell
pip install -r requirements.txt
```

### 3. Initialize & Seed Database
A ready-to-demo synthetic dataset is pre-configured with facilities in Abeokuta (FMC Abeokuta, State Hospital Sokenu, Chrisland Health Clinic), clinical services, staff profiles, and sample patient records:
```powershell
python -m app.core.seed
```

### 4. Run Server
```powershell
python -m uvicorn app.main:app --reload --port 8000
```
- Interactive Swagger API Documentation: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- Interactive ReDoc: [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)

---

### 5. Web App (Frontend)
React + TypeScript + Vite + Tailwind, in [`frontend/`](frontend/). The dev server proxies `/api` to the backend on port 8000.
```powershell
cd frontend
npm install
npm run dev        # http://localhost:5173
```

**One-command demo:** `.\start-demo.ps1` resets the demo data, starts both servers and opens the browser. See [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) for the presenter run sheet.

**Demo story:** Folake Adewale (`VIT-2026-0002`, login `folake@example.com`) has history at State Hospital Sokenu and Chrisland Health Services and is seen at FMC Abeokuta for the first time: one-time-code consent, then nursing vitals, then VITALIS AI (cross-hospital allergy catch), then lab.

---

## 👥 Demo Accounts (Password: `vitalis2026`)

| Role | Identifier / Email | Facility | Department |
|---|---|---|---|
| **Reception Officer** | `reception@fmc.vitalis.ng` | FMC Abeokuta | Reception |
| **Nurse** | `nurse@fmc.vitalis.ng` | FMC Abeokuta | Nursing Station |
| **Doctor (Hospital A)** | `doctor@fmc.vitalis.ng` | FMC Abeokuta | Consultation / Clinics |
| **Lab Scientist** | `lab@fmc.vitalis.ng` | FMC Abeokuta | Diagnostics Lab |
| **Radiologist** | `rad@fmc.vitalis.ng` | FMC Abeokuta | Radiology |
| **Doctor (Hospital B)** | `doctor@statehospital.vitalis.ng` | State Hospital Sokenu | Clinics |
| **Patient** | `olumide@example.com` | — | Patient Profile (`VIT-2026-0001`) |

---

## 🧪 Running Automated Tests

Run the full automated test suite:
```powershell
python -m pytest -v
```

All 7 core test suites verify:
- System health & OpenAPI configuration
- Emergency red-flag triage detection
- Facility matching algorithm scoring breakdown
- End-to-end 4-department hospital workflow (Reception -> Nursing -> Doctor -> Lab -> Doctor review)
- Medication allergy conflicts & drug interaction safeguards
- QR grant creation, single-use token hashing, and redemption audit
- Inter-hospital record transfer and consent lifecycle
