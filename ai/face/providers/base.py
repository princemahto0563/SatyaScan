"""
SatyaScan Biometric Provider Interface
======================================
Defines the contract for face recognition feature extractors and similarity engines.
Supports modular swapping between classical descriptors and modern neural backends.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import numpy as np


class BiometricProvider(ABC):
    """Abstract base class for all SatyaScan biometric feature extraction providers."""

    name: str = "BaseProvider"
    version: str = "Base-v1.0"
    embedding_dim: int = 512
    match_threshold: float = 0.65
    borderline_threshold: float = 0.50

    @abstractmethod
    def extract_embedding(self, face_bgr: np.ndarray) -> np.ndarray:
        """
        Extracts a normalized feature embedding from an aligned face image (BGR).
        Returns a 1D float32 numpy array of length `embedding_dim`.
        Must be L2-normalized so that inner product equals cosine similarity.
        """
        pass

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """
        Calculates cosine similarity between two normalized feature vectors.
        Returns value clipped in range [-1.0, 1.0].
        """
        if emb1 is None or emb2 is None:
            return 0.0
        e1 = np.asarray(emb1, dtype=np.float32).flatten()
        e2 = np.asarray(emb2, dtype=np.float32).flatten()
        norm1 = float(np.linalg.norm(e1))
        norm2 = float(np.linalg.norm(e2))
        if norm1 < 1e-6 or norm2 < 1e-6:
            return 0.0
        cosine = float(np.dot(e1, e2) / (norm1 * norm2))
        return round(float(np.clip(cosine, -1.0, 1.0)), 4)

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if model weights and runtime dependencies are available."""
        pass
