"""YouTube Publishing module -- see docs/features/127-youtube-publishing.md.

Connect one or more YouTube channels via Google OAuth and upload a
finished Factory video (final.mp4 + metadata.json + thumbnail.jpg) to a
chosen channel. Its own two tables, no FK into any other app/modules/*
table (per app/modules/README.md). The one composition root allowed to
bridge this module with app.modules.beat / app.modules.video_composer is
app/api/v1/endpoints/publish_video.py.

Reality check (documented in the feature doc, surfaced in the UI): an
un-audited Google OAuth project has every uploaded video LOCKED to
`private` by YouTube regardless of the requested privacy, and a consent
screen left in "Testing" issues refresh tokens that expire after 7 days.
This module still saves the whole file-transfer + metadata + thumbnail
step; the user flips the video to public in YouTube Studio (or, once their
OAuth app is verified, requests `public`/scheduled directly).
"""
