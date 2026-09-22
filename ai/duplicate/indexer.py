"""
SatyaScan Duplicate / Multi-Identity Vector Search Engine
Utilizes FAISS (Facebook AI Similarity Search) IndexFlatIP
to cross-check facial biometric embeddings against a synthetic reference gallery
to detect individuals operating under multiple distinct travel identities.
"""

from typing import Dict, Any, List, Optional
try:
    import faiss
    FAISS_AVAILABLE = True
except Exception:
    faiss = None
    FAISS_AVAILABLE = False
import numpy as np
import json
import os


class MultiIdentityIndexer:
    """
    Vector search engine for detecting duplicate identity reuse.
    Utilizes FAISS IndexFlatIP when available, with a mathematically equivalent
    pure-NumPy cosine dot-product fallback for containerized/minimal environments.
    Maintains synthetic identity vectors and cross-matches incoming screenings.
    """

    DUPLICATE_THRESHOLD = 0.72  # Cosine similarity threshold for multi-identity flag

    def __init__(self, embedding_dim: int = 512):
        self.embedding_dim = embedding_dim
        if FAISS_AVAILABLE and faiss is not None:
            self.version = "FAISS-IndexFlatIP-v1.0"
            self.index = faiss.IndexFlatIP(self.embedding_dim)
        else:
            self.version = "NumPy-VectorSearch-v1.0"
            self.index = None
            self._embeddings_list: List[np.ndarray] = []
        self.metadata_store: List[Dict[str, Any]] = []

    @property
    def total_records(self) -> int:
        if self.index is not None:
            return self.index.ntotal
        return len(getattr(self, "_embeddings_list", []))

    def add_identity(
        self,
        doc_id: str,
        name: str,
        embedding: np.ndarray,
        doc_type: str = "PASSPORT",
        status: str = "ACTIVE"
    ) -> int:
        """
        Adds a synthetic identity embedding and associated metadata to the index.
        """
        # Ensure embedding is 2D float32 and unit-normalized
        emb = np.array(embedding, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(emb)
        if norm > 1e-6:
            emb = emb / norm

        if self.index is not None:
            idx = self.index.ntotal
            self.index.add(emb)
        else:
            idx = len(self._embeddings_list)
            self._embeddings_list.append(emb[0])

        self.metadata_store.append({
            "index_id": idx,
            "document_id": doc_id,
            "name": name,
            "document_type": doc_type,
            "status": status,
            "classification": "SYNTHETIC_REFERENCE_RECORD"
        })
        return idx

    def search_duplicate(
        self,
        query_embedding: np.ndarray,
        current_doc_id: Optional[str] = None,
        top_k: int = 3
    ) -> Dict[str, Any]:
        """
        Searches index for nearest biometric neighbors.
        Flags potential duplicate identity if high similarity is found for a DIFFERENT document/name.
        """
        total = self.total_records
        if total == 0:
            return {
                "duplicate_detected": False,
                "matches": [],
                "alert": None,
                "total_records_searched": 0
            }

        q = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(q)
        if norm > 1e-6:
            q = q / norm

        k = min(top_k, total)

        if self.index is not None:
            distances, indices = self.index.search(q, k)
            dist_list = distances[0]
            idx_list = indices[0]
        else:
            # Pure NumPy cosine dot-product (exact equivalent of IndexFlatIP for L2-normalized vectors)
            matrix = np.array(self._embeddings_list, dtype=np.float32)  # shape (N, 512)
            scores = np.dot(matrix, q.T).flatten()                      # shape (N,)
            top_k_indices = np.argsort(-scores)[:k]
            idx_list = top_k_indices
            dist_list = scores[top_k_indices]

        matches: List[Dict[str, Any]] = []
        duplicate_flag = False
        primary_alert = None

        for dist, idx in zip(dist_list, idx_list):
            if idx < 0 or idx >= len(self.metadata_store):
                continue
            meta = self.metadata_store[idx]
            sim = float(dist)

            match_info = {
                "document_id": meta["document_id"],
                "name": meta["name"],
                "status": meta["status"],
                "similarity": round(sim, 3),
                "is_same_document": (meta["document_id"] == current_doc_id)
            }
            matches.append(match_info)

            # Check if high similarity matches a DIFFERENT document ID
            if sim >= self.DUPLICATE_THRESHOLD and not match_info["is_same_document"]:
                duplicate_flag = True
                primary_alert = {
                    "severity": "CRITICAL",
                    "matched_document_id": meta["document_id"],
                    "matched_name": meta["name"],
                    "similarity": round(sim, 3),
                    "message": (
                        f"Potential Multi-Identity Reuse: Current face matches existing synthetic record "
                        f"'{meta['document_id']}' (Registered as '{meta['name']}') with {sim:.2f} biometric similarity."
                    )
                }

        return {
            "duplicate_detected": duplicate_flag,
            "threshold": self.DUPLICATE_THRESHOLD,
            "total_records_searched": total,
            "primary_alert": primary_alert,
            "matches": matches,
            "indexer_version": self.version
        }
