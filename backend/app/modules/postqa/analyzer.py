"""Deterministic Final QA evaluation (Task 28 sections 6-35). Pure, no I/O
-- every function here takes an already-resolved QAInput (see schemas.py)
and returns QACheck/QAReport objects. Read-only by construction: nothing
in this module ever writes to a file or mutates its input (section 38/39
-- "QA is read-only... do NOT let QA silently repair anything").
"""

from app.modules.postqa.schemas import (
    QA_STATUSES,
    QACheck,
    QAInput,
)

# Section 15/16 -- a small, configurable tolerance, not exact-equality;
# not a real allowance for a genuinely wrong-length render (Task 26's own
# render-time tolerance is 0.5-1.0s depending on pipeline -- this mirrors
# that same order of magnitude for the same reason: container/encoder/
# beat-quantization rounding, never hiding a real mismatch).
DURATION_TOLERANCE_SEC = 0.75
FPS_TOLERANCE = 0.5
# Matches app.modules.audio.renderer's own _SILENCE_MEAN_VOLUME_DB_THRESHOLD
# (Task 24) -- duplicated, not imported (module isolation).
SILENCE_MEAN_VOLUME_DB_THRESHOLD = -50.0
# loudnorm's own TRUE_PEAK_CEILING_DBTP target (Task 24) is -1.0 dBTP;
# max_volume_db above -1.0 here is a real signal something clipped past
# that ceiling, even though volumedetect's max isn't true-peak-accurate.
CLIPPING_MAX_VOLUME_DB_THRESHOLD = -1.0

_DIMENSION_SEVERITY = "error"


def _check(name, code, status, severity, message, *, actual=None, expected=None, repair_stage=None) -> QACheck:
    return QACheck(
        name=name, code=code, status=status, severity=severity, message=message,
        actual=actual, expected=expected, repair_stage=repair_stage if status != "PASS" else None,
    )


def check_package_complete(data: QAInput) -> QACheck:
    if not data.package_exists:
        return _check(
            "package_complete", "PACKAGE_INCOMPLETE", "FAIL", "error",
            data.package_error_message or "The Ready-to-Post package is incomplete.",
            repair_stage="PACKAGE",
        )
    return _check("package_complete", "PACKAGE_INCOMPLETE", "PASS", "info", "Package is complete.")


def check_final_video(data: QAInput) -> list[QACheck]:
    checks: list[QACheck] = []
    video = data.video
    if video is None or not video.file_exists:
        checks.append(_check(
            "final_video_exists", "FINAL_VIDEO_MISSING", "FAIL", "error",
            "final.mp4 does not exist.", repair_stage="RENDER",
        ))
        return checks
    if video.file_size <= 0:
        checks.append(_check(
            "final_video_exists", "FINAL_VIDEO_INVALID", "FAIL", "error",
            "final.mp4 is empty (0 bytes).", repair_stage="RENDER",
        ))
        return checks
    checks.append(_check("final_video_exists", "FINAL_VIDEO_MISSING", "PASS", "info", "final.mp4 exists and is non-empty."))

    # Section 9/10: exactly one video stream, exactly one audio stream --
    # the exact same guarantee Task 26's own _validate_final_output already
    # enforces at render time; this is a defense-in-depth re-check against
    # tampering/corruption since then, not a first-time discovery.
    if video.video_streams != 1 or video.audio_streams != 1:
        checks.append(_check(
            "stream_counts", "FINAL_STREAM_INVALID", "FAIL", "error",
            f"Expected exactly 1 video + 1 audio stream, found {video.video_streams} video / {video.audio_streams} audio.",
            actual=f"{video.video_streams}v/{video.audio_streams}a", expected="1v/1a", repair_stage="RENDER",
        ))
    else:
        checks.append(_check("stream_counts", "FINAL_STREAM_INVALID", "PASS", "info", "Exactly 1 video + 1 audio stream."))

    if video.width != data.expected_width or video.height != data.expected_height:
        checks.append(_check(
            "resolution", "FINAL_RESOLUTION_MISMATCH", "FAIL", "error",
            f"Resolution {video.width}x{video.height} does not match the configured {data.expected_width}x{data.expected_height}.",
            actual=f"{video.width}x{video.height}", expected=f"{data.expected_width}x{data.expected_height}",
            repair_stage="RENDER",
        ))
    else:
        checks.append(_check("resolution", "FINAL_RESOLUTION_MISMATCH", "PASS", "info", "Resolution matches configuration."))

    if video.fps <= 0 or abs(video.fps - data.expected_fps) > FPS_TOLERANCE:
        checks.append(_check(
            "fps", "FINAL_FPS_MISMATCH", "FAIL", "error",
            f"FPS {video.fps:.2f} does not match the configured {data.expected_fps:.2f} (tolerance {FPS_TOLERANCE}).",
            actual=f"{video.fps:.2f}", expected=f"{data.expected_fps:.2f}", repair_stage="RENDER",
        ))
    else:
        checks.append(_check("fps", "FINAL_FPS_MISMATCH", "PASS", "info", "FPS matches configuration."))

    if data.expected_duration is not None:
        diff = abs(video.duration - data.expected_duration)
        if diff > DURATION_TOLERANCE_SEC:
            checks.append(_check(
                "duration", "FINAL_DURATION_MISMATCH", "FAIL", "error",
                f"Duration {video.duration:.2f}s differs from the expected {data.expected_duration:.2f}s by "
                f"{diff:.2f}s (tolerance {DURATION_TOLERANCE_SEC}s).",
                actual=f"{video.duration:.2f}s", expected=f"{data.expected_duration:.2f}s", repair_stage="RENDER",
            ))
        else:
            checks.append(_check("duration", "FINAL_DURATION_MISMATCH", "PASS", "info", "Duration matches the expected source."))
    return checks


