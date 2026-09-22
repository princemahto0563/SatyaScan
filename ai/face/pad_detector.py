"""
SatyaScan Presentation Attack Detector (PAD)
============================================
Modular interface and evaluator for Presentation Attack Detection (Liveness / Anti-Spoofing).

CRITICAL STANDARDS & ETHICAL DISCLOSURES:
- Absence of presentation attack detection must NEVER be interpreted as certified liveness.
- In this prototype configuration, presentation-attack detection returns NOT_AVAILABLE
  with clear explanation, preventing any false assurance of ISO/NIST PAD compliance.
- No simple image heuristics are marketed or reported as certified liveness.
"""

from typing import Dict, Any, Optional, List, Tuple
from abc import ABC, abstractmethod
import numpy as np


class BasePresentationAttackDetector(ABC):
    """Abstract interface for modular Presentation Attack Detection."""

    @abstractmethod
    def detect(
        self,
        img_bgr: np.ndarray,
        face_box: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates facial presentation for spoofing / presentation attacks (screen, print, mask).
        Returns status in: [PASS, REVIEW, FAIL, NOT_AVAILABLE]
        """
        pass


class PresentationAttackDetector(BasePresentationAttackDetector):
    """
    Standard Prototype PAD implementation.
    Consistently and transparently reports NOT_AVAILABLE in the prototype baseline,
    ensuring operators and deployers are not misled regarding liveness certification.
    """

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.version = "PAD-ModularInterface-v1.0"

    def detect(
        self,
        img_bgr: np.ndarray,
        face_box: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "status": "NOT_AVAILABLE",
                "reason": "Presentation-attack detection is not enabled in this prototype.",
                "method": "NONE",
                "certified": False,
                "disclaimer": (
                    "Presentation-attack detection is inactive. Absence of PAD flags "
                    "must not be interpreted as certified biometric liveness."
                )
            }

        # If a future certified PAD plugin is attached:
        return {
            "status": "NOT_AVAILABLE",
            "reason": "Presentation-attack detection is not enabled in this prototype.",
            "method": "NONE",
            "certified": False,
            "disclaimer": "Prototype environment does not include certified ISO/IEC 30107-3 PAD hardware/models."
        }
