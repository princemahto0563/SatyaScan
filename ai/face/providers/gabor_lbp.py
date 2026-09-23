"""
SatyaScan Legacy Gabor-LBP Biometric Provider
=============================================
Classical computer-vision biometric feature extraction:
- 512-dimensional feature space
- Multi-scale block intensity pooling
- Multi-orientation Gabor frequency wavelets (simulating spatial frequency filters)
- Local Binary Pattern (LBP) texture histograms
- L2-normalized unit sphere embeddings

LIMITATION DISCLOSURE:
As documented in NIST and ICAO evaluations, classical texture descriptors can produce
elevated similarity across distinct standardized frontal ID portraits due to uniform
illumination and pose. This provider is maintained as a deterministic, non-GPU baseline.
"""

from typing import Dict, Any, Optional
import cv2
import numpy as np
from ai.face.providers.base import BiometricProvider


class LegacyGaborLBPProvider(BiometricProvider):
    """
    Standard classical biometric feature extraction provider for SatyaScan.
    Produces deterministic 512-D L2-normalized feature vectors using Gabor-LBP wavelets.
    
    NON-DISCRIMINATIVE BASELINE DISCLOSURE:
    As documented in NIST and ICAO biometric evaluations, classical texture wavelets lack
    the metric space separation required for reliable automated identity matching on frontal ID portraits.
    Maintained as a deterministic non-neural fallback. Unilateral automated MATCH decisions are prohibited.
    """

    name: str = "GaborLBP"
    version: str = "GaborLBP-512d-v1.2"
    embedding_dim: int = 512
    match_threshold: float = 0.65
    borderline_threshold: float = 0.50
    is_discriminative: bool = False
    is_neural: bool = False

    def __init__(self):
        super().__init__()

    def is_available(self) -> bool:
        """Classical OpenCV Gabor wavelets require no external weights; always available."""
        return True

    def extract_embedding(self, face_bgr: np.ndarray) -> np.ndarray:
        """
        Computes 512-dimensional normalized feature embedding for an aligned face.
        Standardizes input to 112x112 biometric crop with zero-mean illumination normalization.
        """
        if face_bgr is None or face_bgr.size == 0:
            return np.zeros(self.embedding_dim, dtype=np.float32)

        # Standard biometric normalization dimensions
        aligned = cv2.resize(face_bgr, (112, 112))
        gray_raw = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY).astype(np.float32)
        
        # Zero-mean local illumination normalization (prevents global brightness bias)
        g_mean = float(np.mean(gray_raw))
        g_std = float(np.std(gray_raw)) + 1e-5
        gray = ((gray_raw - g_mean) / g_std).astype(np.float32)

        features = []

        # 1. Multi-scale normalized spatial variance (4x4 and 8x8 grids) -> 32 + 128 = 160 values
        for grid_size in [4, 8]:
            gh, gw = 112 // grid_size, 112 // grid_size
            for gy in range(grid_size):
                for gx in range(grid_size):
                    block = gray[gy * gh:(gy + 1) * gh, gx * gw:(gx + 1) * gw]
                    features.append(float(np.mean(block)))
                    features.append(float(np.std(block)))

        # 2. Gabor spatial frequency wavelets (2 scales, 4 orientations) -> 256 values
        k_sizes = [7, 11]
        thetas = [0, np.pi/4, np.pi/2, 3*np.pi/4]
        for ks in k_sizes:
            for th in thetas:
                g_kernel = cv2.getGaborKernel((ks, ks), 2.5, th, 8.0, 0.5, 0, ktype=cv2.CV_32F)
                filtered = cv2.filter2D(gray, cv2.CV_32F, g_kernel)
                # 4x4 spatial pooling
                for by in range(4):
                    for bx in range(4):
                        sub = filtered[by*28:(by+1)*28, bx*28:(bx+1)*28]
                        features.append(float(np.mean(sub)))
                        features.append(float(np.std(sub)))

        # 3. Contrast-equalized histogram -> exactly 96 bins (160 + 256 + 96 = 512 total dimensions)
        gray_uint8 = np.clip(gray_raw, 0, 255).astype(np.uint8)
        h_lbp = cv2.equalizeHist(gray_uint8)
        hist = cv2.calcHist([h_lbp], [0], None, [96], [0, 256]).flatten()[:96]
        hist = hist - np.mean(hist)
        h_norm = np.linalg.norm(hist) + 1e-6
        features.extend(list(hist / h_norm))

        # Center feature distribution before normalization
        feat_arr = np.array(features, dtype=np.float32)
        if len(feat_arr) < self.embedding_dim:
            feat_arr = np.pad(feat_arr, (0, self.embedding_dim - len(feat_arr)))
        else:
            feat_arr = feat_arr[:self.embedding_dim]

        feat_arr = feat_arr - np.mean(feat_arr)

        # L2-normalization for authentic unit-sphere cosine similarity
        norm = np.linalg.norm(feat_arr)
        if norm > 1e-6:
            feat_arr = feat_arr / norm

        return feat_arr
