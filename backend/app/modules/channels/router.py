"""Owned channels + sync (see models.py). Errors from the service layer
become 404/400/502 JSON via the handlers in app/main.py."""

from fastapi import APIRouter

from app.modules.channels import service
from app.modules.channels.schemas import ChannelIn, ChannelOut, ChannelPatch, MetricOut, SyncRunOut

router = APIRouter()


@router.get("/channels", response_model=list[ChannelOut])
def list_channels() -> list[ChannelOut]:
    return [ChannelOut.from_row(c) for c in service.list_channels()]


@router.post("/channels", response_model=ChannelOut, status_code=201)
def create_channel(payload: ChannelIn) -> ChannelOut:
    return ChannelOut.from_row(service.create_channel(**payload.model_dump()))


@router.patch("/channels/{channel_id}", response_model=ChannelOut)
def update_channel(channel_id: int, payload: ChannelPatch) -> ChannelOut:
    return ChannelOut.from_row(service.update_channel(channel_id, **payload.model_dump(exclude_unset=True)))


@router.delete("/channels/{channel_id}", status_code=204)
def delete_channel(channel_id: int) -> None:
    service.delete_channel(channel_id)


@router.post("/channels/{channel_id}/sync", response_model=SyncRunOut)
def sync_channel(channel_id: int) -> SyncRunOut:
    return SyncRunOut.model_validate(service.sync_channel(channel_id), from_attributes=True)


@router.get("/channels/{channel_id}/metrics", response_model=list[MetricOut])
def list_metrics(channel_id: int, limit: int = 90) -> list[MetricOut]:
    return [MetricOut.model_validate(m, from_attributes=True) for m in service.list_metrics(channel_id, limit)]


@router.get("/channels/{channel_id}/sync-runs", response_model=list[SyncRunOut])
def list_sync_runs(channel_id: int) -> list[SyncRunOut]:
    return [SyncRunOut.model_validate(r, from_attributes=True) for r in service.list_sync_runs(channel_id)]
