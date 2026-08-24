"""Structured error codes for the render pipeline (Task 10 hardening -- see
docs/features/37-e2e-pipeline-hardening.md). Not a new exception hierarchy:
existing app.core.exceptions types (ValidationError, FileOperationError,
...) are still what's raised and caught by app/main.py's handlers. These
codes are used two ways:

1. Preflight failures collect `(code, message)` pairs and fold them into a
   single ValidationError's message ("CODE: message; CODE: message"), so a
   preflight failure lists every problem at once instead of stopping at the
   first one, while still fitting this codebase's existing "one message
   string" exception convention.
2. A failed async render job classifies which phase it died in (tracked via
   VideoComposeJob.status at the moment of failure) into one of these codes
   for its `.render/job_<id>/report.json` -- see
   VideoComposerService._run_job's except block.
"""

PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
INVALID_BEAT_PLAN = "INVALID_BEAT_PLAN"
MISSING_ASSET = "MISSING_ASSET"
INVALID_MOTION = "INVALID_MOTION"
MISSING_AUDIO = "MISSING_AUDIO"
INVALID_CAPTION_CONFIG = "INVALID_CAPTION_CONFIG"
FFMPEG_NOT_FOUND = "FFMPEG_NOT_FOUND"
FFPROBE_NOT_FOUND = "FFPROBE_NOT_FOUND"
OUTPUT_DIR_NOT_WRITABLE = "OUTPUT_DIR_NOT_WRITABLE"
RENDER_FAILED = "RENDER_FAILED"
OUTPUT_VALIDATION_FAILED = "OUTPUT_VALIDATION_FAILED"
CAPTION_RENDER_FAILED = "CAPTION_RENDER_FAILED"
AUDIO_RENDER_FAILED = "AUDIO_RENDER_FAILED"
INSUFFICIENT_DISK_SPACE = "INSUFFICIENT_DISK_SPACE"
# A RUNNING job found on startup (Task 11 -- see
# docs/features/38-render-job-hardening.md) -- the process died mid-render,
# so this is not a real ffmpeg/validation failure, just an honest label for
# "we don't know if this would have succeeded."
RENDER_INTERRUPTED = "RENDER_INTERRUPTED"

# Task 26 (see docs/features/52-final-composer.md section 45) -- the Final
# Composer's own stable codes, for a VideoComposeJob whose `audio_master_path`
# is set (built entirely from already-produced Beat clips + Audio Master +
# Captions, never TTS/live mixing). FINAL_COMPOSITION_FAILED is this
# pipeline's phase-level default (PHASE_TO_ERROR_CODE["composing_final"]
# below); the rest are raised directly, embedded as a message prefix, the
# same way OUTPUT_VALIDATION_FAILED already is for "validating" -- see
# VideoComposerService._validate_final_output.
FINAL_COMPOSITION_FAILED = "FINAL_COMPOSITION_FAILED"
MISSING_BEAT_ARTIFACT = "MISSING_BEAT_ARTIFACT"
INVALID_BEAT_ARTIFACT = "INVALID_BEAT_ARTIFACT"
AUDIO_MASTER_MISSING = "AUDIO_MASTER_MISSING"
CAPTION_ARTIFACT_MISSING = "CAPTION_ARTIFACT_MISSING"
WATERMARK_ARTIFACT_MISSING = "WATERMARK_ARTIFACT_MISSING"
OUTRO_RENDER_FAILED = "OUTRO_RENDER_FAILED"
FINAL_OUTPUT_INVALID = "FINAL_OUTPUT_INVALID"
FINAL_DURATION_MISMATCH = "FINAL_DURATION_MISMATCH"
FINAL_STREAM_INVALID = "FINAL_STREAM_INVALID"
FINAL_ENCODING_FAILED = "FINAL_ENCODING_FAILED"

# Chinese Drama -> Vietnamese Shorts (VideoComposeJob.source_language set) --
# the new pre-narration ASR+translation phase's own code, covering both the
# "transcribing" and "translating" statuses (see PHASE_TO_ERROR_CODE below).
DUB_GENERATION_FAILED = "DUB_GENERATION_FAILED"

# Maps a VideoComposeJob.status value (the phase that was running when a job
# failed) to the error code its report.json should carry. "queued" has no
# entry -- a job can't fail before it starts running.
PHASE_TO_ERROR_CODE = {
    "transcribing": DUB_GENERATION_FAILED,
    "translating": DUB_GENERATION_FAILED,
    "rendering_beats": RENDER_FAILED,
    "merging": RENDER_FAILED,
    "narrating": AUDIO_RENDER_FAILED,
    "subtitling": CAPTION_RENDER_FAILED,
    "mixing_audio": AUDIO_RENDER_FAILED,
    "finalizing": CAPTION_RENDER_FAILED,
    "validating": OUTPUT_VALIDATION_FAILED,
    # Task 26 -- the Final Composer's own single one-pass phase.
    "composing_final": FINAL_COMPOSITION_FAILED,
}
