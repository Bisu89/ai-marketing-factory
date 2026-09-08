import { useState } from "react";
import { Check, Copy, Loader2, X } from "lucide-react";
import { importStoryPackage } from "../api/story";
import type { StoryImportResult } from "../api/story";
import "./StudioPage.css";

// The prompt to paste into ChatGPT (Go / Plus -- a flat subscription, no
// per-token API charge) so it returns exactly the JSON the importer wants.
export const CHATGPT_PROMPT = `You are a story development editor + storyboard artist for an AUDIO-FIRST short video.
I will give you a logline. Produce the complete plan as a SINGLE JSON object
and NOTHING ELSE (no prose, no markdown fences). Match this schema exactly:

{
  "story_bible": {
    "premise": "one sentence",
    "synopsis": "3-5 sentences",
    "central_conflict": "one sentence",
    "tone": "e.g. tense, nocturnal",
    "setting_summary": "one sentence",
    "themes": ["...", "..."],
    "world_rules": ["...", "..."],
    "timeline": ["beat 1", "beat 2", "beat 3"]
  },
  "style_bible": {
    "palette": "e.g. ash and ember",
    "lighting": "e.g. torch and moonlight",
    "mood": "e.g. grim",
    "visual_references": ["...", "..."]
  },
  "characters": [
    {
      "name": "Mara",
      "role": "courier",
      "age": "20s",
      "gender": "female",
      "appearance": "short description",
      "wardrobe": "short description",
      "personality": "short description",
      "canonical_prompt_block": "ONE dense visual sentence: face, hair, build, wardrobe. This exact text is reused in every image prompt so the character never changes. Keep it under 40 words and purely visual.",
      "negative_constraints": "e.g. no armor, no modern items"
    }
  ],
  "locations": [
    { "name": "The Low Gate", "description": "short", "mood": "claustrophobic" }
  ],
  "chapters": [
    {
      "title": "The Order",
      "summary": "1-2 sentences",
      "goal": "the dramatic goal of this chapter",
      "retention_notes": "why the viewer keeps watching",
      "scenes": [
        {
          "scene_type": "one of: HOOK, SETUP, BUILD, REVEAL, CLIMAX, TWIST, REACTION, CONFRONTATION, TRANSITION, ENDING, BODY",
          "narration": "ONE spoken paragraph -- what the narrator says over this scene",
          "dialogue": [ { "character_name": "Mara", "line": "Move!" } ],
          "character_names": ["Mara"],
          "location_name": "The Low Gate",
          "camera": "e.g. tracking shot, close, wide",
          "emotion": "the dominant emotion",
          "time_of_day": "e.g. night",
          "duration_hint": 7,
          "image_prompt": "optional: an explicit 'what appears on screen' description"
        }
      ]
    }
  ]
}

Rules:
- 3-6 chapters, 4-10 scenes per chapter, 30-60 scenes total.
- CHAPTER 1, SCENE 1 is the HOOK (scene_type "HOOK"): open on the single
  most striking image or the highest-stakes moment, and plant a question
  the viewer must keep watching to answer. First sentence must land in
  under 4 seconds. NEVER open with "In this video", "Today we look at",
  "Have you ever wondered", or any slow throat-clearing.
- The LAST scene (scene_type "ENDING") resolves the question and lands one
  closing thought -- no "thanks for watching" (the outro handles that).
- Every character_name / location_name in a scene MUST match a name defined
  in "characters" / "locations" exactly.
- duration_hint is seconds per scene, 3-12.
- Physical on-screen MOVEMENT (running, fighting, a chase) belongs in the
  narration wording -- that is what earns a scene a video clip later.
- Output the JSON object only.

LOGLINE: `;

export function StudioImportModal({
  storyId,
  hasContent,
  onClose,
  onImported,
}: {
  storyId: number;
  hasContent: boolean;
  onClose: () => void;
  onImported: (result: StoryImportResult) => void;
}) {
  const [text, setText] = useState("");
  const [replace, setReplace] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(CHATGPT_PROMPT);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setError("Could not copy to clipboard — select the prompt text manually.");
    }
  }

  async function handleImport() {
    if (busy) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      setError("That is not valid JSON. Paste the whole object ChatGPT returned, starting with { and ending with }.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onImported(await importStoryPackage(storyId, parsed, replace));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="studio-modal-backdrop" onClick={onClose}>
      <div className="studio-modal studio-modal--wide" onClick={(e) => e.stopPropagation()}>
        <div className="studio-modal-header">
          <h3>Import a written story</h3>
          <button className="btn btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <p className="studio-meta-dim">
          Skip the AI planning pipeline: write the story in ChatGPT (a flat subscription — no API cost), then paste
          the JSON here. The Scene Director + cost + Produce steps are unchanged.
        </p>

        <div className="studio-import-step">
          <button className="btn btn-secondary" onClick={copyPrompt}>
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "Copied" : "Copy the ChatGPT prompt"}
          </button>
          <span className="studio-meta-dim">Paste it into ChatGPT, add your logline after it, send.</span>
        </div>

        <label className="studio-field">
          <span>Paste ChatGPT's JSON response</span>
          <textarea
            rows={12}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={'{\n  "story_bible": { ... },\n  "characters": [ ... ],\n  "chapters": [ ... ]\n}'}
            spellCheck={false}
          />
        </label>

        {hasContent && (
          <label className="studio-import-replace">
            <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
            <span>This story already has chapters/characters — replace them</span>
          </label>
        )}

        {error && <div className="studio-alert studio-alert-error">{error}</div>}

        <div className="studio-modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleImport} disabled={busy || !text.trim()}>
            {busy ? <Loader2 size={14} className="spin" /> : null}
            Import
          </button>
        </div>
      </div>
    </div>
  );
}
