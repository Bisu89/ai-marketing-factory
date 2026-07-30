from fastapi import APIRouter, HTTPException

from app.schemas.detect import DetectRequest, DetectResultOut
from app.services.detect.ytdlp_detector import DetectionError, detect_url

router = APIRouter()


@router.post("/detect", response_model=DetectResultOut)
def detect(payload: DetectRequest):
    try:
        return detect_url(str(payload.url))
    except DetectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