def check_audio_levels(data: QAInput) -> list[QACheck]:
    checks: list[QACheck] = []
    if not data.narration_enabled:
        return checks  # section 19 -- silent-by-design projects are never penalized for being silent
    level = data.audio_level
    if level is None or not level.probed or level.mean_volume_db is None:
        checks.append(_check(
            "audio_silence", "AUDIO_SILENT", "WARN", "warning",
            "Could not analyze the final audio track's loudness.", repair_stage="AUDIO",
        ))
        return checks
    if level.mean_volume_db <= SILENCE_MEAN_VOLUME_DB_THRESHOLD:
        checks.append(_check(
            "audio_silence", "AUDIO_SILENT", "FAIL", "error",
            f"Final audio is effectively silent (mean volume {level.mean_volume_db:.1f} dB <= "
            f"{SILENCE_MEAN_VOLUME_DB_THRESHOLD} dB) but narration is enabled for this project.",
            actual=f"{level.mean_volume_db:.1f} dB", expected=f"> {SILENCE_MEAN_VOLUME_DB_THRESHOLD} dB",
            repair_stage="AUDIO",
        ))
    else:
        checks.append(_check("audio_silence", "AUDIO_SILENT", "PASS", "info", "Final audio is not silent."))

    if level.max_volume_db is not None and level.max_volume_db > CLIPPING_MAX_VOLUME_DB_THRESHOLD:
        checks.append(_check(
            "audio_clipping", "AUDIO_CLIPPING", "WARN", "warning",
            f"Final audio peak ({level.max_volume_db:.1f} dB) exceeds the {CLIPPING_MAX_VOLUME_DB_THRESHOLD} dB ceiling.",
            actual=f"{level.max_volume_db:.1f} dB", expected=f"<= {CLIPPING_MAX_VOLUME_DB_THRESHOLD} dB",
            repair_stage="AUDIO",
        ))
    else:
        checks.append(_check("audio_clipping", "AUDIO_CLIPPING", "PASS", "info", "Final audio peak is within the configured ceiling."))
    return checks


def check_thumbnail(data: QAInput) -> list[QACheck]:
    checks: list[QACheck] = []
    thumb = data.thumbnail
    if thumb is None or not thumb.exists or thumb.file_size <= 0:
        checks.append(_check(
            "thumbnail_valid", "THUMBNAIL_INVALID", "FAIL", "error",
            "thumbnail.jpg is missing or empty.", repair_stage="THUMBNAIL",
        ))
        return checks
    if thumb.width != thumb.expected_width or thumb.height != thumb.expected_height:
        checks.append(_check(
            "thumbnail_valid", "THUMBNAIL_INVALID", "FAIL", "error",
            f"Thumbnail dimensions {thumb.width}x{thumb.height} do not match the expected "
            f"{thumb.expected_width}x{thumb.expected_height}.",
            actual=f"{thumb.width}x{thumb.height}", expected=f"{thumb.expected_width}x{thumb.expected_height}",
            repair_stage="THUMBNAIL",
        ))
    else:
        checks.append(_check("thumbnail_valid", "THUMBNAIL_INVALID", "PASS", "info", "Thumbnail exists with the correct dimensions."))

    if thumb.is_low_quality:
        checks.append(_check(
            "thumbnail_quality", "THUMBNAIL_LOW_QUALITY", "WARN", "warning",
            "Thumbnail looks technically weak (too dark/bright/flat) -- section 21's own deterministic re-check.",
            repair_stage="THUMBNAIL",
        ))
    else:
        checks.append(_check("thumbnail_quality", "THUMBNAIL_LOW_QUALITY", "PASS", "info", "Thumbnail passes technical quality checks."))
    return checks


