# VITALIS: live demo run sheet

**Story in one line:** Mrs Folake Adewale (54) has been seen at **State Hospital Sokenu** (twice) and **Chrisland Health Services** (once). Today she feels unwell at home. VITALIS CareConnect finds her a hospital that can actually treat her (**FMC Abeokuta**), she shares her records from her phone, FMC confirms before she travels, and VITALIS AI spots what no single hospital could.

**Target length:** about 7 minutes. All accounts use the password `vitalis2026`; the login page has one-click buttons.

**Two screens make this demo.** The phone part works best on a real phone (same Wi-Fi, `http://<laptop-ip>:5173`, log in as **Patient's phone**) held up next to the projector. Without a phone, open a second browser window logged in as **Patient's phone**.

---

## Before you present

1. Run `.\start-demo.ps1` from the repo root. It resets the demo data, starts both servers and opens the browser.
   - Manual alternative: `python -m app.core.seed --reset`, then `python -m uvicorn app.main:app --port 8000`, then in `frontend/` run `npm run dev`.
2. **Optional (high impact):** open `http://<laptop-ip>:5173` on a phone on the same Wi-Fi and log in as **Patient app**. During step 1 the one-time code appears live on the phone. Hold it up.
3. Zoom the browser to 90% on a 1366px projector so the doctor workspace fits.
4. Rehearse at least twice and reset between runs (`.\start-demo.ps1`).

---

## The run

### 0. Hook (30s): login page
> "Today, if you've been treated at three hospitals, you have three separate paper files and no hospital can see the others. VITALIS makes it one patient, one record, every hospital, and the patient stays in control."

### 1. At home: the patient's phone (1.5 min): **Patient's phone**
- **Check my symptoms**. Tap **Headache**, **Blurred vision**, **Excessive thirst**, **Frequent urination**; leave **About a week**. Tap **Check my symptoms**.
- **Say:** "The emergency check is deterministic rules, not AI, so it never waits on a model."
- **Find a hospital that can see me**, then tap **Heart and blood pressure**.
- **Say:** "This is not a directory. State Hospital is closer to her, but it doesn't report a heart and blood pressure service, so VITALIS leaves it out and says why. Availability is what the hospital itself reported, with when it was last confirmed." Open **Why this hospital** to show the transparent score.
- **Ask FMC Abeokuta to see me**. Point at **Share my records from other hospitals**: "Only FMC, for 24 hours, revocable. This is her consent." Tap **Share and send to FMC Abeokuta**.
- The phone now says **Waiting for the hospital to confirm**. **Say:** "She doesn't travel until the hospital confirms it can take her."

### Optional (45s): emergency coordination. Do this only if time allows, and reset afterwards
- On the phone: **Check my symptoms** → **Chest pain** → **Find a hospital that will take me now**. The phone shows **Asking FMC Abeokuta to confirm** and the list of hospitals VITALIS will try next.
- As **Reception**: the red **Emergency requests** card appears. **Say:** "VITALIS never sends a patient to a hospital that hasn't said yes." Click **We can receive this patient**: the phone shows the ambulance and ETA (simulated dispatch).
- For the decline story, type *active labour* in "Anything else?" instead: FMC clicks **Can't take** → the phone instantly switches to **Asking State Hospital, Sokenu**.

### 2. Reception (45s): click **1 Reception**
- **Incoming referrals** is at the top: her symptoms, "Care needed: Heart and blood pressure", and **Patient shared their records from 2 other hospitals**.
- **Confirm we can see this patient**. Hold up the phone: it changes to **The hospital can see you** with her VITALIS ID.
- **Say:** "She arrives." Click **Patient arrived: start visit**. The complaint is already filled in from her phone; **Send to triage**.
- **Say:** "No paper, no repeating her story, and her history from two other hospitals is already here, because *she* shared it."
- *(Backup path, for walk-ins without the app: search **VIT-2026-0002** → **Request access from patient** → one-time code. Mention it; don't demo both.)*

### 3. Nurse (45s): click **2 Nurse**
- Select Folake, click **Fill demo readings**, then point at the **red** BP 174/108 and glucose 236.
- **Say:** "Abnormal values flag as they're typed, and next to each one is her *previous* reading from State Hospital. BP was 156; it's climbing."
- **Save and send to doctor**. Priority becomes **Urgent** automatically.

### 4. Doctor (2.5 min, the centrepiece): click **3 Doctor**
- Open Folake. Scroll slowly:
  - **Patient header:** allergy in red, "Patient consented".
  - **Right column:** "History from other hospitals", the BP chart (each dot coloured by hospital), labs from other hospitals.
- Click **Run VITALIS AI** (top right of the visit card) and let the steps animate. Read one or two aloud ("Detected trend: systolic 148 → 152 → 156 → 174 across 3 facilities").
- **Say the three wins:**
  1. **Red flag:** "Markedly raised BP with blurred vision: rule out hypertensive emergency."
  2. **Probable new type 2 diabetes:** expand it and show that every piece of evidence cites *its source hospital and date*. "Our own trained diabetes model contributes, alongside WHO criteria."
  3. **Cross-hospital safety catch:** "Hydrochlorothiazide is the textbook next drug for her blood pressure. VITALIS says **avoid**, because a *different hospital* recorded a sulfonamide allergy seven months ago. Without VITALIS, this doctor would never know."
- In **Risk models trained by the VITALIS team**, open *"5 of 8 inputs came from the patient’s record"*. **Say:** "We show exactly which inputs were measured and which were assumed, and we show a Low / Moderate / High band, not a fake-precise percentage, because these models are not yet validated on Nigerian patients. No black box."
- Expand diabetes, click **Order** next to HbA1c, then **Accept and draft note**. Click **Use demo finding** under Examination.
- **Say:** "The AI suggests, the doctor decides. Nothing enters the record until a clinician signs it."
- In **Prescribe**, type `Hydrochlorothiazide`, then **Check safety**: blocked. Change it to `Lisinopril 10 mg`, then **Sign note**.

### 5. Lab (45s): click **4 Laboratory**
- Select HbA1c, then **Sample collected**, then **Fill demo result** (7.4% shows **High**), then **Save result**, then **Verify & release to doctor**.
- (Optional) Back as Doctor: the "New results are ready" banner appears and HbA1c 7.4% confirms the diagnosis.

### 6. Patient (30s): click **Patient’s phone**
- **Who looked** tab: "She sees exactly who looked at her record, when, and from which hospital, and can **revoke** with one tap."

### 7. Close (20s)
> "She found the right hospital before travelling. She shared her record from her phone. The hospital confirmed before she left home. And an AI caught an allergy-drug conflict that no single hospital could see. One patient, one record, every hospital. That's VITALIS."

---

## If something goes wrong
| Problem | Fix |
|---|---|
| "Cannot reach the VITALIS server" | Backend isn't running: `python -m uvicorn app.main:app --port 8000` |
| Folake not in a queue | A previous rehearsal used her up. Log in as **Medical director**, then **Reset demo data** (or run `.\start-demo.ps1`) |
| Code expired (10 min) | Click **Resend** in the code dialog |
| Projector too small | Browser zoom 80–90% |
| Folake's phone still shows an old referral or emergency | Reset demo data (each rehearsal leaves a completed referral and a 24 h consent behind) |

---

## Likely judge questions and honest answers

**"Is the AI real, or scripted?"**
Real and deterministic. The engine (`app/services/clinical_ai.py`) reads the actual record. Change the vitals and the output changes. It combines WHO/NICE-based clinical rules with two machine-learning models the team trained (SVC for diabetes, Random Forest for heart disease) and runs entirely on our own server. No patient data goes to an external AI service.

**"Why not use ChatGPT / an LLM?"**
Patient safety and privacy. Our outputs are traceable to source data and guidelines, they can't hallucinate a lab value, they cost nothing per patient, and they work offline. An LLM could later *summarise* the output in plain language, but it would not be the decision engine.

**"How accurate are your models?"**
Give the team's measured accuracy/AUC from training (fill in: diabetes ___ / heart ___). Be honest about limits: the diabetes model was trained on the Pima dataset (one population), and several heart-model inputs require exercise testing, which is why the UI labels those inputs *assumed* and calls it a "screen". Next step: retrain on Nigerian clinical data with partner hospitals.

**"What stops a hospital from snooping?"**
A facility sees only its own records until the patient gives a one-time code. Access is facility-scoped, expires after 24 hours, can be revoked by the patient, and every view is in an immutable audit log (Admin → Governance & audit). Only the hash of the code is stored.

**"What if the patient has no phone or is unconscious?"**
Emergency override (break-glass) with mandatory justification and heightened audit is the planned next feature. The emergency flag at reception already bypasses the queue.

**"How do you know the hospital can actually treat her?"**
Hospitals report their own services and availability, with a timestamp and the name of who confirmed it. Matching filters out any hospital that lacks the needed service *before* it looks at distance, then ranks with a transparent score (service 40%, availability 25%, distance 20%, verification and freshness 15%). Unknown availability is never treated as available, and the hospital must explicitly confirm before the patient is told to travel.

**"Is the patient symptom check an AI chatbot?"**
No, deliberately. It is a rule-based check: emergency warning signs trigger "call 112" instantly and never wait for a model. It never tells the patient a diagnosis. A language model could later help patients describe symptoms in Yoruba or Pidgin, but it would never decide urgency.

**"Is the SMS real?"**
In the prototype it's simulated (shown on screen and in the patient app). Production would use an SMS gateway such as Termii or Africa's Talking.

**"How does this scale / interoperate?"**
FastAPI with a PostgreSQL-ready data model and role-based access control. The record structure maps to HL7 FHIR resources (Patient, Encounter, Observation, DiagnosticReport), which is the roadmap for connecting existing hospital systems.

**"Is this real patient data?"**
No. All patients and clinicians are fictional, synthetic data.
