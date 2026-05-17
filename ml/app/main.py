from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from .config import DET_SIZE, DET_THRESHOLD, MODEL_NAME
from .engine import FaceEngine

app = FastAPI(title="Marist Time Machine — ML", version="0.1.0")


class FaceDTO(BaseModel):
    bbox: list[float]
    landmarks: list[list[float]]
    detection_score: float
    embedding: list[float]


class AnalyzeResponse(BaseModel):
    faces: list[FaceDTO]


@app.on_event("startup")
def _warmup() -> None:
    FaceEngine.get()


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "det_threshold": DET_THRESHOLD,
        "det_size": DET_SIZE,
    }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)) -> AnalyzeResponse:
    """Detect + align + embed all faces in one pass (matches InsightFace API)."""
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="file must be an image")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="empty payload")
    faces = FaceEngine.get().analyze(payload)
    return AnalyzeResponse(faces=[FaceDTO(**f.__dict__) for f in faces])
