import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "VITALIS — Technical Architecture Blueprint (ITDC 2026)")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 744, 558, 744)

        # Footer
        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, footer_text)
        self.drawString(54, 36, "CONFIDENTIAL & PROPRIETARY — VITALIS HEALTHCARE COORDINATION NETWORK")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)

        self.restoreState()

def create_pdf():
    out_pdf = r"c:\Users\USER\Desktop\NCS backend\docs\VITALIS_Technical_Architecture_Blueprint.pdf"
    doc = SimpleDocTemplate(
        out_pdf,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    PRIMARY = colors.HexColor("#064E3B")    # Deep Emerald
    SECONDARY = colors.HexColor("#10B981")  # Mint Accent
    DARK = colors.HexColor("#1E293B")       # Slate 800
    MUTED = colors.HexColor("#64748B")      # Slate 500
    BG_LIGHT = colors.HexColor("#F8FAFC")   # Slate 50

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=PRIMARY
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=SECONDARY
    )
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=PRIMARY,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=DARK,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=DARK,
        spaceAfter=6
    )
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=DARK,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3
    )
    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=11,
        textColor=DARK
    )

    story = []

    # Title Block
    story.append(Paragraph("THE INTELLIGENT HEALTHCARE COORDINATION NETWORK", subtitle_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("VITALIS", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Complete Technical Architecture & System Blueprint</b><br/><i>Backend & Frontend Architecture • Algorithms • ML Model Integration • ITDC 2026</i>", body_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceBefore=4, spaceAfter=12))

    # Section 1: Executive Overview
    story.append(Paragraph("1. Executive Overview & Core Philosophy", h1_style))
    story.append(Paragraph(
        "<b>VITALIS</b> addresses fragmentation across two dimensions of healthcare delivery: "
        "<b>External patient navigation</b> (matching patient needs to verified facility capabilities) and "
        "<b>Internal hospital coordination</b> (unifying Reception, Nursing, Doctor consultation, and Diagnostics).",
        body_style
    ))
    story.append(Paragraph(
        "<b>Safety Invariant:</b> Patient Safety Before Automation. Emergency rules are deterministic. "
        "The AI/ML decision support layer provides non-diagnostic documentation and structured draft suggestions; "
        "it never autonomously diagnoses, prescribes, or overrules human clinical judgment.",
        bullet_style
    ))
    story.append(Spacer(1, 6))

    # Section 2: Architecture Tiers Table
    story.append(Paragraph("2. Tiered System Architecture", h1_style))
    story.append(Paragraph("The system is designed as a high-performance Modular Monolith:", body_style))

    tiers_data = [
        [Paragraph("<b>Tier</b>", body_style), Paragraph("<b>Components & Tech Stack</b>", body_style), Paragraph("<b>Key Responsibilities</b>", body_style)],
        [
            Paragraph("<b>Presentation Tier</b>", body_style),
            Paragraph("Next.js 14+ App Router, TypeScript, Tailwind CSS, shadcn/ui", body_style),
            Paragraph("Patient PWA (triage, matching, QR consent, records); Hospital Portal (Reception, Nursing, Doctor, Diagnostics); Admin Console.", body_style)
        ],
        [
            Paragraph("<b>API & Security Tier</b>", body_style),
            Paragraph("FastAPI, JWT Bearer Tokens, Argon2id, RBAC Dependencies", body_style),
            Paragraph("Role-scoped access control across 8 roles, request validation, rate limiting, and immutable audit event logging.", body_style)
        ],
        [
            Paragraph("<b>Domain Services</b>", body_style),
            Paragraph("Encounter State Machine, ROUTE Matcher, CONNECT QR, TRANSFER Engine", body_style),
            Paragraph("Single persistent patient encounter; multi-criteria facility suitability; single-use tokenized QR grants; inter-hospital package exchange.", body_style)
        ],
        [
            Paragraph("<b>Persistence Tier</b>", body_style),
            Paragraph("PostgreSQL / SQLite, SQLAlchemy ORM, Private Object Storage", body_style),
            Paragraph("Relational schema, versioned clinical notes, append-only audit trail, secure object storage for imaging & reports.", body_style)
        ]
    ]

    t_tiers = Table(tiers_data, colWidths=[90, 180, 234])
    t_tiers.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [BG_LIGHT, colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_tiers)
    story.append(Spacer(1, 10))

    # Section 3: Centralized Hospital Workflow
    story.append(Paragraph("3. Centralized Hospital Workflow: The Four Departments", h1_style))
    story.append(Paragraph(
        "A patient is registered once at Reception. Departmental staff contribute structured notes to the same encounter ID:",
        body_style
    ))
    story.append(Paragraph("• <b>Reception (Intake):</b> Searches or registers patient; records complaint, arrival mode, and referral source; issues unique encounter number; routes to Nursing.", bullet_style))
    story.append(Paragraph("• <b>Nursing (Observations):</b> Records vital signs (BP, Pulse, Temp, SpO2, Resp Rate, Pain Score); automatic threshold alarms flag abnormal readings for urgent review.", bullet_style))
    story.append(Paragraph("• <b>Doctor (Consultation):</b> Consolidated view of intake and vitals; AI-assisted differential diagnosis drawer; orders diagnostic tests; signs consultation note.", bullet_style))
    story.append(Paragraph("• <b>Diagnostics (Lab & Radiology):</b> Receives orders in work queues; steps order through collection and result entry; authorized verification pushes results directly to doctor.", bullet_style))
    story.append(Spacer(1, 10))

    # Section 4: Mathematical Algorithms
    story.append(Paragraph("4. Mathematical Formulas & Algorithmic Engines", h1_style))
    story.append(Paragraph("<b>4.1 VITALIS ROUTE — Facility Matching Formula</b>", h2_style))
    story.append(Paragraph("The platform computes a transparent suitability score (0–100):<br/><b>S = 0.40·C + 0.25·A + 0.20·D + 0.15·V</b>", body_style))
    story.append(Paragraph("• <b>C (Service Compatibility - 40%):</b> Hard filter. Excludes any facility that cannot provide the essential service.", bullet_style))
    story.append(Paragraph("• <b>A (Reported Availability - 25%):</b> Available=100%, Limited=60%, Unknown=30%, Unavailable=0%. Unknown availability is penalized.", bullet_style))
    story.append(Paragraph("• <b>D (Distance Suitability - 20%):</b> Haversine great-circle decay (<=2km: 100%, 10km: 62%, 30km: 22%).", bullet_style))
    story.append(Paragraph("• <b>V (Verification & Freshness - 15%):</b> Verified=100%, Pending=60%. Decays if confirmed >24h (-15%) or >48h (-30%).", bullet_style))

    story.append(Paragraph("<b>4.2 VITALIS CONNECT — Cryptographic QR Identity</b>", h2_style))
    story.append(Paragraph(
        "The QR code encodes a high-entropy random single-use token URL. The server stores only the <b>SHA-256 hash</b> of the token. "
        "<b>Zero medical data or patient PII is stored inside the QR code.</b> Grants expire within 5–10 minutes and support instant revocation.",
        body_style
    ))
    story.append(Spacer(1, 10))

    # Section 5: Frontend Architecture
    story.append(Paragraph("5. Frontend Architecture (Next.js 14+ PWA)", h1_style))
    story.append(Paragraph(
        "Built as a mobile-first Progressive Web App (PWA) using Next.js 14 App Router, Tailwind CSS, and shadcn/ui. "
        "It supports offline static caching and optimistic client-side drafts for low-connectivity environments.",
        body_style
    ))

    fe_data = [
        [Paragraph("<b>Route Group</b>", body_style), Paragraph("<b>User Target</b>", body_style), Paragraph("<b>Key Capabilities</b>", body_style)],
        [
            Paragraph("<b>/patient/*</b>", body_style),
            Paragraph("Patient PWA", body_style),
            Paragraph("Symptom intake wizard, nearby facility search, consent and QR sharing, longitudinal records, referral tracker.", body_style)
        ],
        [
            Paragraph("<b>/hospital/*</b>", body_style),
            Paragraph("Clinical Staff", body_style),
            Paragraph("Reception intake desk (/reception), Nursing vital triage (/nursing), Doctor consultation console (/doctor), Diagnostics queue (/diagnostics).", body_style)
        ],
        [
            Paragraph("<b>/admin/*</b>", body_style),
            Paragraph("Hospital Admin", body_style),
            Paragraph("Facility service availability management, staff role permissions, immutable audit log inspection.", body_style)
        ]
    ]

    t_fe = Table(fe_data, colWidths=[100, 110, 294])
    t_fe.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [BG_LIGHT, colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_fe)
    story.append(Spacer(1, 10))

    # Section 6: Machine Learning Integration
    story.append(Paragraph("6. Machine Learning Model Integration Guide", h1_style))
    story.append(Paragraph(
        "The backend provides a standardized <code>VitalisMLModelAdapter</code> slot in <code>app/services/intelligence.py</code>. "
        "When your ML model is ready, simply hook its predictions into this adapter. "
        "Deterministic safety red flags run first; then the model generates differential candidates, requiring mandatory physician review.",
        body_style
    ))
    story.append(Spacer(1, 8))

    # Section 7: Demo Accounts & Verification
    story.append(Paragraph("7. Verified Demo Accounts (Password: vitalis2026)", h1_style))
    story.append(Paragraph("All 7 automated test suites are passing. The demo database is seeded with realistic Abeokuta healthcare data:", body_style))

    acc_data = [
        [Paragraph("<b>Department / Role</b>", body_style), Paragraph("<b>Login Email</b>", body_style), Paragraph("<b>Affiliation / Context</b>", body_style)],
        [Paragraph("Reception", body_style), Paragraph("reception@fmc.vitalis.ng", body_style), Paragraph("FMC Abeokuta (Front Desk)", body_style)],
        [Paragraph("Nursing", body_style), Paragraph("nurse@fmc.vitalis.ng", body_style), Paragraph("FMC Abeokuta (Triage Station)", body_style)],
        [Paragraph("Doctor", body_style), Paragraph("doctor@fmc.vitalis.ng", body_style), Paragraph("FMC Abeokuta (Clinics)", body_style)],
        [Paragraph("Lab Tech", body_style), Paragraph("lab@fmc.vitalis.ng", body_style), Paragraph("FMC Abeokuta (Clinical Pathology)", body_style)],
        [Paragraph("Radiologist", body_style), Paragraph("rad@fmc.vitalis.ng", body_style), Paragraph("FMC Abeokuta (Imaging Dept)", body_style)],
        [Paragraph("Hospital B Doctor", body_style), Paragraph("doctor@statehospital.vitalis.ng", body_style), Paragraph("State Hospital Sokenu (Referral recipient)", body_style)],
        [Paragraph("Patient", body_style), Paragraph("olumide@example.com", body_style), Paragraph("Olumide Adeleke (VIT-2026-0001)", body_style)]
    ]

    t_acc = Table(acc_data, colWidths=[120, 180, 204])
    t_acc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [BG_LIGHT, colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_acc)

    # Build PDF with NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF document saved to {out_pdf}")

if __name__ == "__main__":
    create_pdf()
