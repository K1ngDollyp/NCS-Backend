import os
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def create_document():
    doc = Document()

    # Set Margins (0.75 in)
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.8)
        s.right_margin = Inches(0.8)

    # Palette
    COLOR_PRIMARY = RGBColor(6, 78, 59)      # Deep Emerald (#064e3b)
    COLOR_SECONDARY = RGBColor(16, 185, 129)  # Mint Accent (#10b981)
    COLOR_DARK = RGBColor(30, 41, 59)         # Slate 800
    COLOR_MUTED = RGBColor(100, 116, 139)     # Slate 500

    # Styles
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(10.5)
    normal_style.font.color.rgb = COLOR_DARK

    def set_cell_background(cell, fill_hex):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
        tcPr.append(shd)

    def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
        tcPr.append(tcMar)

    # --- Title & Cover Header ---
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    run_sub = title_p.add_run("THE INTELLIGENT HEALTHCARE COORDINATION NETWORK\n")
    run_sub.font.size = Pt(10)
    run_sub.font.bold = True
    run_sub.font.color.rgb = COLOR_SECONDARY

    run_title = title_p.add_run("VITALIS")
    run_title.font.size = Pt(28)
    run_title.font.bold = True
    run_title.font.color.rgb = COLOR_PRIMARY

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(16)
    r1 = sub_p.add_run("Complete Technical Architecture & System Blueprint (Backend & Frontend)\n")
    r1.font.size = Pt(13)
    r1.font.bold = True
    r1.font.color.rgb = COLOR_DARK
    r2 = sub_p.add_run("Competition Prototype • Startup-Ready Foundation • 16th Edition ITDC 2026\nChrisland University, Abeokuta, Ogun State")
    r2.font.size = Pt(10)
    r2.font.italic = True
    r2.font.color.rgb = COLOR_MUTED

    # Divider Line
    line_table = doc.add_table(rows=1, cols=1)
    line_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = line_table.rows[0].cells[0]
    set_cell_background(c, "064E3B")
    c.width = Inches(6.9)
    p = c.paragraphs[0]
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --- 1. Executive Overview ---
    h1 = doc.add_heading(level=1)
    r = h1.add_run("1. Executive Overview & Architectural Philosophy")
    r.font.color.rgb = COLOR_PRIMARY
    r.font.bold = True

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.add_run("VITALIS is an AI-assisted healthcare coordination platform designed to bridge two critical fragmentation gaps in African healthcare systems:\n")
    
    b1 = doc.add_paragraph(style='List Bullet')
    b1.add_run("External Healthcare Fragmentation (Patient-to-Facility): ").bold = True
    b1.add_run("Patients lack transparent visibility into which facility possesses the specific medical service they need, whether services are operational, and how to safely port their medical history without repeating diagnostic tests.")

    b2 = doc.add_paragraph(style='List Bullet')
    b2.add_run("Internal Departmental Fragmentation (Desk-to-Desk): ").bold = True
    b2.add_run("Within a hospital, Reception, Nursing, Doctor Consultation, and Diagnostics (Laboratory & Radiology) often operate in silos. VITALIS unifies these four departments under a single, coordinated, auditable Patient Encounter.")

    p_box = doc.add_paragraph()
    p_box.paragraph_format.space_before = Pt(6)
    p_box.paragraph_format.space_after = Pt(12)
    box_run = p_box.add_run("Core Design Principle: Patient Safety Before Automation. Emergency rules are deterministic. The AI/ML model serves as non-diagnostic documentation and decision support; it never autonomously diagnoses, prescribes, or replaces human clinical authority.")
    box_run.font.italic = True
    box_run.font.bold = True
    box_run.font.color.rgb = COLOR_PRIMARY

    # --- 2. High-Level Architecture Diagram Description ---
    h1 = doc.add_heading(level=1)
    r = h1.add_run("2. System Architecture & Tiered Layers")
    r.font.color.rgb = COLOR_PRIMARY
    r.font.bold = True

    p = doc.add_paragraph()
    p.add_run("VITALIS is engineered as a Modular Monolith in Python FastAPI with a Next.js 14+ PWA frontend and PostgreSQL/SQLite relational storage.")

    # Table of Tiers
    table = doc.add_table(rows=5, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Layer / Tier", "Components & Technologies", "Key Responsibilities"]
    col_widths = [Inches(1.5), Inches(2.3), Inches(3.1)]

    # Header Row
    for i, title in enumerate(headers):
        cell = table.cell(0, i)
        cell.width = col_widths[i]
        set_cell_background(cell, "064E3B")
        set_cell_margins(cell, 120, 120, 140, 140)
        p = cell.paragraphs[0]
        r = p.add_run(title)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(9.5)

    data = [
        ("Presentation Tier", "Next.js 14+ App Router, TypeScript, Tailwind CSS, shadcn/ui", "Patient PWA (triage, matching, QR sharing, records); Hospital Portal (Reception, Nursing, Doctor, Diagnostics); Admin Console."),
        ("API & Security Tier", "FastAPI, JWT Bearer Tokens, Argon2id, RBAC Dependencies", "Role-based and facility-scoped authorization, request validation, rate limiting, and immutable audit event logging."),
        ("Domain Services Tier", "FastAPI Domain Routers, Clinical State Machine, Routing Engine", "Centralized hospital encounter lifecycle; VITALIS ROUTE facility suitability; VITALIS CONNECT QR grants; VITALIS TRANSFER inter-hospital exchange."),
        ("Persistence Tier", "PostgreSQL / SQLite, SQLAlchemy ORM, Private Object Storage", "Relational entities, audit log storage, versioned clinical notes, encrypted object keys for diagnostic imaging and documents.")
    ]

    for row_idx, row_data in enumerate(data, start=1):
        for col_idx, text in enumerate(row_data):
            cell = table.cell(row_idx, col_idx)
            cell.width = col_widths[col_idx]
            bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
            set_cell_background(cell, bg)
            set_cell_margins(cell, 100, 100, 120, 120)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(text)
            r.font.size = Pt(9)
            if col_idx == 0:
                r.font.bold = True
                r.font.color.rgb = COLOR_PRIMARY

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # --- 3. Centralized 4-Department Hospital Workflow ---
    h1 = doc.add_heading(level=1)
    r = h1.add_run("3. Centralized Hospital Workflow: The Four Departments")
    r.font.color.rgb = COLOR_PRIMARY
    r.font.bold = True

    p = doc.add_paragraph()
    p.add_run("A patient is registered once and moves through role-scoped departmental queues. Every department contributes structured data to the same persistent Encounter:")

    dept_data = [
        ("Reception (Intake)", "Patient search or assisted registration. Captures arrival mode, reason for visit, complaint, referral source, and emergency bypass flag. Generates unique encounter number (ENC-FAC-YYMMDD-XXX) and routes to Nursing queue."),
        ("Nursing (Observations)", "Measures and records vital signs (Systolic/Diastolic BP, Pulse Rate, Temperature, SpO2, Respiratory Rate, Pain Score). Automatically evaluates clinical warning thresholds (e.g. Temp > 37.8C or SpO2 < 94%) and alerts attending clinicians."),
        ("Doctor (Consultation)", "Consolidated review of intake, nursing vitals, prior medical history, and allergies. AI-assisted differential diagnosis drawer (with evidence citations). Places investigation orders (Lab/Radiology) and signs clinical progress/disposition notes."),
        ("Diagnostics (Lab & Rad)", "Receives orders in role-specific work queues. Steps order through requested -> acknowledged -> in_progress -> result_entered -> verified. Returns verified results directly to Doctor's review console.")
    ]

    for title, desc in dept_data:
        p = doc.add_paragraph(style='List Bullet')
        r1 = p.add_run(f"{title}: ")
        r1.bold = True
        r1.font.color.rgb = COLOR_PRIMARY
        p.add_run(desc)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # --- 4. Mathematical Algorithms & Security Models ---
    h1 = doc.add_heading(level=1)
    r = h1.add_run("4. Core Algorithmic & Security Engines")
    r.font.color.rgb = COLOR_PRIMARY
    r.font.bold = True

    # 4.1 ROUTE
    h2 = doc.add_heading(level=2)
    h2.add_run("4.1 VITALIS ROUTE — Facility Matching Algorithm").font.color.rgb = COLOR_SECONDARY
    p = doc.add_paragraph()
    p.add_run("The platform computes a multi-dimensional prototype suitability score (0-100):\n")
    p.add_run("S = 0.40*C + 0.25*A + 0.20*D + 0.15*V\n").bold = True
    
    b1 = doc.add_paragraph(style='List Bullet')
    b1.add_run("C (Service Compatibility - 40%): ").bold = True
    b1.add_run("Hard filter. If a facility cannot provide the essential clinical service, it is excluded (score = 0).")
    
    b2 = doc.add_paragraph(style='List Bullet')
    b2.add_run("A (Reported Availability - 25%): ").bold = True
    b2.add_run("Available = 100%, Limited = 60%, Unknown = 30%, Unavailable = 0%. Unknown availability is never treated as confirmed.")
    
    b3 = doc.add_paragraph(style='List Bullet')
    b3.add_run("D (Distance Suitability - 20%): ").bold = True
    b3.add_run("Haversine great-circle distance decay (<=2km: 100%, 10km: 62%, 30km: 22%).")

    b4 = doc.add_paragraph(style='List Bullet')
    b4.add_run("V (Verification & Data Freshness - 15%): ").bold = True
    b4.add_run("Verified = 100%, Pending = 60%. Time decay reduces score if last confirmed >24h (-15%) or >48h (-30%).")

    # 4.2 CONNECT
    h2 = doc.add_heading(level=2)
    h2.add_run("4.2 VITALIS CONNECT — Cryptographic QR Sharing").font.color.rgb = COLOR_SECONDARY
    p = doc.add_paragraph()
    p.add_run("Security Invariant: The QR code contains ZERO medical records, names, or diagnosis strings. It encodes a high-entropy random single-use token URL (32-byte urlsafe string). The server stores only the SHA-256 hash. Tokens expire within 5-10 minutes, support instant patient revocation, and enforce single-use redemption with audit logging.")

    # 4.3 Drug Safety
    h2 = doc.add_heading(level=2)
    h2.add_run("4.3 Pre-Computation Medication Safety Checker").font.color.rgb = COLOR_SECONDARY
    p = doc.add_paragraph()
    p.add_run("Before a doctor submits a proposed medication, the rule engine cross-references patient allergies and current active drugs against a curated clinical formulary (e.g. Penicillin cross-reactivity with Amoxicillin, QT prolongation risks between Ciprofloxacin and Artemether-Lumefantrine).")

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --- 5. Frontend Architecture ---
    h1 = doc.add_heading(level=1)
    r = h1.add_run("5. Frontend Architecture (Next.js 14+ PWA)")
    r.font.color.rgb = COLOR_PRIMARY
    r.font.bold = True

    p = doc.add_paragraph()
    p.add_run("The frontend provides two distinct, responsive experiences built on Next.js 14 App Router:\n")

    p1 = doc.add_paragraph(style='List Bullet')
    p1.add_run("Patient PWA (/patient/*): ").bold = True
    p1.add_run("Mobile-first interface featuring guided symptom intake wizard, nearby facility search with suitability explanations, consent and QR sharing screen, longitudinal health records, and referral status tracking.")

    p2 = doc.add_paragraph(style='List Bullet')
    p2.add_run("Hospital Staff Portal (/hospital/*): ").bold = True
    p2.add_run("High-density workstation interfaces for Reception (/reception), Nursing triage station (/nursing), Doctor consultation console (/doctor), and Laboratory/Radiology diagnostic queue (/diagnostics).")

    # Frontend Stack Table
    table = doc.add_table(rows=6, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.cell(0, 0).width = Inches(2.2)
    table.cell(0, 1).width = Inches(4.7)
    set_cell_background(table.cell(0, 0), "064E3B")
    set_cell_background(table.cell(0, 1), "064E3B")
    r0 = table.cell(0, 0).paragraphs[0].add_run("Frontend Layer")
    r0.bold = True; r0.font.color.rgb = RGBColor(255, 255, 255)
    r1 = table.cell(0, 1).paragraphs[0].add_run("Technology & Implementation")
    r1.bold = True; r1.font.color.rgb = RGBColor(255, 255, 255)

    fe_stack = [
        ("Framework", "Next.js 14+ (App Router) with React 18 & TypeScript"),
        ("Styling & Components", "Tailwind CSS + shadcn/ui (Radix UI primitives)"),
        ("State & Data Fetching", "TanStack React Query v5 for server cache & optimistic updates"),
        ("Low-Bandwidth Support", "PWA Service Worker static caching + IndexedDB local form drafts"),
        ("Visual Identity", "Deep Emerald (#064e3b), Mint Accent (#10b981), Warning Amber (#d97706)")
    ]

    for idx, (layer, tech) in enumerate(fe_stack, start=1):
        c1 = table.cell(idx, 0); c2 = table.cell(idx, 1)
        bg = "F8FAFC" if idx % 2 == 1 else "FFFFFF"
        set_cell_background(c1, bg); set_cell_background(c2, bg)
        set_cell_margins(c1, 80, 80, 100, 100); set_cell_margins(c2, 80, 80, 100, 100)
        c1.paragraphs[0].add_run(layer).bold = True
        c2.paragraphs[0].add_run(tech)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --- 6. Machine Learning Model Integration Guide ---
    h1 = doc.add_heading(level=1)
    r = h1.add_run("6. Machine Learning Model Integration Guide")
    r.font.color.rgb = COLOR_PRIMARY
    r.font.bold = True

    p = doc.add_paragraph()
    p.add_run("The backend includes a dedicated Model Adapter Interface (app/services/intelligence.py). When the team is ready to connect the custom diagnostic or triage ML model, simply implement the adapter:")

    code_p = doc.add_paragraph()
    code_p.paragraph_format.left_indent = Inches(0.3)
    r = code_p.add_run(
        "class VitalisMLModelAdapter:\n"
        "    @classmethod\n"
        "    def predict_differentials(cls, complaint, vitals, patient_context):\n"
        "        # 1. Call local PyTorch weights or remote model endpoint\n"
        "        # 2. Return standardized candidate list:\n"
        "        return [{\n"
        "            'condition': 'Plasmodium Falciparum Malaria',\n"
        "            'ranking': 1,\n"
        "            'confidence_signal': '0.92 (High suspicion)',\n"
        "            'suggested_tests': ['Malaria RDT', 'Blood Film', 'FBC']\n"
        "        }]"
    )
    r.font.name = 'Consolas'
    r.font.size = Pt(8.5)
    r.font.color.rgb = RGBColor(51, 65, 85)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --- 7. Verification & Demo Accounts ---
    h1 = doc.add_heading(level=1)
    r = h1.add_run("7. Verification Results & Seed Demo Accounts")
    r.font.color.rgb = COLOR_PRIMARY
    r.font.bold = True

    p = doc.add_paragraph()
    p.add_run("All 7 automated test suites (test_vitalis_api.py) have executed and passed: System Health, Triage Emergency Triggers, ROUTE Facility Matching, 4-Department Hospital Workflow, Medication Safety Pre-Check, QR Grant Redemption, and Inter-Hospital Transfers.\n")

    table = doc.add_table(rows=8, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.cell(0, 0).width = Inches(1.8)
    table.cell(0, 1).width = Inches(2.6)
    table.cell(0, 2).width = Inches(2.5)
    for i, t in enumerate(["Role", "Account Email (Password: vitalis2026)", "Affiliation"]):
        c = table.cell(0, i)
        set_cell_background(c, "064E3B")
        r = c.paragraphs[0].add_run(t)
        r.bold = True; r.font.color.rgb = RGBColor(255, 255, 255)

    accounts = [
        ("Reception", "reception@fmc.vitalis.ng", "FMC Abeokuta (Front Desk)"),
        ("Nurse", "nurse@fmc.vitalis.ng", "FMC Abeokuta (Triage Station)"),
        ("Doctor", "doctor@fmc.vitalis.ng", "FMC Abeokuta (Consultation)"),
        ("Lab Scientist", "lab@fmc.vitalis.ng", "FMC Abeokuta (Clinical Lab)"),
        ("Radiologist", "rad@fmc.vitalis.ng", "FMC Abeokuta (Imaging Dept)"),
        ("Doctor (Hospital B)", "doctor@statehospital.vitalis.ng", "State Hospital Sokenu"),
        ("Patient Profile", "olumide@example.com", "Olumide Adeleke (VIT-2026-0001)")
    ]

    for idx, (role, email, affil) in enumerate(accounts, start=1):
        c0 = table.cell(idx, 0); c1 = table.cell(idx, 1); c2 = table.cell(idx, 2)
        bg = "F8FAFC" if idx % 2 == 1 else "FFFFFF"
        set_cell_background(c0, bg); set_cell_background(c1, bg); set_cell_background(c2, bg)
        set_cell_margins(c0, 60, 60, 80, 80); set_cell_margins(c1, 60, 60, 80, 80); set_cell_margins(c2, 60, 60, 80, 80)
        c0.paragraphs[0].add_run(role).bold = True
        c1.paragraphs[0].add_run(email)
        c2.paragraphs[0].add_run(affil)

    # Save Word document
    out_path = r"c:\Users\USER\Desktop\NCS backend\docs\VITALIS_Technical_Architecture_Blueprint.docx"
    doc.save(out_path)
    print(f"Word document saved to {out_path}")

if __name__ == "__main__":
    create_document()
