from fastapi import APIRouter, Depends, Query

from app.api.deps import get_video_library_service
from app.schemas.tag import VideoTagsIn
from app.schemas.video import VideoImportIn, VideoListResponse, VideoOut, VideoUpdateIn, video_to_out
from app.services.library.service import VideoLibraryService

router = APIRouter()


@router.get("/videos", response_model=VideoListResponse)
def list_videos(
    search: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    category_id: int | None = None,
    emotion_id: int | None = None,
    tag: str | None = None,
    favorite: bool | None = None,
    duration: str | None = None,
    resolution: str | None = None,
    sort: str = "newest",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    service: VideoLibraryService = Depends(get_video_library_service),
):
    items, total = service.list_videos(
        search=search,
        platform=platform,
        status=status,
        category_id=category_id,
        emotion_id=emotion_id,
        tag=tag,
        favorite=favorite,
        duration=duration,
        resolution=resolution,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return VideoListResponse(
        items=[video_to_out(v, service.library_dir) for v in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/videos", response_model=VideoOut, status_code=201)
def import_video(payload: VideoImportIn, service: VideoLibraryService = Depends(get_video_library_service)):
    video = service.import_existing_file(
        file_path=payload.file_path,
        platform=payload.platform,
        channel_name=payload.channel_name,
        title=payload.title,
        external_id=payload.external_id,
        category_id=payload.category_id,
        notes=payload.notes,
        tags=payload.tags,
    )
    return video_to_out(video, service.library_dir)


@router.get("/videos/{video_id}", response_model=VideoOut)
def get_video(video_id: int, service: VideoLibraryService = Depends(get_video_library_service)):
    return video_to_out(service.get_video(video_id), service.library_dir)


@router.put("/videos/{video_id}", response_model=VideoOut)
def update_video(
    video_id: int,
    payload: VideoUpdateIn,
    service: VideoLibraryService = Depends(get_video_library_service),
):
    video = service.update_video(
        video_id,
        status=payload.status,
        category_id=payload.category_id,
        emotion_id=payload.emotion_id,
        notes=payload.notes,
    )
    return video_to_out(video, service.library_dir)


@router.delete("/videos/{video_id}", status_code=204)
def delete_video(
    video_id: int,
    hard: bool = False,
    service: VideoLibraryService = Depends(get_video_library_service),
):
    service.delete_video(video_id, hard=hard)


@router.post("/videos/{video_id}/open-folder", status_code=204)
def open_video_folder(video_id: int, service: VideoLibraryService = Depends(get_video_library_service)):
    service.open_folder(video_id)


@router.post("/videos/{video_id}/favorite", response_model=VideoOut)
def favorite_video(video_id: int, service: VideoLibraryService = Depends(get_video_library_service)):
    return video_to_out(service.set_favorite(video_id, True), service.library_dir)


@router.delete("/videos/{video_id}/favorite", response_model=VideoOut)
def unfavorite_video(video_id: int, service: VideoLibraryService = Depends(get_video_library_service)):
    return video_to_out(service.set_favorite(video_id, False), service.library_dir)


@router.post("/videos/{video_id}/tags", response_model=VideoOut)
def add_video_tags(
    video_id: int,
    payload: VideoTagsIn,
    service: VideoLibraryService = Depends(get_video_library_service),
):
    return video_to_out(service.add_tags(video_id, payload.tag_names), service.library_dir)


@router.delete("/videos/{video_id}/tags/{tag_id}", response_model=VideoOut)
def remove_video_tag(
    video_id: int,
    tag_id: int,
    service: VideoLibraryService = Depends(get_video_library_service),
):
    return video_to_out(service.remove_tag(video_id, tag_id), service.library_dir)
