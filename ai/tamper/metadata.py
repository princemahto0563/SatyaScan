"""
SatyaScan EXIF & Image Metadata Forensics
Extracts metadata, camera signatures, modification histories,
and image editing software tags (Photoshop, GIMP, Canva, etc.).
"""

from typing import Dict, Any, Optional
from PIL import Image, ExifTags
import os


class MetadataForensics:
    """
    Metadata and EXIF header forensic inspector.
    Note: Lack of metadata is common due to scanning/messaging compression and is NOT proof of forgery.
    However, presence of image manipulation software signatures provides strong supporting evidence.
    """

    SUSPICIOUS_SOFTWARE = [
        "adobe", "photoshop", "gimp", "canva", "procreate",
        "pixelmator", "affinity", "paint.net", "corel", "lightroom"
    ]

    def __init__(self):
        self.version = "MetadataForensics-v1.0"

    def analyze(self, image_path: str) -> Dict[str, Any]:
        """
        Extracts EXIF and format tags from image file.
        """
        if not os.path.exists(image_path):
            return {"error": "Image file not found"}

        try:
            with Image.open(image_path) as img:
                img_format = img.format
                img_mode = img.mode
                img_size = img.size

                raw_exif = img.getexif()
                exif_data: Dict[str, Any] = {}
                software_signature: Optional[str] = None
                modify_date: Optional[str] = None
                create_date: Optional[str] = None

                if raw_exif:
                    for tag_id, value in raw_exif.items():
                        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                        # Filter strings and numbers
                        if isinstance(value, (str, int, float)):
                            exif_data[tag_name] = str(value)
                            if tag_name.lower() == "software":
                                software_signature = str(value)
                            elif "modify" in tag_name.lower() or "datetime" in tag_name.lower():
                                modify_date = str(value)
                            elif "original" in tag_name.lower():
                                create_date = str(value)

                # Check for suspicious editing software
                is_tampered_software = False
                if software_signature:
                    sig_lower = software_signature.lower()
                    if any(sw in sig_lower for sw in self.SUSPICIOUS_SOFTWARE):
                        is_tampered_software = True

                anomaly_score = 65.0 if is_tampered_software else 0.0

                observation = (
                    f"EXIF metadata present. Software tag: '{software_signature}'. Format: {img_format} {img_size[0]}x{img_size[1]}."
                    if software_signature else
                    f"EXIF header is empty or stripped. Format: {img_format} {img_size[0]}x{img_size[1]}."
                )

                interpretation = (
                    f"Image editing software detected in metadata ('{software_signature}'). Strongly indicates post-capture modification."
                    if is_tampered_software else
                    "Metadata contains standard camera tags or has been neutralized by standard scanning pipelines. Neutral forensic signal."
                )

                return {
                    "technique": "Metadata / EXIF Forensics",
                    "anomaly_score": anomaly_score,
                    "exif_present": bool(exif_data),
                    "software_signature": software_signature,
                    "editing_software_detected": is_tampered_software,
                    "modify_date": modify_date,
                    "dimensions": {"width": img_size[0], "height": img_size[1]},
                    "format": img_format,
                    "exif_tags_count": len(exif_data),
                    "observation": observation,
                    "interpretation": interpretation,
                    "recommendation": "Review image edit history." if is_tampered_software else "Supporting metadata consistent."
                }
        except Exception as e:
            return {
                "technique": "Metadata / EXIF Forensics",
                "anomaly_score": 0.0,
                "error": str(e),
                "observation": "Metadata could not be extracted.",
                "interpretation": "Neutral forensic signal.",
                "recommendation": "None."
            }
