"""
SatyaScan Copy-Move Forgery Detection (CMFD)
Detects cloned document regions (stamps, numbers, signatures) using
ORB feature keypoint matching and spatial offset clustering.
"""

from typing import Dict, Any, List
import cv2
import numpy as np


class CopyMoveDetector:
    """
    Keypoint-based Copy-Move Forgery Detector.
    Identifies cloned regions duplicated within the same document image.
    """

    def __init__(self, n_features: int = 1200, min_spatial_distance: float = 55.0):
        self.n_features = n_features
        self.min_spatial_distance = min_spatial_distance
        self.version = "CMFD-ORB-v1.0"

    def analyze(self, image_input: Any) -> Dict[str, Any]:
        """
        Runs keypoint extraction and self-similarity matching.
        """
        if isinstance(image_input, str):
            img = cv2.imread(image_input)
        elif isinstance(image_input, np.ndarray):
            img = image_input
        else:
            return {"error": "Invalid image input"}

        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        # 1. Detect ORB features and descriptors
        orb = cv2.ORB_create(nfeatures=self.n_features, fastThreshold=15)
        keypoints, descriptors = orb.detectAndCompute(gray, None)

        if descriptors is None or len(keypoints) < 20:
            return {
                "technique": "Copy-Move Forgery Detection",
                "anomaly_score": 0.0,
                "matches_found": 0,
                "observation": "Insufficient keypoints extracted for copy-move analysis.",
                "interpretation": "Insufficient texture or features to assess self-cloning.",
                "recommendation": "Document surface lacks sufficient keypoint density."
            }

        # 2. Match descriptors against themselves using BFMatcher (KNN k=2)
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        knn_matches = bf.knnMatch(descriptors, descriptors, k=3)

        # 3. Filter matches: ignore identity match (k=0 is self), check k=1 and k=2 with distance and spatial offset
        cloned_pairs: List[Dict[str, Any]] = []
        displacement_vectors: List[Tuple[float, float]] = []

        for match_group in knn_matches:
            if len(match_group) < 2:
                continue
            m1 = match_group[1]  # Closest non-self descriptor match
            kp1 = keypoints[m1.queryIdx]
            kp2 = keypoints[m1.trainIdx]

            # Spatial Euclidean distance between keypoints
            pt1 = np.array(kp1.pt)
            pt2 = np.array(kp2.pt)
            spatial_dist = float(np.linalg.norm(pt1 - pt2))

            # Filter out neighboring keypoints (natural texture correlation)
            if spatial_dist >= self.min_spatial_distance and m1.distance < 45:
                disp = (float(pt2[0] - pt1[0]), float(pt2[1] - pt1[1]))
                cloned_pairs.append({
                    "src_point": [round(float(pt1[0]), 1), round(float(pt1[1]), 1)],
                    "dst_point": [round(float(pt2[0]), 1), round(float(pt2[1]), 1)],
                    "descriptor_distance": int(m1.distance),
                    "spatial_offset": round(spatial_dist, 1)
                })
                displacement_vectors.append(disp)

        # 4. Cluster displacement vectors to find coherent cloned blocks
        # Genuine copy-move has consistent displacement vectors
        coherent_clusters = 0
        if len(cloned_pairs) >= 5:
            # Quantize displacement vectors into 20-pixel bins
            bins: Dict[Tuple[int, int], int] = {}
            for dx, dy in displacement_vectors:
                bx = int(dx // 25)
                by = int(dy // 25)
                bins[(bx, by)] = bins.get((bx, by), 0) + 1
            max_cluster = max(bins.values()) if bins else 0
            if max_cluster >= 4:
                coherent_clusters = max_cluster

        # Calculate anomaly score
        raw_score = (coherent_clusters * 16.0) + min(len(cloned_pairs) * 1.5, 30.0)
        anomaly_score = round(min(max(float(raw_score), 0.0), 100.0), 1)

        observation = (
            f"Detected {len(cloned_pairs)} descriptor match pairs exceeding spatial threshold. "
            f"Largest coherent displacement cluster: {coherent_clusters} keypoints."
            if cloned_pairs else
            "No spatially separated duplicated keypoint clusters detected."
        )

        interpretation = (
            "Potential copy-move duplication detected. Multiple feature keypoints share near-identical visual descriptors and coherent displacement."
            if anomaly_score >= 45.0 else
            "No evidence of copy-move or cloned visual elements found."
        )

        return {
            "technique": "Copy-Move Forgery Detection",
            "anomaly_score": anomaly_score,
            "total_keypoints": len(keypoints),
            "matches_found": len(cloned_pairs),
            "coherent_cluster_size": coherent_clusters,
            "matched_pairs": cloned_pairs[:20],  # Return up to 20 for UI rendering
            "observation": observation,
            "interpretation": interpretation,
            "recommendation": "Inspect visual elements (stamps, text, seals) for duplication." if anomaly_score >= 45.0 else "Normal baseline."
        }
