"""
SatyaScan Document Collage Decomposition & Provenance Lineage Engine
Detects multi-panel document spreads and stacked cards in evaluation fixtures.
Extracts individual document regions, computes cryptographic digests,
and maintains immutable parent-to-crop lineage:
    PARENT_IMAGE_SHA256 -> DOCUMENT_CROP_SHA256 -> REFERENCE_ID
"""

from typing import Dict, Any, List, Optional, Tuple
import os
import hashlib
import cv2
import numpy as np


class CollageExtractor:
    """
    Decomposes multi-card/multi-page collage images into discrete document cards
    and establishes parent-child provenance records.
    """

    @staticmethod
    def sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def sha256_file(cls, filepath: str) -> str:
        with open(filepath, "rb") as f:
            return cls.sha256_bytes(f.read())

    @classmethod
    def detect_layout_type(cls, img: np.ndarray, filename: str) -> str:
        """
        Determines the structural layout of the uploaded image:
        - PASSPORT_BOOKLET_COLLAGE: Wide booklet spread containing identity page, cover, and observation page.
        - STACKED_VISA_COLLAGE: Tall image containing two stacked visa cards.
        - SINGLE_VISA_CARD: Single isolated visa card.
        - GENERIC_SINGLE_DOCUMENT: Standard isolated document.
        """
        h, w = img.shape[:2]

        # 1. Stacked visa cards (tall aspect ratio, height > width)
        if h > w and h >= 800:
            return "STACKED_VISA_COLLAGE"

        # Quick downscaled text inspection for distinguishing wide cards
        try:
            import pytesseract
            small = cv2.resize(img, (min(w, 600), min(h, 400)))
            txt = pytesseract.image_to_string(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)).lower()
        except Exception:
            txt = filename.lower()

        # 2. Single visa card (contains visa marker and not booklet cover/MRZ)
        if "visa" in txt and not ("p<ind" in txt or "front cover" in txt or "sample)" in txt):
            return "SINGLE_VISA_CARD"

        # 3. Wide booklet spread (e.g. 1264x843, 896x628, 1024x682)
        if (w / max(h, 1)) >= 1.25 and ("passport" in txt or "republic of india" in txt or "p<ind" in txt or "cover" in txt or w >= 800):
            return "PASSPORT_BOOKLET_COLLAGE"

        return "GENERIC_SINGLE_DOCUMENT"

    @classmethod
    def extract_regions(
        cls,
        parent_filepath: str,
        output_base_dir: str
    ) -> List[Dict[str, Any]]:
        """
        Decomposes parent image into isolated document regions and persists them to disk.
        Returns a list of region descriptors with complete provenance lineage.
        """
        if not os.path.exists(parent_filepath):
            return []

        img = cv2.imread(parent_filepath)
        if img is None:
            return []

        parent_hash = cls.sha256_file(parent_filepath)
        parent_filename = os.path.basename(parent_filepath)
        h, w = img.shape[:2]
        layout = cls.detect_layout_type(img, parent_filename)

        passports_dir = os.path.join(output_base_dir, "passports")
        visas_dir = os.path.join(output_base_dir, "visas")
        booklets_dir = os.path.join(output_base_dir, "booklets")
        variants_dir = os.path.join(output_base_dir, "mutations", "visa_tampering")

        os.makedirs(passports_dir, exist_ok=True)
        os.makedirs(visas_dir, exist_ok=True)
        os.makedirs(booklets_dir, exist_ok=True)
        os.makedirs(variants_dir, exist_ok=True)

        regions: List[Dict[str, Any]] = []

        if layout == "PASSPORT_BOOKLET_COLLAGE":
            # Three horizontal panels: Cover, Observation Page, Identity Page
            # 1. Identity Page (Right half) - Contains full identity card, MRZ, and photo
            id_crop = img[:, int(w * 0.48):]
            id_crop_name = f"crop_id_{parent_hash[:8]}.jpg"
            id_crop_path = os.path.join(passports_dir, id_crop_name)
            cv2.imwrite(id_crop_path, id_crop)
            id_crop_hash = cls.sha256_file(id_crop_path)

            regions.append({
                "parent_filename": parent_filename,
                "parent_sha256": parent_hash,
                "document_crop_sha256": id_crop_hash,
                "crop_filepath": id_crop_path,
                "region_role": "IDENTITY_PAGE",
                "document_type": "PASSPORT",
                "is_primary_screening_target": True,
                "bounding_box": [int(w * 0.48), 0, w, h],
                "lineage": f"{parent_hash} -> {id_crop_hash} (IDENTITY_PAGE)"
            })

            # 2. Cover / Address Page (Left quarter)
            cov_crop = img[:, :int(w * 0.25)]
            cov_crop_name = f"crop_cover_{parent_hash[:8]}.jpg"
            cov_crop_path = os.path.join(booklets_dir, cov_crop_name)
            cv2.imwrite(cov_crop_path, cov_crop)
            cov_crop_hash = cls.sha256_file(cov_crop_path)

            regions.append({
                "parent_filename": parent_filename,
                "parent_sha256": parent_hash,
                "document_crop_sha256": cov_crop_hash,
                "crop_filepath": cov_crop_path,
                "region_role": "COVER_PAGE",
                "document_type": "PASSPORT_COVER",
                "is_primary_screening_target": False,
                "bounding_box": [0, 0, int(w * 0.25), h],
                "lineage": f"{parent_hash} -> {cov_crop_hash} (COVER_PAGE)"
            })

            # 3. Observation / Back Cover Page (Center quarter)
            obs_crop = img[:, int(w * 0.25):int(w * 0.50)]
            obs_crop_name = f"crop_obs_{parent_hash[:8]}.jpg"
            obs_crop_path = os.path.join(booklets_dir, obs_crop_name)
            cv2.imwrite(obs_crop_path, obs_crop)
            obs_crop_hash = cls.sha256_file(obs_crop_path)

            regions.append({
                "parent_filename": parent_filename,
                "parent_sha256": parent_hash,
                "document_crop_sha256": obs_crop_hash,
                "crop_filepath": obs_crop_path,
                "region_role": "OBSERVATION_PAGE",
                "document_type": "PASSPORT_OBSERVATION",
                "is_primary_screening_target": False,
                "bounding_box": [int(w * 0.25), 0, int(w * 0.50), h],
                "lineage": f"{parent_hash} -> {obs_crop_hash} (OBSERVATION_PAGE)"
            })

        elif layout == "STACKED_VISA_COLLAGE":
            # Two vertical cards: Top = Reference Visa, Bottom = Visa Variant
            # 1. Top Visa (Reference Card)
            mid_y = int(h * 0.50)
            top_crop = img[:mid_y, :]
            top_crop_name = f"crop_visa_ref_{parent_hash[:8]}.jpg"
            top_crop_path = os.path.join(visas_dir, top_crop_name)
            cv2.imwrite(top_crop_path, top_crop)
            top_crop_hash = cls.sha256_file(top_crop_path)

            regions.append({
                "parent_filename": parent_filename,
                "parent_sha256": parent_hash,
                "document_crop_sha256": top_crop_hash,
                "crop_filepath": top_crop_path,
                "region_role": "VISA_CARD",
                "document_type": "VISA",
                "is_primary_screening_target": True,
                "bounding_box": [0, 0, w, mid_y],
                "lineage": f"{parent_hash} -> {top_crop_hash} (VISA_CARD_REF)"
            })

            # 2. Bottom Visa (Visa Variant with altered linkage)
            bot_crop = img[mid_y:, :]
            bot_crop_name = f"crop_visa_var_{parent_hash[:8]}.jpg"
            bot_crop_path = os.path.join(variants_dir, bot_crop_name)
            cv2.imwrite(bot_crop_path, bot_crop)
            bot_crop_hash = cls.sha256_file(bot_crop_path)

            regions.append({
                "parent_filename": parent_filename,
                "parent_sha256": parent_hash,
                "document_crop_sha256": bot_crop_hash,
                "crop_filepath": bot_crop_path,
                "region_role": "VISA_VARIANT",
                "document_type": "VISA",
                "is_primary_screening_target": False,
                "bounding_box": [0, mid_y, w, h],
                "lineage": f"{parent_hash} -> {bot_crop_hash} (VISA_VARIANT)"
            })

        else:
            # Single Visa / Generic Document Card
            doc_crop_name = f"crop_doc_{parent_hash[:8]}.jpg"
            doc_crop_path = os.path.join(visas_dir, doc_crop_name)
            cv2.imwrite(doc_crop_path, img)
            doc_crop_hash = cls.sha256_file(doc_crop_path)

            regions.append({
                "parent_filename": parent_filename,
                "parent_sha256": parent_hash,
                "document_crop_sha256": doc_crop_hash,
                "crop_filepath": doc_crop_path,
                "region_role": "VISA_CARD",
                "document_type": "VISA",
                "is_primary_screening_target": True,
                "bounding_box": [0, 0, w, h],
                "lineage": f"{parent_hash} -> {doc_crop_hash} (SINGLE_VISA_CARD)"
            })

        return regions