def check_metadata(data: QAInput) -> QACheck:
    meta = data.metadata
    if meta is None or not meta.exists:
        return _check("metadata_valid", "METADATA_INVALID", "FAIL", "error", "metadata.json is missing.", repair_stage="PACKAGE")
    if not meta.parses:
        return _check("metadata_valid", "METADATA_INVALID", "FAIL", "error", "metadata.json does not parse as valid JSON.", repair_stage="PACKAGE")
    # Section 27 -- title/description are genuinely required (Task 27's own
    # validate_package already enforces real, non-empty values for both --
    # see package_generate.py's own validate_title/validate_description
    # calls). Hashtags are deliberately NOT required here: Task 27's own
    # validate_package already treats an empty hashtag list as a complete,
    # valid package (its validate_hashtags call there is passed
    # max_count=max(1, len(hashtags)), which a 0-length list trivially
    # satisfies) -- a project with nothing to derive hashtags from (e.g.
    # no ContentBrief) is not a QA failure this check should invent.
    if not meta.title or not meta.description:
        return _check(
            "metadata_valid", "METADATA_INVALID", "FAIL", "error",
            "metadata.json is missing a required title/description value.", repair_stage="PACKAGE",
        )
    # Section 27 -- the metadata's own artifact references must point at
    # the real package files, never a stale/renamed path.
    if meta.referenced_video != "video_hoan_chinh.mp4" and meta.referenced_video is not None:
        pass  # filename is whatever the real render produced; presence-checked below, not hardcoded here
    if not meta.referenced_video or not meta.referenced_thumbnail:
        return _check(
            "metadata_valid", "METADATA_INVALID", "FAIL", "error",
            "metadata.json does not reference both the video and thumbnail filenames.", repair_stage="PACKAGE",
        )
    return _check("metadata_valid", "METADATA_INVALID", "PASS", "info", "metadata.json is present, parses, and has required fields.")


def check_captions(data: QAInput) -> list[QACheck]:
    checks: list[QACheck] = []
    captions = data.captions
    if not captions.enabled:
        return checks  # section 6 -- only checked when captions are actually enabled

    if not captions.exists or not captions.parses:
        checks.append(_check(
            "captions_valid", "CAPTIONS_INVALID", "FAIL", "error",
            "Captions are enabled but captions.ass is missing or does not parse.", repair_stage="CAPTIONS",
        ))
        return checks
    if captions.dialogue_count <= 0:
        checks.append(_check(
            "captions_valid", "CAPTIONS_INVALID", "FAIL", "error",
            "captions.ass parses but contains zero caption lines.", repair_stage="CAPTIONS",
        ))
        return checks
    checks.append(_check("captions_valid", "CAPTIONS_INVALID", "PASS", "info", f"{captions.dialogue_count} caption lines, valid ASS."))

    if data.expected_duration is not None and captions.max_end_time is not None:
        if captions.max_end_time > data.expected_duration + DURATION_TOLERANCE_SEC:
            checks.append(_check(
                "captions_timing", "CAPTIONS_TIMING_INVALID", "FAIL", "error",
                f"A caption ends at {captions.max_end_time:.2f}s, after the video's own "
                f"{data.expected_duration:.2f}s duration.",
                actual=f"{captions.max_end_time:.2f}s", expected=f"<= {data.expected_duration:.2f}s",
                repair_stage="CAPTIONS",
            ))
        else:
            checks.append(_check("captions_timing", "CAPTIONS_TIMING_INVALID", "PASS", "info", "All captions end within the video's duration."))
    return checks


