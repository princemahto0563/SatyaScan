"""
SatyaScan Biometric Provider Registry
=====================================
Central factory for obtaining configured biometric feature extractors.
Ensures graceful fallback to LegacyGaborLBPProvider when modern neural models are not present.
"""

import logging
from ai.face.providers.base import BiometricProvider
from ai.face.providers.gabor_lbp import LegacyGaborLBPProvider
from ai.face.providers.modern_face import ModernFaceProvider

logger = logging.getLogger(__name__)


def get_biometric_provider(preferred_provider: str = "gabor_lbp") -> BiometricProvider:
    """
    Returns an instantiated and verified BiometricProvider.
    If the preferred provider is unavailable, falls back to LegacyGaborLBPProvider.
    """
    if preferred_provider.lower() in ["modern", "arcface", "neural"]:
        modern = ModernFaceProvider()
        if modern.is_available():
            return modern
        logger.info(
            "[Biometrics] ModernFaceProvider requested but weights/runtime not available. "
            "Falling back to baseline LegacyGaborLBPProvider."
        )

    # Standard default baseline
    return LegacyGaborLBPProvider()
