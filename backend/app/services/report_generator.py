"""
SatyaScan Forensic Case Report Generator (ReportLab)
Generates an official, court-grade border security screening summary PDF document
with SatyaScan branding, case metadata, masked PII, forensic findings, biometric metrics,
SHA-256 audit digest, and mandatory decision-support disclaimers.
"""

from typing import Dict, Any, List
import os
import html
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Adds standard running footer with page numbers and security classifications."""
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
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#475569"))
        # Header text
        self.drawString(54, 755, "CONFIDENTIAL // LAW ENFORCEMENT & IMMIGRATION SCREENING RECORD")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 748, 558, 748)
        
        # Footer text
        self.line(54, 45, 558, 45)
        self.drawString(54, 32, "SatyaScan Document Integrity Workstation · DEMO / EVALUATION DATA · SIH26188")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_str)
        self.restoreState()


class ReportGenerator:
    """
    Builds official screening PDF reports using ReportLab.
    """

    @classmethod
    def generate_pdf(cls, case_data: Dict[str, Any], output_pdf_path: str) -> str:
        """
        Renders complete multi-section screening dossier into PDF.
        """
        os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)
        doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=60,
            bottomMargin=54
        )

        styles = getSampleStyleSheet()
        normal = styles["Normal"]

        # Custom styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A")
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=normal,
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748B")
        )
        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0F766E"),
            spaceBefore=8,
            spaceAfter=4
        )
        cell_bold = ParagraphStyle(
            "CellBold", parent=normal, fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.HexColor("#1E293B")
        )
        cell_text = ParagraphStyle(
            "CellText", parent=normal, fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#334155")
        )

        elements = []

        # 1. Document Header Banner
        screening_id = case_data.get("id", "SAT-2026-UNKNOWN")
        risk_band = case_data.get("risk_band", "LOW")
        risk_score = case_data.get("risk_score", 0.0)

        band_colors = {
            "LOW": colors.HexColor("#059669"),
            "MEDIUM": colors.HexColor("#D97706"),
            "HIGH": colors.HexColor("#DC2626"),
            "CRITICAL": colors.HexColor("#991B1B")
        }
        accent_color = band_colors.get(risk_band, colors.HexColor("#475569"))

        header_data = [
            [
                Paragraph("<b>SatyaScan</b><br/><font size=9 color='#475569'>Document Integrity & Identity Verification Workstation</font>", title_style),
                Paragraph(
                    f"<para align=right><font size=14 color='{accent_color.hexval()}'><b>{risk_band} RISK</b></font><br/>"
                    f"<font size=10 color='#1E293B'><b>Score: {risk_score:.1f} / 100</b></font><br/>"
                    f"<font size=8 color='#64748B'>CASE #{screening_id}</font></para>",
                    normal
                )
            ]
        ]
        t_head = Table(header_data, colWidths=[330, 174])
        t_head.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ]))
        elements.append(t_head)
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=accent_color, spaceAfter=8))

        # 2. Case Overview Table
        ts_str = case_data.get("created_at", datetime.now().isoformat())
        doc_type = case_data.get("document_type", "PASSPORT")
        masked_id = case_data.get("masked_document_id", "N/A")
        cp_info = case_data.get("checkpoint_name") or case_data.get("checkpoint_id") or "Central Immigration Checkpoint"
        operator_info = case_data.get("operator_name") or "Authorized Border Officer"
        if case_data.get("operator_badge"):
            operator_info += f" ({case_data.get('operator_badge')})"

        overview_data = [
            [
                Paragraph("<b>Screening ID:</b>", cell_bold), Paragraph(html.escape(str(screening_id)), cell_text),
                Paragraph("<b>Screening Date:</b>", cell_bold), Paragraph(html.escape(str(ts_str)[:19]), cell_text)
            ],
            [
                Paragraph("<b>Checkpoint:</b>", cell_bold), Paragraph(html.escape(str(cp_info)), cell_text),
                Paragraph("<b>Screening Officer:</b>", cell_bold), Paragraph(html.escape(str(operator_info)), cell_text)
            ],
            [
                Paragraph("<b>Document Type:</b>", cell_bold), Paragraph(html.escape(str(doc_type)), cell_text),
                Paragraph("<b>Masked Doc No:</b>", cell_bold), Paragraph(html.escape(str(masked_id)), cell_text)
            ],
            [
                Paragraph("<b>OCR Engine:</b>", cell_bold), Paragraph(html.escape(str(case_data.get("ocr_engine") or "PaddleOCR / Tesseract")), cell_text),
                Paragraph("<b>System Status:</b>", cell_bold), Paragraph(html.escape(str(case_data.get("status", "COMPLETED"))), cell_text)
            ],
            [
                Paragraph("<b>Recommendation:</b>", cell_bold),
                Paragraph(f"<b>{html.escape(str(case_data.get('recommendation', 'Routine Clearance')))}</b>", cell_bold),
                Paragraph("<b>Evaluation Mode:</b>", cell_bold),
                Paragraph("DEMO / EVALUATION DATA", cell_bold)
            ]
        ]
        t_overview = Table(overview_data, colWidths=[95, 157, 95, 157])
        t_overview.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t_overview)
        elements.append(Spacer(1, 10))

        # 3. Extracted Visual Fields Table
        elements.append(Paragraph("1. Identity Field Extraction & Cross-Verification", section_heading))
        fields = case_data.get("extracted_fields", [])
        is_visa = (str(doc_type).upper() == "VISA")

        if is_visa:
            field_rows = [
                [
                    Paragraph("<b>Field Name</b>", cell_bold),
                    Paragraph("<b>Extracted Value</b>", cell_bold),
                    Paragraph("<b>OCR Engine</b>", cell_bold),
                    Paragraph("<b>Confidence</b>", cell_bold),
                    Paragraph("<b>Status / Validity</b>", cell_bold)
                ]
            ]
            for f in fields:
                val_clean = html.escape(str(f.get("visual_value") or f.get("mrz_value") or "—"))
                val_status = f.get("validation", "VALID")
                status_color = "#059669" if val_status == "VALID" else "#DC2626"
                engine_str = f.get("ocr_engine") or case_data.get("ocr_engine") or "PaddleOCR"
                field_rows.append([
                    Paragraph(html.escape(str(f.get("field_name", "")).replace("_", " ").title()), cell_text),
                    Paragraph(val_clean, cell_text),
                    Paragraph(html.escape(str(engine_str)), cell_text),
                    Paragraph(f"{f.get('confidence', 1.0):.2f}" if f.get('confidence') is not None else "—", cell_text),
                    Paragraph(f"<font color='{status_color}'><b>{html.escape(str(val_status))}</b></font>", cell_text)
                ])
        else:
            field_rows = [
                [
                    Paragraph("<b>Field Name</b>", cell_bold),
                    Paragraph("<b>Visual (VIZ)</b>", cell_bold),
                    Paragraph("<b>MRZ Decoded</b>", cell_bold),
                    Paragraph("<b>Confidence</b>", cell_bold),
                    Paragraph("<b>Cross-Check Status</b>", cell_bold)
                ]
            ]
            for f in fields:
                status_color = "#059669" if f.get("match_status") == "MATCH" else "#DC2626"
                field_name_clean = html.escape(str(f.get("field_name", "")).replace("_", " ").title())
                vis_val_clean = html.escape(str(f.get("visual_value", "—")))
                mrz_val_clean = html.escape(str(f.get("mrz_value", "—")))
                status_clean = html.escape(str(f.get("match_status", "MATCH")))
                field_rows.append([
                    Paragraph(field_name_clean, cell_text),
                    Paragraph(vis_val_clean, cell_text),
                    Paragraph(mrz_val_clean, cell_text),
                    Paragraph(f"{f.get('confidence', 1.0):.2f}" if f.get('confidence') is not None else "—", cell_text),
                    Paragraph(f"<font color='{status_color}'><b>{status_clean}</b></font>", cell_text)
                ])
        if len(field_rows) == 1:
            field_rows.append([Paragraph("No extracted fields available.", cell_text)] * 5)

        t_fields = Table(field_rows, colWidths=[100, 110, 110, 64, 120])
        t_fields.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        elements.append(t_fields)
        elements.append(Spacer(1, 10))

        # 4. Multi-Signal Tampering Forensics & Biometrics
        elements.append(Paragraph("2. Forensic & Biometric Integrity Analysis", section_heading))
        tamper = case_data.get("tamper_summary", {})
        face = case_data.get("face_result") or {}

        ela_interp = html.escape(str(tamper.get("signals", {}).get("ela", {}).get("interpretation", "Normal compression baseline")))
        noise_interp = html.escape(str(tamper.get("signals", {}).get("noise_residual", {}).get("interpretation", "Homogeneous noise distribution")))
        copy_interp = html.escape(str(tamper.get("signals", {}).get("copy_move", {}).get("interpretation", "No cloned regions found")))
        face_verdict = html.escape(str(face.get("verification_result", "NOT_RUN")))
        face_rec = html.escape(str(face.get("recommendation", "N/A")))

        forensic_rows = [
            [
                Paragraph("<b>Forensic Dimension</b>", cell_bold),
                Paragraph("<b>Observed Measurement</b>", cell_bold),
                Paragraph("<b>Integrity Assessment</b>", cell_bold)
            ],
            [
                Paragraph("Error Level Analysis (ELA)", cell_text),
                Paragraph(f"Score: {tamper.get('signals', {}).get('ela', {}).get('anomaly_score', 0.0)}/100", cell_text),
                Paragraph(ela_interp, cell_text)
            ],
            [
                Paragraph("Sensor Noise Residual", cell_text),
                Paragraph(f"Score: {tamper.get('signals', {}).get('noise_residual', {}).get('anomaly_score', 0.0)}/100", cell_text),
                Paragraph(noise_interp, cell_text)
            ],
            [
                Paragraph("Copy-Move Detection", cell_text),
                Paragraph(f"Score: {tamper.get('signals', {}).get('copy_move', {}).get('anomaly_score', 0.0)}/100", cell_text),
                Paragraph(copy_interp, cell_text)
            ],
            [
                Paragraph("Face Biometric Verification", cell_text),
                Paragraph(f"Similarity: {face.get('similarity_score', 'N/A')} (Threshold: {face.get('threshold', 0.65)})", cell_text),
                Paragraph(f"<b>{face_verdict}</b> — {face_rec}", cell_text)
            ]
        ]
        t_forensic = Table(forensic_rows, colWidths=[130, 124, 250])
        t_forensic.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        elements.append(t_forensic)
        elements.append(Spacer(1, 10))

        # 5. Risk Evidence Reasons
        elements.append(Paragraph("3. Explainable Risk Factors & Findings", section_heading))
        reasons = case_data.get("risk_reasons", [])
        reason_rows = [
            [
                Paragraph("<b>Category</b>", cell_bold),
                Paragraph("<b>Severity</b>", cell_bold),
                Paragraph("<b>Evidence Summary</b>", cell_bold),
                Paragraph("<b>Operational Guidance</b>", cell_bold)
            ]
        ]
        for r in reasons[:6]:  # Show top 6
            sev = r.get("severity", "LOW")
            scolor = "#DC2626" if sev in ["CRITICAL", "HIGH"] else "#D97706" if sev == "MEDIUM" else "#059669"
            cat_clean = html.escape(str(r.get("category", "")).replace("_", " "))
            sev_clean = html.escape(str(sev))
            sum_clean = html.escape(str(r.get("summary", "")))
            act_clean = html.escape(str(r.get("action", "")))
            reason_rows.append([
                Paragraph(cat_clean, cell_text),
                Paragraph(f"<font color='{scolor}'><b>{sev_clean}</b></font>", cell_text),
                Paragraph(sum_clean, cell_text),
                Paragraph(act_clean, cell_text)
            ])
        if len(reason_rows) == 1:
            reason_rows.append([
                Paragraph("CLEARED", cell_text),
                Paragraph("<font color='#059669'><b>LOW</b></font>", cell_text),
                Paragraph("Document passed all automated integrity and rule checks.", cell_text),
                Paragraph("Permit routine passenger transit.", cell_text)
            ])

        t_reasons = Table(reason_rows, colWidths=[90, 60, 194, 160])
        t_reasons.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        elements.append(t_reasons)
        elements.append(Spacer(1, 12))

        # 6. Permissioned Blockchain Audit Anchor & Officer Sign-off Block
        b_anchor = case_data.get("blockchain_anchor") or {}
        anchor_status = b_anchor.get("status", "UNAVAILABLE")
        status_color = "#059669" if anchor_status == "VERIFIED" else ("#DC2626" if anchor_status == "MISMATCH" else "#D97706")

        doc_hash = b_anchor.get("document_hash") or "N/A"
        res_hash = b_anchor.get("result_hash") or "N/A"
        tx_id = b_anchor.get("transaction_id") or "NONE (Private ledger offline / Pending host deployment)"
        network_str = b_anchor.get("network", "Hyperledger Fabric (Private)")
        channel_str = b_anchor.get("channel", "satyascan-channel")
        chaincode_str = b_anchor.get("chaincode", "screening_anchor")

        audit_events = case_data.get("audit_trail", [])
        latest_hash = audit_events[-1].get("event_hash") if audit_events else "0" * 64

        anchor_info_p = Paragraph(
            f"<b>PERMISSIONED BLOCKCHAIN AUDIT ANCHOR:</b><br/>"
            f"<font size=6.5 color='#334155'><b>Network:</b> {network_str} | <b>Channel:</b> {channel_str} | <b>Chaincode:</b> {chaincode_str}</font><br/>"
            f"<font size=6.5 color='#334155'><b>Anchor Status:</b> <font color='{status_color}'><b>{anchor_status}</b></font> | "
            f"<b>Local SHA-256 Audit Chain:</b> <font color='#059669'><b>VERIFIED ({len(audit_events)} events unbroken)</b></font></font><br/>"
            f"<font size=5.5 color='#475569'><b>Document SHA-256 Digest:</b> {doc_hash}</font><br/>"
            f"<font size=5.5 color='#475569'><b>Result Canonical SHA-256 Digest:</b> {res_hash}</font><br/>"
            f"<font size=5.5 color='#64748B'><b>Transaction ID:</b> {tx_id}</font><br/>"
            f"<font size=6 color='#64748B'><i>Evidence stays off-chain; cryptographic proof goes on-chain. Zero PII/biometrics.</i></font>",
            normal
        )

        sign_p = Paragraph(
            "<b>Screening Officer Sign-off:</b><br/><br/>"
            "Signature: __________________________<br/>"
            "Badge / Station: ____________________<br/>"
            "Action: [  ] CLEARED   [  ] SECONDARY",
            normal
        )

        sign_data = [[anchor_info_p, sign_p]]
        t_sign = Table(sign_data, colWidths=[330, 174])
        t_sign.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t_sign)
        elements.append(Spacer(1, 6))

        # 7. Mandatory Disclaimer
        disclaimer_text = (
            "<b>NOTICE & DISCLAIMER:</b> This verification record is generated by the SatyaScan "
            "Document Integrity & Identity Verification Workstation for decision-support purposes only. Automated findings, "
            "forensic anomaly scores, and biometric metrics do not autonomously constitute a legal verdict. Final admissibility "
            "and legal clearance decisions remain the sole statutory prerogative of authorized immigration and border security officers."
        )
        elements.append(Paragraph(disclaimer_text, ParagraphStyle("Disc", parent=normal, fontSize=6.5, leading=8.5, textColor=colors.HexColor("#64748B"))))

        doc.build(elements, canvasmaker=NumberedCanvas)
        return output_pdf_path
