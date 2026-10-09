# Kênh văn học Việt Nam — prompt khởi tạo (bản đã sửa)

> Thư mục này **riêng cho kênh văn học** (không dùng chung nội dung với Biblical Figures hay kênh khác).
> Chỉ **máy dựng** là dùng chung: `content-prompts/vox_documentary_template/tools/episode_builder.py`, backend
> `app/modules/documentary`, Remotion theme `cinematic`, 5 cổng duyệt. Bản gốc của prompt này đã được review; các thay đổi
> chính: bỏ phong cách giấy cắt dán (đã loại), bỏ schema JSON thứ hai (dùng `spec.json`), làm theo giai đoạn, giữ cổng duyệt của người.
>
> Cách dùng: mở session mới, dán nguyên nội dung dưới dòng `---` làm yêu cầu.

---

# TASK (PHASE A): Vietnamese literature channel — editorial + visual template and the pilot episode spec

## 0. Read first, do not duplicate
Read `content-prompts/vox_documentary_template/HANDOFF.md`, `RULES.md`, `IMAGE_STYLE.md`, `README.md`, and one example spec.
That system already exists: sources/claims with verbatim excerpts, a 7-section script (hook, context, timeline, evidence,
turning_point, consequences, conclusion), storyboard, manual AI-image loop via CSV, `edge-tts` voice, 5 human approval gates,
Remotion `cinematic` theme, export bundle. **Extend it; do not build a parallel pipeline, schema, or renderer.**
Create all new files under `content-prompts/literature_vi/` only. Do not change files of other channels.
Reply to the user in Vietnamese. Never approve a gate, never call a paid API, never start a full render, never generate
more than the images needed to test one prompt (and only on request).

## 1. Channel positioning (`CHANNEL.md`)
Vietnamese literature told as character-centred cinematic storytelling plus analysis, for viewers who have not read the work
(students, adults interested in psychology and society). Not a school lecture and not a copy of "soạn bài"/study-guide text.
Include: mission and audience; content pillars (50% human stories and tragedies, 30% themes/psychology/society, 20% contemporary
reading; treated as hypotheses); editorial principles (accuracy before drama; evidence before interpretation; interpretation
labelled as interpretation; opinions need reasoning; no invented quotations; no invented scenes presented as canon; characters not
reduced to hero/villain); retention (hook, tension, visual reveals, analytical ending, no misleading clickbait); title and
thumbnail formulas (character-centred, psychological question, social dilemma, contemporary reading; never promise facts the
work does not contain); quality bar (research, script review, original commentary, audio clarity, subtitles, licensing, final QA).
**Original commentary is mandatory**: each episode needs a creator viewpoint section written or approved by the channel owner
(placeholder the owner fills), because that is what makes the channel more than a retelling.

## 2. Visual direction (`VISUAL.md`)
Decision already made: use the existing **`cinematic`** theme (full-bleed images, dark parchment data cards, gold serif text).
The paper-collage look was rejected by the owner. Do **not** design layered cut-out/parallax characters; that would need a new
Remotion preset and transparent-PNG workflow and is out of scope for Phase A (list it under "future option" only).
Define an original channel look on top of cinematic: base palette, accent rule, which scene types use full-bleed images vs
data cards (HeadlineImpact for key lines, EvidenceBoard for textual evidence/quotes with citation, ArchivalPortrait for real
period images, BigNumber/Timeline only if the story has them), typography already in the theme, on-screen labels ("Minh họa AI").
Image style for rural Vietnam of the 1930s (propose and justify one: e.g. muted gouache/ink-wash illustration or aged
sepia painting; **not** the Baroque style of Biblical Figures). Include: character reference sheet workflow (name, age if the
work states it, face/silhouette, clothing, props, emotional range, continuity rules; mark any look the work does not state as a
creative interpretation); scene patterns (establishing, portrait, interaction, flashback, symbolic, analysis, turning point,
ending); asset reuse/naming/licence recording (reuse the project image pool idea); and a populatable image-prompt template
(work+scene, character ref, action, emotion, composition, style, palette, lighting, framing, 16:9, continuity, negatives:
no text/letters/watermark/frame). Images are made by the user from a CSV; never wire an image API.

