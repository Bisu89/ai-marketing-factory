"""Viral Source Radar -- one search box, every platform searched in parallel,
rule-based (no-AI) viral scoring, and rights-aware download gating.

Phase 1 scope: Reddit + YouTube engines, deterministic keyword expansion,
local viral score, dedup, and a Save-to-Library action. TikTok / Instagram
have no compliant public keyword-search API for a distributed desktop app,
so their engines are honest "unavailable" stubs (see engines/tiktok.py).

This module owns its own tables (discovery_search / discovery_result) and
must never import app.modules.beat / app.modules.batch / app.modules.ai --
turning a discovered source into content is a job for a future composition
root, not this module.
"""
