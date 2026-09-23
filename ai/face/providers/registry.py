"""
SatyaScan Biometric Provider Registry
=====================================
Central factory for obtaining configured biometric feature extractors.
Ensures graceful fallback to LegacyGaborLBPProvider when modern neural models are not present.
"""

import logging
import os
from ai.face.providers.base import BiometricProvider
from ai.face.providers.gabor_lbp import LegacyGaborLBPProvider
from ai.face.providers.modern_face import ModernFaceProvider
from ai.face.providers.sface import SFaceProvider

logger = logging.getLogger(__name__)


def get_biometric_provider(preferred_provider: str = "auto") -> BiometricProvider:
    """
    Returns an instantiated and verified BiometricProvider.
    Attempts modern deep neural provider (SFace) by default or when requested.
    Falls back gracefully to LegacyGaborLBPProvider if weights or runtime are unavailable.
    """
    pref = preferred_provider.lower().strip()

    # 1. Check explicit Gabor request
    if pref == "gabor_lbp" or pref == "gabor":
        return LegacyGaborLBPProvider()

    # 2. Check SFace neural provider (default / auto / neural / modern)
    if pref in ["auto", "sface", "modern", "neural", "arcface"]:
        sface = SFaceProvider()
        if sface.is_available():
            return sface
        logger.info(
            "[Biometrics] SFaceProvider unavailable. Checking secondary neural adapters."
        )

        modern = ModernFaceProvider()
        if modern.is_available():
            return modern

        logger.info(
            "[Biometrics] Neural face providers not available. "
            "Falling back to baseline LegacyGaborLBPProvider (Classical)."
        )

    # Standard fallback baseline
    return LegacyGaborLBPProvider()

