"""
SatyaScan Synthetic Travel Document Dataset Generator
Builds 9+ deterministic, safe synthetic travel documents and matching selfie samples.
Every document is visibly and metadata-marked: "DEMO / SYNTHETIC — NOT A REAL DOCUMENT".
Generates ground-truth binary masks for tamper evaluation and writes data/metadata.csv.
"""

from typing import Tuple, Dict, Any, List
import os
import csv
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ai.mrz.mrz_parser import MRZParser


class SyntheticDatasetBuilder:
    """
    Deterministic synthetic document and face generator.
    """

    WIDTH = 900
    HEIGHT = 600

    def __init__(self, output_dir: str = "data"):
        self.output_dir = output_dir
        self.genuine_dir = os.path.join(output_dir, "genuine")
        self.tampered_dir = os.path.join(output_dir, "tampered")
        self.selfies_dir = os.path.join(output_dir, "selfies")
        self.masks_dir = os.path.join(output_dir, "masks")
        self.metadata_path = os.path.join(output_dir, "metadata.csv")

        for d in [self.genuine_dir, self.tampered_dir, self.selfies_dir, self.masks_dir]:
            os.makedirs(d, exist_ok=True)

    def _draw_synthetic_face(self, seed: int, with_beard: bool = False, is_female: bool = False) -> np.ndarray:
        """Draws a clean, stylized synthetic face avatar for biometric testing."""
        np.random.seed(seed)
        face = np.ones((220, 180, 3), dtype=np.uint8) * 230  # Soft gray studio background

        skin_color = (165, 195, 230)  # Light warm skin tone BGR
        hair_color = (25, 30, 45)     # Dark brown / black
        eye_color = (35, 45, 60)

        # Draw neck and shoulders
        cv2.rectangle(face, (55, 170), (125, 220), skin_color, -1)
        cv2.ellipse(face, (90, 220), (70, 35), 0, 0, 360, (60, 70, 90), -1)  # Shirt

        # Draw head oval
        cv2.ellipse(face, (90, 110), (55, 70), 0, 0, 360, skin_color, -1)

        # Draw hair
        if is_female:
            cv2.ellipse(face, (90, 80), (62, 50), 0, 180, 360, hair_color, -1)
            cv2.ellipse(face, (40, 130), (15, 45), 0, 0, 360, hair_color, -1)
            cv2.ellipse(face, (140, 130), (15, 45), 0, 0, 360, hair_color, -1)
        else:
            cv2.ellipse(face, (90, 75), (58, 40), 0, 180, 360, hair_color, -1)

        # Draw eyes
        cv2.circle(face, (70, 105), 6, (255, 255, 255), -1)
        cv2.circle(face, (110, 105), 6, (255, 255, 255), -1)
        cv2.circle(face, (70, 105), 3, eye_color, -1)
        cv2.circle(face, (110, 105), 3, eye_color, -1)

        # Eyebrows
        cv2.line(face, (60, 95), (80, 95), hair_color, 2)
        cv2.line(face, (100, 95), (120, 95), hair_color, 2)

        # Nose line
        cv2.line(face, (90, 105), (90, 125), (130, 160, 195), 2)
        cv2.line(face, (85, 125), (95, 125), (130, 160, 195), 2)

        # Mouth
        cv2.ellipse(face, (90, 145), (18, 6), 0, 0, 180, (90, 100, 170), -1)

        # Add beard if requested (for Case 08 appearance change demonstration)
        if with_beard:
            # Jawline and chin beard
            cv2.ellipse(face, (90, 150), (46, 32), 0, 0, 180, hair_color, -1)
            # Mustache
            cv2.ellipse(face, (90, 138), (22, 6), 0, 180, 360, hair_color, -1)
            # Re-carve inner mouth
            cv2.ellipse(face, (90, 145), (12, 3), 0, 0, 180, (90, 100, 170), -1)

        return face

    def create_base_document(
        self,
        doc_num: str,
        surname: str,
        given_names: str,
        dob_yymmdd: str,
        dob_display: str,
        expiry_yymmdd: str,
        expiry_display: str,
        sex: str,
        face_avatar: np.ndarray,
        is_watermarked: bool = True
    ) -> Tuple[np.ndarray, str, str]:
        """Renders an authentic-looking synthetic TD3 passport biodata page."""
        # Base canvas: Security background with soft cream/guilloche tone
        doc = np.ones((self.HEIGHT, self.WIDTH, 3), dtype=np.uint8) * 245
        # Soft patterned guilloche grid
        for y in range(0, self.HEIGHT, 16):
            cv2.line(doc, (0, y), (self.WIDTH, y), (235, 238, 240), 1)
        for x in range(0, self.WIDTH, 16):
            cv2.line(doc, (x, 0), (x, self.HEIGHT), (235, 238, 240), 1)

        # Header band (Dark Navy Blue)
        cv2.rectangle(doc, (0, 0), (self.WIDTH, 75), (55, 30, 20), -1)
        cv2.putText(doc, "REPUBLIC OF INDIA", (300, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        cv2.putText(doc, "PASSPORT / PASSEPORT", (325, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 215, 230), 1)

        # Synthetic Disclaimer Watermark across the document
        if is_watermarked:
            cv2.putText(
                doc, "DEMO / SYNTHETIC — NOT A REAL DOCUMENT", (120, 260),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (210, 210, 220), 2
            )

        # Portrait Photo Window (left)
        px, py, pw, ph = 50, 110, 180, 220
        cv2.rectangle(doc, (px - 2, py - 2), (px + pw + 2, py + ph + 2), (180, 180, 190), 2)
        doc[py:py+ph, px:px+pw] = face_avatar

        # Ghost Image (watermark portrait) on right side
        ghost = cv2.resize(face_avatar, (90, 110))
        gray_ghost = cv2.cvtColor(ghost, cv2.COLOR_BGR2GRAY)
        ghost_color = cv2.cvtColor(gray_ghost, cv2.COLOR_GRAY2BGR)
        gx, gy = 730, 140
        doc[gy:gy+110, gx:gx+90] = cv2.addWeighted(doc[gy:gy+110, gx:gx+90], 0.6, ghost_color, 0.4, 0)

        # Official Emblem placeholder
        cv2.circle(doc, (140, 38), 24, (220, 200, 140), 2)
        cv2.putText(doc, "SSB", (126, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (220, 200, 140), 1)

        # VIZ Text Fields
        fields = [
            ("Type / Type", "P", 280, 115),
            ("Country Code / Code Pays", "IND", 450, 115),
            ("Passport No. / No. Passeport", doc_num, 620, 115),
            ("Surname / Nom", surname, 280, 165),
            ("Given Names / Prenoms", given_names, 280, 215),
            ("Nationality / Nationalite", "INDIAN", 280, 265),
            ("Date of Birth / Date de Naissance", dob_display, 280, 315),
            ("Sex / Sexe", sex, 540, 315),
            ("Place of Birth / Lieu de Naissance", "DELHI", 280, 365),
            ("Date of Issue / Date de Delivrance", "10/05/2018", 280, 415),
            ("Date of Expiry / Date d'Expiration", expiry_display, 540, 415),
        ]

        for label, val, tx, ty in fields:
            cv2.putText(doc, label.upper(), (tx, ty - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (100, 110, 120), 1)
            cv2.putText(doc, val.upper(), (tx, ty + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (15, 20, 30), 2)

        # Build valid ICAO 7-3-1 check digits for MRZ
        # Pad doc num to 9 chars
        padded_doc_num = doc_num.ljust(9, '<')
        c_doc = MRZParser.calculate_check_digit(padded_doc_num)
        c_dob = MRZParser.calculate_check_digit(dob_yymmdd)
        c_exp = MRZParser.calculate_check_digit(expiry_yymmdd)
        c_opt = "<"

        # Composite check digit payload
        comp_payload = f"{padded_doc_num}{c_doc}{dob_yymmdd}{c_dob}{expiry_yymmdd}{c_exp}<<<<<<<<<<<<<<<"
        c_comp = MRZParser.calculate_check_digit(comp_payload)

        # Line 1
        name_mrz = f"{surname}<<{given_names}".replace(" ", "<").upper()
        name_mrz = name_mrz.ljust(39, '<')[:39]
        line1 = f"P<IND{name_mrz}"

        # Line 2
        sex_char = "M" if sex.upper().startswith("M") else "F" if sex.upper().startswith("F") else "<"
        line2 = f"{padded_doc_num}{c_doc}IND{dob_yymmdd}{c_dob}{sex_char}{expiry_yymmdd}{c_exp}<<<<<<<<<<<<<<<{c_comp}"

        # Draw MRZ Bottom Box
        cv2.rectangle(doc, (0, 480), (self.WIDTH, self.HEIGHT), (255, 255, 255), -1)
        cv2.line(doc, (0, 480), (self.WIDTH, 480), (200, 205, 210), 2)

        # Draw OCR-B style MRZ typography
        cv2.putText(doc, line1, (30, 525), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (10, 10, 15), 2)
        cv2.putText(doc, line2, (30, 565), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (10, 10, 15), 2)

        return doc, line1, line2

    def build_all_cases(self) -> List[Dict[str, Any]]:
        """Generates the 9 canonical deterministic SIH demo cases."""
        manifest: List[Dict[str, Any]] = []

        # Faces
        face_arjun = self._draw_synthetic_face(seed=101, with_beard=False)
        face_arjun_bearded = self._draw_synthetic_face(seed=101, with_beard=True)
        face_imposter = self._draw_synthetic_face(seed=999, with_beard=False)
        face_female = self._draw_synthetic_face(seed=202, is_female=True)

        # -------------------------------------------------------------
        # CASE 01: GENUINE SYNTHETIC PASSPORT (Low Risk)
        # -------------------------------------------------------------
        doc1, l1, l2 = self.create_base_document(
            doc_num="Z1234567",
            surname="SHARMA",
            given_names="ARJUN",
            dob_yymmdd="920514",
            dob_display="14/05/1992",
            expiry_yymmdd="280513",
            expiry_display="13/05/2028",
            sex="MALE",
            face_avatar=face_arjun
        )
        c1_path = os.path.join(self.genuine_dir, "case01_genuine_arjun.jpg")
        cv2.imwrite(c1_path, doc1)

        # Selfie for Case 01: Arjun matching clean-shaven
        s1_path = os.path.join(self.selfies_dir, "case01_selfie_arjun.jpg")
        cv2.imwrite(s1_path, face_arjun)

        manifest.append({
            "image_id": "case01_genuine_arjun.jpg",
            "case_id": "CASE-01",
            "document_type": "PASSPORT",
            "category": "GENUINE",
            "expected_risk": "LOW",
            "tamper_type": "NONE",
            "doc_path": c1_path,
            "selfie_path": s1_path,
            "description": "Standard authentic synthetic Indian passport. Valid MRZ, clean forensics, matching face."
        })

        # -------------------------------------------------------------
        # CASE 02: EXPIRED DOCUMENT (Medium/High Risk)
        # -------------------------------------------------------------
        doc2, _, _ = self.create_base_document(
            doc_num="A9876543",
            surname="KUMAR",
            given_names="RAVI",
            dob_yymmdd="850320",
            dob_display="20/03/1985",
            expiry_yymmdd="220319",  # Expired in 2022
            expiry_display="19/03/2022",
            sex="MALE",
            face_avatar=face_arjun
        )
        c2_path = os.path.join(self.tampered_dir, "case02_expired_ravi.jpg")
        cv2.imwrite(c2_path, doc2)
        s2_path = os.path.join(self.selfies_dir, "case02_selfie_ravi.jpg")
        cv2.imwrite(s2_path, face_arjun)

        manifest.append({
            "image_id": "case02_expired_ravi.jpg",
            "case_id": "CASE-02",
            "document_type": "PASSPORT",
            "category": "EXPIRED",
            "expected_risk": "HIGH",
            "tamper_type": "DOCUMENT_EXPIRED",
            "doc_path": c2_path,
            "selfie_path": s2_path,
            "description": "Passport expired in 2022. Expiry validation rule triggers high operational flag."
        })

        # -------------------------------------------------------------
        # CASE 03: DOB MODIFIED (VIZ vs MRZ Mismatch)
        # -------------------------------------------------------------
        # Create genuine doc with DOB 1990 in MRZ, but alter visual DOB to 2002
        doc3, _, _ = self.create_base_document(
            doc_num="Z5544332",
            surname="VERMA",
            given_names="DEEPAK",
            dob_yymmdd="900115",  # MRZ says 15 Jan 1990
            dob_display="15/01/1990",
            expiry_yymmdd="290114",
            expiry_display="14/01/2029",
            sex="MALE",
            face_avatar=face_arjun
        )
        # Tamper: Cover visual DOB with edited text "15/01/2002"
        mask3 = np.zeros((self.HEIGHT, self.WIDTH), dtype=np.uint8)
        # Cover VIZ DOB area (x: 275-450, y: 310-335)
        cv2.rectangle(doc3, (275, 318), (440, 342), (245, 245, 245), -1)
        cv2.rectangle(mask3, (275, 318), (440, 342), 255, -1)
        cv2.putText(doc3, "15/01/2002", (280, 336), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (10, 10, 10), 2)

        c3_path = os.path.join(self.tampered_dir, "case03_tampered_dob.jpg")
        cv2.imwrite(c3_path, doc3)
        m3_path = os.path.join(self.masks_dir, "case03_tampered_dob_mask.png")
        cv2.imwrite(m3_path, mask3)

        manifest.append({
            "image_id": "case03_tampered_dob.jpg",
            "case_id": "CASE-03",
            "document_type": "PASSPORT",
            "category": "TAMPERED",
            "expected_risk": "HIGH",
            "tamper_type": "DOB_MODIFIED",
            "doc_path": c3_path,
            "mask_path": m3_path,
            "selfie_path": s1_path,
            "description": "Visual Date of Birth altered to 2002 while MRZ states 1990. Triggers VIZ/MRZ mismatch."
        })

        # -------------------------------------------------------------
        # CASE 04: PHOTO REPLACED (Spliced portrait + Face mismatch)
        # -------------------------------------------------------------
        doc4, _, _ = self.create_base_document(
            doc_num="Z7788990",
            surname="PATEL",
            given_names="MANISH",
            dob_yymmdd="940822",
            dob_display="22/08/1994",
            expiry_yymmdd="300821",
            expiry_display="21/08/2030",
            sex="MALE",
            face_avatar=face_arjun
        )
        # Tamper: Paste different female face avatar over portrait window
        mask4 = np.zeros((self.HEIGHT, self.WIDTH), dtype=np.uint8)
        px, py, pw, ph = 50, 110, 180, 220
        doc4[py:py+ph, px:px+pw] = face_female
        cv2.rectangle(mask4, (px, py), (px + pw, py + ph), 255, -1)

        c4_path = os.path.join(self.tampered_dir, "case04_photo_replaced.jpg")
        cv2.imwrite(c4_path, doc4)
        m4_path = os.path.join(self.masks_dir, "case04_photo_replaced_mask.png")
        cv2.imwrite(m4_path, mask4)
        # Selfie is male Arjun -> Mismatch with replaced female portrait photo!
        manifest.append({
            "image_id": "case04_photo_replaced.jpg",
            "case_id": "CASE-04",
            "document_type": "PASSPORT",
            "category": "TAMPERED",
            "expected_risk": "CRITICAL",
            "tamper_type": "PHOTO_REPLACEMENT",
            "doc_path": c4_path,
            "mask_path": m4_path,
            "selfie_path": s1_path,
            "description": "Photo window replaced with spliced foreign avatar. Triggers ELA anomaly + Biometric mismatch."
        })

        # -------------------------------------------------------------
        # CASE 05: STAMP / COPY-MOVE TAMPER
        # -------------------------------------------------------------
        doc5, _, _ = self.create_base_document(
            doc_num="Z3322110",
            surname="SINGH",
            given_names="KABIR",
            dob_yymmdd="881110",
            dob_display="10/11/1988",
            expiry_yymmdd="281109",
            expiry_display="09/11/2028",
            sex="MALE",
            face_avatar=face_arjun
        )
        # Create a stamped circular visa emblem at (650, 260)
        cv2.circle(doc5, (650, 260), 38, (40, 40, 180), 2)
        cv2.putText(doc5, "ENTRY VISA", (620, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (40, 40, 180), 1)
        cv2.putText(doc5, "SSB CHECK", (622, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (40, 40, 180), 1)

        # Clone it to (480, 260) — Copy-Move forgery!
        stamp_crop = doc5[220:300, 610:690].copy()
        doc5[220:300, 450:530] = stamp_crop

        mask5 = np.zeros((self.HEIGHT, self.WIDTH), dtype=np.uint8)
        cv2.circle(mask5, (490, 260), 40, 255, -1)

        c5_path = os.path.join(self.tampered_dir, "case05_copymove_stamp.jpg")
        cv2.imwrite(c5_path, doc5)
        m5_path = os.path.join(self.masks_dir, "case05_copymove_stamp_mask.png")
        cv2.imwrite(m5_path, mask5)

        manifest.append({
            "image_id": "case05_copymove_stamp.jpg",
            "case_id": "CASE-05",
            "document_type": "PASSPORT",
            "category": "TAMPERED",
            "expected_risk": "HIGH",
            "tamper_type": "COPY_MOVE_STAMP",
            "doc_path": c5_path,
            "mask_path": m5_path,
            "selfie_path": s1_path,
            "description": "Cloned visa inspection stamp duplicated into another zone. Triggers CMFD keypoint alert."
        })

        # -------------------------------------------------------------
        # CASE 06: MULTIPLE IDENTITY REUSE
        # -------------------------------------------------------------
        # Same face avatar (seed 101) but document says name is "RAHUL VERMA" (matches seeded FAISS gallery!)
        doc6, _, _ = self.create_base_document(
            doc_num="Z6677889",
            surname="VERMA",
            given_names="RAHUL",
            dob_yymmdd="920514",
            dob_display="14/05/1992",
            expiry_yymmdd="280513",
            expiry_display="13/05/2028",
            sex="MALE",
            face_avatar=face_arjun
        )
        c6_path = os.path.join(self.genuine_dir, "case06_multi_identity.jpg")
        cv2.imwrite(c6_path, doc6)

        manifest.append({
            "image_id": "case06_multi_identity.jpg",
            "case_id": "CASE-06",
            "document_type": "PASSPORT",
            "category": "MULTI_IDENTITY",
            "expected_risk": "CRITICAL",
            "tamper_type": "IDENTITY_REUSE",
            "doc_path": c6_path,
            "selfie_path": s1_path,
            "description": "Same physical face presented under disparate synthetic identity. Triggers FAISS vector match."
        })

        # -------------------------------------------------------------
        # CASE 07: POOR IMAGE QUALITY (Fails Quality Gate)
        # -------------------------------------------------------------
        # Severely blur doc1 using Gaussian Blur (kernel 45x45)
        blurred_doc = cv2.GaussianBlur(doc1, (45, 45), 0)
        c7_path = os.path.join(self.tampered_dir, "case07_blurry_fail.jpg")
        cv2.imwrite(c7_path, blurred_doc)

        manifest.append({
            "image_id": "case07_blurry_fail.jpg",
            "case_id": "CASE-07",
            "document_type": "PASSPORT",
            "category": "DEGRADED",
            "expected_risk": "MEDIUM",
            "tamper_type": "BLUR_DEGRADATION",
            "doc_path": c7_path,
            "selfie_path": s1_path,
            "description": "Heavy optical blur. Quality gate detects insufficient Laplacian sharpness and requests re-scan."
        })

        # -------------------------------------------------------------
        # CASE 08: LEGITIMATE APPEARANCE CHANGE (Clean Doc vs Bearded Selfie)
        # -------------------------------------------------------------
        # Document is clean-shaven Arjun (doc1), but live selfie has beard!
        s8_path = os.path.join(self.selfies_dir, "case08_selfie_bearded_arjun.jpg")
        cv2.imwrite(s8_path, face_arjun_bearded)

        manifest.append({
            "image_id": "case01_genuine_arjun.jpg",  # Uses genuine doc1
            "case_id": "CASE-08",
            "document_type": "PASSPORT",
            "category": "APPEARANCE_CHANGE",
            "expected_risk": "LOW",
            "tamper_type": "NONE",
            "doc_path": c1_path,
            "selfie_path": s8_path,
            "description": "Same person with full beard in live capture. Biometrics pass, appearance difference noted as MODERATE."
        })

        # -------------------------------------------------------------
        # CASE 09: DIFFERENT PERSON / IMPERSONATOR (Low Face Similarity)
        # -------------------------------------------------------------
        # Document is Arjun (doc1), but live selfie is imposter!
        s9_path = os.path.join(self.selfies_dir, "case09_selfie_imposter.jpg")
        cv2.imwrite(s9_path, face_imposter)

        manifest.append({
            "image_id": "case01_genuine_arjun.jpg",
            "case_id": "CASE-09",
            "document_type": "PASSPORT",
            "category": "IMPERSONATION",
            "expected_risk": "HIGH",
            "tamper_type": "NONE",
            "doc_path": c1_path,
            "selfie_path": s9_path,
            "description": "Completely different individual attempting transit on Arjun's passport. Face similarity < 0.50."
        })

        # Write metadata.csv
        with open(self.metadata_path, mode="w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "case_id", "image_id", "document_type", "category",
                "expected_risk", "tamper_type", "doc_path", "selfie_path", "description"
            ], extrasaction="ignore")
            writer.writeheader()
            for m in manifest:
                writer.writerow(m)

        print(f"[SatyaScan Dataset] Generated {len(manifest)} synthetic cases and metadata.csv successfully.")
        return manifest


if __name__ == "__main__":
    builder = SyntheticDatasetBuilder()
    builder.build_all_cases()