## 3. Script template (`SCRIPT_TEMPLATE.md`)
6–9 minute Vietnamese episode. Map the flexible beats to the system's 7 section kinds:
hook→hook; context and character background→context; main conflict and analysis→evidence; turning point→turning_point;
climax and consequences→consequences; personal commentary + closing reflection→conclusion (two paragraphs groups).
Per scene record: scene id (S###, assigned by the tool), narrative purpose, narration, **narration mode**, source facts or
textual evidence, emotional intent, visual description, on-screen text, sound idea, transition, commentary status.
Narration modes and how each is stored in the existing spec:
- **FACT / NARRATOR** (events of the work, analysis grounded in the text): `factual=true`, cites a claim whose source is the
  verbatim excerpt of the work.
- **CHARACTER POV** (creative inner voice): `factual=false`; must never be presented as Nam Cao's words; no quotation marks implying a quote.
- **CREATOR COMMENTARY** (the owner's viewpoint): `factual=false`; states reasoning and points to evidence from the text.
Rules: natural spoken Vietnamese, concrete actions over slogans, years as 4 digits, no formulaic moral ("bài học rút ra"),
no melodrama the text does not support, no fabricated quotes. Include a four-way distinction in the notes: facts from the work,
reliable context, interpretation, connective narration. Include the final review checklist (accuracy, coherence, hook,
analysis, original commentary, natural Vietnamese, unsupported claims, quotation/licence, duration from real audio).
If a field the app cannot store is needed (e.g. a `mode` label), do **not** invent backend behaviour: record it as a naming
convention in the script notes and list the small backend change as a proposal.

## 4. Mapping instead of a new schema (`MAPPING.md`)
Do not create `BEATS_SCHEMA.json`. Write a table mapping every desired beat field (beat_id, sequence, narrative_function,
narration_mode, narration_text, estimated vs actual duration, source_notes, interpretation_notes, character_ids, visual_prompt,
asset ids, composition, camera_motion, on_screen_text, sound_design, transition, verification_status) to where it already lives
(spec.json sources/claims/script/scene_overrides/images, storyboard scene fields, timeline = actual timing from audio) or
mark it "not supported; proposal". Estimated timing must stay distinct from audio-derived timing, as in the system.

## 5. Pilot: `episodes/chi-pheo-ep01/`
Working title: "Chí Phèo: Khi một người không còn được phép làm người lương thiện". Central question (a hypothesis, not a
conclusion): why does Chí Phèo's wish to return to an ordinary humane life become a tragedy?
Deliverables: episode objective; audience; thesis/interpretive angle (acknowledge an alternative reading); research and
verification checklist; character reference requirements; thumbnail concept; **`spec.json` in the existing spec format**
(sources with `fetch` from the story's text, claims, script of 7 sections with modes as above, scene_overrides for data cards,
image list left for the user), a readable `script.md`, key-scene image prompts (at most 8), sound suggestions, closing
audience question, Shorts ideas, QC checklist.
Source rule: the story text must come from a real source (Vietnamese Wikisource; Nam Cao d. 1951, public domain). Extend
`episode_builder.py` minimally so `fetch` can take `{"kind":"wikisource","lang":"vi",...}` and verify that every quotation is
cut from the fetched text. If the text cannot be fetched, **write no quotations** and list what still needs verification.
Treat Chí Phèo, Bá Kiến and Thị Nở with complexity; no school-essay structure; no invented canonical scenes.

## 6. Validation and report
Run `python content-prompts/vox_documentary_template/tools/episode_builder.py create ...` only against a backend started from a
scratch directory (see HANDOFF "Bẫy đã gặp") or stop at the spec and say it was not run. Validate the JSON with Python. Report
created/modified files, commands actually run with results, assumptions, unverified literary details, remaining manual work
(owner commentary, art-style choice, images from CSV, gate approvals), and how to start episode 2 from this folder.
Add a short `docs/features/NNN-*.md` and one line in `docs/README.md`.
