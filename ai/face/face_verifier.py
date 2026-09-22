"""
SatyaScan Face Verification & Appearance Analysis Engine
========================================================
Performs local face detection, quality assessment, 512-dimensional Gabor-LBP
feature descriptor extraction, and authentic unit-sphere cosine similarity calculation.
Crucially distinguishes biometric IDENTITY SIMILARITY from VISIBLE APPEARANCE VARIATION
(facial hair, eyewear, lighting, and aging).

Preserves full backward compatibility while integrating Biometric V2 architecture.
"""

from typing import Dict, Any, Optional, Tuple, List
import numpy as np
from ai.face.service import FaceVerificationService


class FaceVerifier(FaceVerificationService):
    """
    Biometric face verification and appearance analysis module.
    Inherits from FaceVerificationService for modular Biometric V2 provider architecture.
    """

    MATCH_THRESHOLD = 0.65
    BORDERLINE_THRESHOLD = 0.50

    def __init__(self):
        super().__init__()