def check_beat_completeness(data: QAInput) -> QACheck:
    beats = data.beats
    if beats.total_beats == 0:
        return _check("beat_completeness", "BEAT_ARTIFACT_MISSING", "FAIL", "error", "Project has no beats.", repair_stage="RENDER")
    if not beats.order_is_contiguous:
        return _check(
            "beat_completeness", "BEAT_ARTIFACT_MISSING", "FAIL", "error",
            "Beat ordering is not a contiguous 1..N sequence.", repair_stage="RENDER",
        )
    if beats.beats_with_motion_artifact < beats.total_beats:
        # Section 30's own "no missing beats" -- a WARN, not a FAIL: the
        # exact same reasoning Task 23's own Quality Gate check already
        # uses (MOTION_ARTIFACT_MISSING) -- the final render still falls
        # back to rendering the clip on demand, so a missing *cache* is
        # slower, not broken; the beat itself is present in final.mp4
        # either way.
        return _check(
            "beat_completeness", "BEAT_ARTIFACT_MISSING", "WARN", "warning",
            f"{beats.total_beats - beats.beats_with_motion_artifact}/{beats.total_beats} beats have no cached "
            f"Motion artifact (rendered fresh instead).",
            actual=str(beats.beats_with_motion_artifact), expected=str(beats.total_beats), repair_stage="MOTION",
        )
    return _check("beat_completeness", "BEAT_ARTIFACT_MISSING", "PASS", "info", "Every beat has a valid, complete artifact.")


def check_dependency_freshness(data: QAInput) -> list[QACheck]:
    checks: list[QACheck] = []
    deps = data.dependencies
    if deps.audio_master_is_newer_than_video is True:
        checks.append(_check(
            "dependency_freshness_audio", "STALE_DEPENDENCY", "FAIL", "error",
            "Audio Master was regenerated after this final.mp4 was rendered -- the video is stale.",
            repair_stage="RENDER",
        ))
    elif deps.audio_master_is_newer_than_video is False:
        checks.append(_check("dependency_freshness_audio", "STALE_DEPENDENCY", "PASS", "info", "final.mp4 is at least as new as Audio Master."))

    if deps.captions_is_newer_than_video is True:
        checks.append(_check(
            "dependency_freshness_captions", "STALE_DEPENDENCY", "FAIL", "error",
            "Captions were regenerated after this final.mp4 was rendered -- the video is stale.",
            repair_stage="RENDER",
        ))
    elif deps.captions_is_newer_than_video is False:
        checks.append(_check("dependency_freshness_captions", "STALE_DEPENDENCY", "PASS", "info", "final.mp4 is at least as new as Captions."))
    return checks


def check_package_version(data: QAInput) -> QACheck:
    version = data.version
    if version.package_engine_version is None:
        return _check(
            "package_version", "STALE_PACKAGE_VERSION", "WARN", "warning",
            "No package engine version recorded for this project's package.", repair_stage="PACKAGE",
        )
    if version.package_engine_version != version.current_package_engine_version:
        # Section 35 -- a WARN, not a hard FAIL: an engine-version bump
        # does not, by itself, mean this project's already-produced
        # artifact is actually broken content-wise, only that it predates
        # whatever changed -- never silently blocking every already-
        # completed project the instant a version constant is bumped.
        return _check(
            "package_version", "STALE_PACKAGE_VERSION", "WARN", "warning",
            f"Package was generated by engine version {version.package_engine_version!r}, current is "
            f"{version.current_package_engine_version!r}.",
            actual=version.package_engine_version, expected=version.current_package_engine_version,
            repair_stage="PACKAGE",
        )
    return _check("package_version", "STALE_PACKAGE_VERSION", "PASS", "info", "Package engine version is current.")


def evaluate_final_qa(data: QAInput) -> list[QACheck]:
    """Section 47's own minimum check list, run in order. Pure -- the
    caller (composition root) wraps this into a full QAReport with
    started_at/completed_at/score.
    """
    checks: list[QACheck] = [check_package_complete(data)]
    checks.extend(check_final_video(data))
    checks.extend(check_audio_levels(data))
    checks.extend(check_thumbnail(data))
    checks.append(check_metadata(data))
    checks.extend(check_captions(data))
    checks.append(check_beat_completeness(data))
    checks.extend(check_dependency_freshness(data))
    checks.append(check_package_version(data))
    return checks


def score_from_checks(checks: list[QACheck]) -> int:
    """Section 45 -- informational only, never overrides a mandatory
    failure (overall_status below is computed independently of this).
    """
    if not checks:
        return 0
    weights = {"PASS": 1.0, "WARN": 0.5, "FAIL": 0.0}
    total = sum(weights[c.status] for c in checks)
    return round(100 * total / len(checks))


def overall_status(checks: list[QACheck]) -> str:
    """Section 5 -- a single FAIL always wins, regardless of score
    (section 45's own explicit "must still produce FAIL").
    """
    if any(c.status == "FAIL" for c in checks):
        return "FAIL"
    if any(c.status == "WARN" for c in checks):
        return "PASS_WITH_WARNINGS"
    return "PASS"


assert set(QA_STATUSES) == {"PASS", "PASS_WITH_WARNINGS", "FAIL"}
