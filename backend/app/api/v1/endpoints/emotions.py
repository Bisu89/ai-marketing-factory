from fastapi import APIRouter, Depends

from app.api.deps import get_emotion_service
from app.schemas.emotion import EmotionOut
from app.services.library.service import EmotionService

router = APIRouter()


@router.get("/emotions", response_model=list[EmotionOut])
def list_emotions(service: EmotionService = Depends(get_emotion_service)):
    return service.list()
