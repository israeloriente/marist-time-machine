"""InsightFace wrapper. Loads SCRFD detector + ArcFace recognizer once.

Mirrors Immich's approach: buffalo_l bundle, 5-point landmarks, 112x112
crop normalization done by InsightFace internals, 512-D L2-normalized
embedding ready for cosine similarity in pgvector.
"""

from __future__ import annotations

import io
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np
from insightface.app import FaceAnalysis
from PIL import Image, ImageOps

from .config import DET_SIZE, DET_THRESHOLD, MODEL_NAME


@dataclass
class DetectedFace:
    bbox: list[float]
    landmarks: list[list[float]]
    detection_score: float
    embedding: list[float]


class FaceEngine:
    _instance: "FaceEngine | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        # CPU-only providers; add CUDAExecutionProvider if GPU available.
        providers = ["CPUExecutionProvider"]
        self.app = FaceAnalysis(name=MODEL_NAME, providers=providers)
        self.app.prepare(ctx_id=0, det_size=(DET_SIZE, DET_SIZE), det_thresh=DET_THRESHOLD)

    @classmethod
    def get(cls) -> "FaceEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @staticmethod
    def _decode(image_bytes: bytes) -> np.ndarray:
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
        # InsightFace expects BGR (OpenCV convention)
        arr = np.array(img)[:, :, ::-1].copy()
        return arr

    def analyze(self, image_bytes: bytes) -> list[DetectedFace]:
        bgr = self._decode(image_bytes)
        faces: list[Any] = self.app.get(bgr)
        out: list[DetectedFace] = []
        for f in faces:
            emb = f.normed_embedding  # already L2-normalized, shape (512,)
            out.append(
                DetectedFace(
                    bbox=[float(x) for x in f.bbox.tolist()],
                    landmarks=[[float(x), float(y)] for x, y in f.kps.tolist()],
                    detection_score=float(f.det_score),
                    embedding=[float(x) for x in emb.tolist()],
                )
            )
        return out
