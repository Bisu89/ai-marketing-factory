"""Pure batch-domain read endpoint -- list batches, no knowledge of
app.modules.beat or app.modules.video_composer required (see models.py's
module docstring). Everything else (create, generate-beats, render,
cancel, retry, and the single-batch detail view -- which needs to sync
render status from VideoComposeJob and compute per-item render
eligibility) lives in the composition root instead --
app/api/v1/endpoints/batch_render.py -- per this codebase's established
"video_composer/router.py stays pure video_composer; composition_render.py
is where cross-module orchestration lives" split (see that file's own
module docstring for the precedent this mirrors).
"""

from fastapi import APIRouter

from app.modules.batch.schemas import BatchOut
from app.modules.batch.service import list_batches

router = APIRouter()


@router.get("/batches", response_model=list[BatchOut])
def list_all_batches() -> list[BatchOut]:
    return [BatchOut.model_validate(b, from_attributes=True) for b in list_batches()]
