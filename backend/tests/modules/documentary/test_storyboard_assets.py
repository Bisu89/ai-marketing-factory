"""Documentary storyboard + asset registry + manual image loop (feature 165)."""

import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ValidationError
from app.db.base import Base
from app.modules.documentary import assets as assets_mod
from app.modules.documentary.assets import AssetService, asset_state
from app.modules.documentary.research import ResearchService
from app.modules.documentary.schemas import (
    SECTION_ORDER,
    ClaimIn,
    ProjectCreate,
    ScriptParagraph,
    ScriptSave,
    ScriptSection,
    SourceIn,
)
from app.modules.documentary.service import DocumentaryService
from app.modules.documentary.storyboard import (
    PlannedScene,
    StoryboardPolicy,
    StoryboardService,
    classify,
    plan_units,
)

POLICY = StoryboardPolicy()


def sentences(prefix: str, n: int) -> str:
    return " ".join(f"{prefix} câu số {k} của đoạn này kể về một sự kiện lịch sử quan trọng." for k in range(1, n + 1))


def section(kind: str, *texts: str, claim_id: int | None = None) -> ScriptSection:
    return ScriptSection(
        kind=kind,
        heading=kind,
        paragraphs=[ScriptParagraph(text=t, claim_ids=[claim_id] if claim_id else [], factual=bool(claim_id)) for t in texts],
    )


class UnitPlanningTests(unittest.TestCase):
    def test_splits_on_sentence_boundaries_not_fixed_length(self):
        units = plan_units([section("context", sentences("A", 6))], POLICY)
        self.assertEqual(len(units), 3)
        for u in units:
            self.assertTrue(u.text.endswith("."))
            self.assertLessEqual(len(u.text.split()), POLICY.max_scene_words)

    def test_tiny_transition_paragraph_is_folded_into_next(self):
        units = plan_units([section("hook", "Mở đầu ngắn.", sentences("B", 2))], POLICY)
        self.assertNotIn("Mở đầu ngắn.", [u.text for u in units])  # no scene of its own
        self.assertTrue(units[0].text.startswith("Mở đầu ngắn."))

    def test_one_long_sentence_is_kept_whole(self):
        long = " ".join(["từ"] * 80) + "."
        units = plan_units([section("context", long)], POLICY)
        self.assertEqual(len(units), 1)

    def test_order_follows_script(self):
        units = plan_units(
            [section("hook", sentences("H", 2)), section("context", sentences("C", 2))], POLICY
        )
        self.assertEqual([u.section_kind for u in units], ["hook", "context"])


class ClassifyTests(unittest.TestCase):
    def c(self, kind, text):
        return classify(PlannedScene(kind, "p", text), POLICY)

    def test_rules(self):
        self.assertEqual(self.c("timeline", "Sự việc diễn ra lần lượt."), ("TimelineBuild", "programmatic"))
        self.assertEqual(self.c("context", "Năm 1453 rồi năm 1492 mọi thứ đổi khác."), ("TimelineBuild", "programmatic"))
        self.assertEqual(self.c("consequences", "Hơn 3.000 người đã thiệt mạng."), ("BigNumber", "programmatic"))
        self.assertEqual(self.c("context", "Theo bản đồ cổ, con tàu đi về phía bắc."), ("MapZoom", "programmatic"))
        self.assertEqual(self.c("evidence", "Có hai cách giải thích."), ("EvidenceBoard", "programmatic"))
        self.assertEqual(self.c("context", "Ông ngồi một mình bên cửa sổ."), ("PhotoKenBurns", "image"))

    def test_ai_video_is_never_a_strategy(self):
        self.assertFalse(POLICY.allow_ai_video)
        for kind in SECTION_ORDER:
            self.assertIn(self.c(kind, "Một câu bất kỳ.")[1], ("programmatic", "image"))


class _Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "lib"
        self.engine = create_engine(
            f"sqlite:///{Path(self.tmp.name) / 't.db'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(
            bind=self.engine, tables=[t for n, t in Base.metadata.tables.items() if n.startswith("documentary_")]
        )
        self.db = sessionmaker(bind=self.engine)()
        self.svc = DocumentaryService(self.db, library_root=self.root)
        self.assets = AssetService(self.db, self.root)
        self.board = StoryboardService(self.db)
        self.p = self.svc.create(ProjectCreate(title="T", topic="t"))
        r = ResearchService(self.db)
        src = r.add_source(self.p.id, SourceIn(title="S"))
        self.claim = r.add_claim(self.p.id, ClaimIn(text="C", status="verified", source_ids=[src.id])).id

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        try:
            self.tmp.cleanup()
        except PermissionError:  # known Windows SQLite tmpdir race
            pass

    def png(self, name="a.png", color=(10, 20, 30), size=(16, 9)) -> Path:
        f = Path(self.tmp.name) / name
        Image.new("RGB", size, color).save(f)
        return f

    def script(self, hook_text: str, context_text: str | None = None):
        """All seven sections; `hook_text` / `context_text` are the variable parts."""
        sections = []
        for kind in SECTION_ORDER:
            text = {"hook": hook_text, "context": context_text or sentences("Ngữ cảnh", 2)}.get(
                kind, sentences(kind.capitalize(), 2)
            )
            sections.append(section(kind, text, claim_id=self.claim))
        self.svc.save_script(self.p.id, ScriptSave(sections=sections), "manual")

    def approve_script(self):
        self.svc.advance(self.p.id)
        self.svc.approve(self.p.id, "research")
        self.svc.advance(self.p.id)
        self.svc.approve(self.p.id, "script")

    def ready(self, hook_text=None, context_text=None):
        self.script(hook_text or sentences("Mở", 2), context_text)
        self.approve_script()
        return self.svc.plan_storyboard(self.p.id)


class PlanTests(_Case):
    def test_plan_requires_approved_script(self):
        self.script(sentences("Mở", 2))
        with self.assertRaises(ValidationError):
            self.svc.plan_storyboard(self.p.id)

    def test_plan_creates_ordered_scenes_with_stable_keys(self):
        info = self.ready()
        scenes = self.board.list(self.p.id)
        self.assertEqual(info["scenes"], len(scenes))
        self.assertEqual([s.scene_key for s in scenes], [f"S{i:03d}" for i in range(1, len(scenes) + 1)])
        self.assertEqual([s.order_index for s in scenes], list(range(1, len(scenes) + 1)))
        self.assertTrue(all(s.expected_duration > 0 and s.actual_duration is None for s in scenes))

    def test_replan_unchanged_script_is_a_noop(self):
        self.ready()
        before = [(s.id, s.scene_key) for s in self.board.list(self.p.id)]
        v = self.svc.get(self.p.id).storyboard_version
        info = self.svc.plan_storyboard(self.p.id)
        self.assertEqual((info["created"], info["removed"]), (0, 0))
        self.assertEqual([(s.id, s.scene_key) for s in self.board.list(self.p.id)], before)
        self.assertEqual(self.svc.get(self.p.id).storyboard_version, v)  # approvals not needlessly invalidated

    def test_changing_one_paragraph_keeps_other_scenes_and_their_assets(self):
        self.ready()
        # give every image group an approved asset
        for n, head in enumerate(self.assets.needing_images(self.p.id)):
            a, _ = self.assets.import_file(self.p.id, self.png(f"i{n}.png", (n, n, n)))
            self.assets.approve(self.p.id, a.id)
            self.assets.assign(self.p.id, head.id, a.id)
        before = {s.narration_hash: (s.scene_key, s.asset_id) for s in self.board.list(self.p.id)}
        # edit only the hook; context text stays identical to the first run
        self.script(sentences("Mở đầu MỚI", 2), sentences("Ngữ cảnh", 2))
        self.assertEqual(self.svc.get(self.p.id).state, "script_review")  # saving revoked the old approval
        self.svc.approve(self.p.id, "script")
        info = self.svc.plan_storyboard(self.p.id)
        self.assertGreater(info["created"], 0)
        self.assertGreater(info["kept"], 0)
        after = {s.narration_hash: (s.scene_key, s.asset_id) for s in self.board.list(self.p.id)}
        unchanged = set(before) & set(after)
        self.assertTrue(unchanged)
        for h in unchanged:
            self.assertEqual(before[h], after[h])  # same key AND same asset: nothing to regenerate
        new_keys = {k for h, (k, _) in after.items() if h not in before}
        old_keys = {k for k, _ in before.values()}
        self.assertFalse(new_keys & old_keys)  # keys are never reused

    def test_image_scenes_in_one_paragraph_share_groups_of_three(self):
        self.ready(hook_text=sentences("Mở", 12))  # 12 sentences -> several scenes in one paragraph
        hook = [s for s in self.board.list(self.p.id) if s.section_kind == "hook"]
        self.assertGreater(len(hook), 3)
        groups = {}
        for s in hook:
            groups.setdefault(s.image_group, []).append(s)
        self.assertTrue(all(len(v) <= 3 for v in groups.values()))
        self.assertLess(len(groups), len(hook))

    def test_programmatic_scenes_need_no_image(self):
        self.ready()
        scenes = self.board.list(self.p.id)
        prog = [s for s in scenes if s.asset_strategy == "programmatic"]
        self.assertTrue(prog)
        self.assertTrue(all(asset_state(s, None) == "programmatic" and s.image_group is None for s in prog))


class AssetTests(_Case):
    def test_import_validates_type_and_content(self):
        bad = Path(self.tmp.name) / "x.txt"
        bad.write_text("hi")
        with self.assertRaises(ValidationError):
            self.assets.import_file(self.p.id, bad)
        fake = Path(self.tmp.name) / "fake.png"
        fake.write_text("not really a png")
        with self.assertRaises(ValidationError):
            self.assets.import_file(self.p.id, fake)
        with self.assertRaises(ValidationError):
            self.assets.import_file(self.p.id, Path(self.tmp.name) / "nope.png")

    def test_size_limit(self):
        f = self.png()
        with patch.object(assets_mod, "MAX_IMAGE_BYTES", 10):
            with self.assertRaises(ValidationError):
                self.assets.import_file(self.p.id, f)

    def test_dedupe_by_content_hash_and_generated_filename(self):
        a, created = self.assets.import_file(self.p.id, self.png("one.png"))
        b, created2 = self.assets.import_file(self.p.id, self.png("copy.png"))
        self.assertTrue(created)
        self.assertFalse(created2)
        self.assertEqual(a.id, b.id)
        self.assertNotIn("one", Path(a.path).name)  # user-supplied name never reaches the filesystem path
        self.assertTrue(Path(a.path).is_file())

    def test_archival_needs_license_and_attribution_before_approval(self):
        a, _ = self.assets.import_file(self.p.id, self.png(), origin="archival")
        with self.assertRaises(ValidationError):
            self.assets.approve(self.p.id, a.id)
        self.assets.update_metadata(self.p.id, a.id, {"license": "unknown", "attribution": "Thư viện X"})
        with self.assertRaises(ValidationError):
            self.assets.approve(self.p.id, a.id)
        self.assets.update_metadata(self.p.id, a.id, {"license": "Public domain", "attribution": ""})
        with self.assertRaises(ValidationError):
            self.assets.approve(self.p.id, a.id)
        self.assets.update_metadata(self.p.id, a.id, {"attribution": "Thư viện X"})
        self.assertEqual(self.assets.approve(self.p.id, a.id).approval_status, "approved")

    def test_editing_metadata_resets_approval(self):
        a, _ = self.assets.import_file(self.p.id, self.png())
        self.assets.approve(self.p.id, a.id)
        self.assertEqual(self.assets.update_metadata(self.p.id, a.id, {"tags": ["x"]}).approval_status, "pending")

    def test_cannot_assign_asset_to_programmatic_scene(self):
        self.ready()
        prog = next(s for s in self.board.list(self.p.id) if s.asset_strategy == "programmatic")
        a, _ = self.assets.import_file(self.p.id, self.png())
        with self.assertRaises(ValidationError):
            self.assets.assign(self.p.id, prog.id, a.id)

    def test_assign_applies_to_whole_group_and_replace_is_independent(self):
        self.ready(hook_text=sentences("Mở", 12))
        hook = [s for s in self.board.list(self.p.id) if s.section_kind == "hook"]
        head = next(s for s in hook if s.image_group == s.scene_key)
        other_head = next(s for s in self.board.list(self.p.id) if s.image_group and s.image_group != head.image_group)
        a1, _ = self.assets.import_file(self.p.id, self.png("1.png", (1, 1, 1)))
        a2, _ = self.assets.import_file(self.p.id, self.png("2.png", (2, 2, 2)))
        self.assets.assign(self.p.id, other_head.id, a2.id)
        group = self.assets.assign(self.p.id, head.id, a1.id)
        self.assertTrue(all(s.asset_id == a1.id for s in group))
        self.assertGreater(len(group), 1)
        # replacing the first group's image leaves the other group alone
        self.assets.assign(self.p.id, head.id, a2.id)
        self.db.refresh(other_head)
        self.assertEqual(other_head.asset_id, a2.id)


class ManualLoopTests(_Case):
    def rows(self, text: str):
        return list(csv.reader(io.StringIO(text.lstrip("﻿"))))

    def test_csv_lists_only_image_groups_missing_an_asset(self):
        self.ready()
        text, info = self.assets.export_csv(self.p.id)
        rows = self.rows(text)
        self.assertTrue(text.startswith("﻿"))
        self.assertEqual(rows[0][0], "STT")
        heads = self.assets.needing_images(self.p.id)
        self.assertEqual(len(rows) - 1, len(heads))
        self.assertEqual(info["to_generate"], len(heads))
        names = [r[1] for r in rows[1:]]
        self.assertEqual(names, [f"{h.scene_key}_{h.section_kind}.png" for h in heads])
        prog = {s.scene_key for s in self.board.list(self.p.id) if s.asset_strategy == "programmatic"}
        self.assertFalse(any(n.split("_")[0] in prog for n in names))

    def test_import_folder_matches_by_scene_key_and_rest_is_reported(self):
        self.ready()
        heads = self.assets.needing_images(self.p.id)
        folder = Path(self.tmp.name) / "gen"
        folder.mkdir()
        h0 = heads[0]
        Image.new("RGB", (32, 18), (9, 9, 9)).save(folder / f"{h0.scene_key}_whatever.png")
        Image.new("RGB", (32, 18), (8, 8, 8)).save(folder / "random_name.png")
        (folder / "notes.txt").write_text("ignored")
        report = self.assets.import_folder(self.p.id, folder)
        self.assertEqual(len(report["imported"]), 1)
        self.assertEqual(report["unmatched"], ["random_name.png"])
        self.db.refresh(h0)
        a = self.assets.get(self.p.id, h0.asset_id)
        self.assertEqual((a.origin, a.approval_status, a.input_hash), ("ai_manual", "pending", h0.input_hash))
        self.assertEqual(a.prompt, h0.visual_objective)
        # re-running the same folder creates nothing new
        again = self.assets.import_folder(self.p.id, folder)
        self.assertEqual((len(again["imported"]), len(again["duplicate"])), (0, 1))

    def test_approved_asset_with_same_input_hash_is_reused_not_requested_again(self):
        self.ready()
        heads = self.assets.needing_images(self.p.id)
        h0 = heads[0]
        a, _ = self.assets.import_file(
            self.p.id, self.png("z.png"), origin="ai_manual", input_hash=h0.input_hash, prompt=h0.visual_objective
        )
        self.assets.approve(self.p.id, a.id)
        text, info = self.assets.export_csv(self.p.id)
        self.assertEqual(info["reused_from_cache"], 1)
        self.assertEqual(info["to_generate"], len(heads) - 1)
        self.db.refresh(h0)
        self.assertEqual(h0.asset_id, a.id)
        self.assertNotIn(f"{h0.scene_key}_", text)

    def test_editing_a_scene_marks_only_its_image_stale(self):
        self.ready()
        heads = self.assets.needing_images(self.p.id)
        for n, h in enumerate(heads):
            a, _ = self.assets.import_file(
                self.p.id, self.png(f"s{n}.png", (n, 1, 1)), origin="ai_manual", input_hash=h.input_hash
            )
            self.assets.approve(self.p.id, a.id)
            self.assets.assign(self.p.id, h.id, a.id)
        self.assertEqual(self.assets.needing_images(self.p.id), [])
        target = heads[0]
        self.board.update(self.p.id, target.id, {"visual_objective": "Một mô tả hoàn toàn khác."})
        need = self.assets.needing_images(self.p.id)
        self.assertEqual([s.scene_key for s in need], [target.scene_key])  # only that one is asked for again
        issues = {i.message for i in self.assets.review(self.p.id)}
        self.assertTrue(any(target.scene_key in m and "mô tả" in m for m in issues))

    def test_gate_three_needs_every_scene_resolved_and_approved(self):
        self.ready()
        self.svc.advance(self.p.id)  # storyboard_review
        self.svc.advance(self.p.id)  # asset_generation
        self.svc.advance(self.p.id)  # asset_review
        with self.assertRaises(ValidationError):
            self.svc.approve(self.p.id, "storyboard_assets")
        for n, h in enumerate(self.assets.needing_images(self.p.id)):
            a, _ = self.assets.import_file(self.p.id, self.png(f"g{n}.png", (n, 2, 2)))
            self.assets.assign(self.p.id, h.id, a.id)
        self.assertTrue(any(i.code == "asset_pending" for i in self.assets.review(self.p.id)))
        for a in self.assets.list(self.p.id):
            self.assets.approve(self.p.id, a.id)
        self.assertEqual(self.assets.review(self.p.id), [])
        self.svc.approve(self.p.id, "storyboard_assets")

    def test_replacing_asset_after_gate_three_invalidates_it(self):
        self.ready()
        for _ in range(3):
            self.svc.advance(self.p.id)
        for n, h in enumerate(self.assets.needing_images(self.p.id)):
            a, _ = self.assets.import_file(self.p.id, self.png(f"r{n}.png", (n, 3, 3)))
            self.assets.approve(self.p.id, a.id)
            self.assets.assign(self.p.id, h.id, a.id)
        self.svc.approve(self.p.id, "storyboard_assets")
        gate = next(g for g in self.svc.gate_statuses(self.svc.get(self.p.id)) if g.gate == "storyboard_assets")
        self.assertEqual(gate.status, "approved")
        head = next(s for s in self.board.list(self.p.id) if s.image_group == s.scene_key)
        new, _ = self.assets.import_file(self.p.id, self.png("new.png", (99, 99, 99)))
        self.assets.assign(self.p.id, head.id, new.id)
        self.svc.storyboard_changed(self.p.id)
        gate = next(g for g in self.svc.gate_statuses(self.svc.get(self.p.id)) if g.gate == "storyboard_assets")
        self.assertNotEqual(gate.status, "approved")  # a swapped image is never covered by the old approval

    def test_same_file_used_by_two_groups_is_not_falsely_stale(self):
        """Regression: identical bytes assigned to two groups with different
        prompts used to flag the second as stale (staleness lives on the
        assignment, not on the asset)."""
        self.ready()
        h1, h2 = self.assets.needing_images(self.p.id)[:2]
        a, _ = self.assets.import_file(self.p.id, self.png(), origin="ai_manual", input_hash=h1.input_hash)
        self.assets.assign(self.p.id, h1.id, a.id)
        self.assets.assign(self.p.id, h2.id, a.id)
        self.db.refresh(h2)
        self.assertEqual(asset_state(h2, a), "pending")

    def test_editing_a_follower_gives_it_its_own_image_request(self):
        self.ready(hook_text=sentences("Mở", 12))
        hook = [s for s in self.board.list(self.p.id) if s.section_kind == "hook"]
        head = next(s for s in hook if s.image_group == s.scene_key and sum(1 for x in hook if x.image_group == s.scene_key) > 1)
        follower = next(s for s in hook if s.image_group == head.scene_key and s.id != head.id)
        a, _ = self.assets.import_file(self.p.id, self.png(), origin="ai_manual", input_hash=head.input_hash)
        self.assets.assign(self.p.id, head.id, a.id)
        self.board.update(self.p.id, follower.id, {"visual_objective": "Cảnh riêng với mô tả riêng."})
        self.db.refresh(head)
        self.assertEqual(follower.image_group, follower.scene_key)
        self.assertIn(follower.scene_key, [s.scene_key for s in self.assets.needing_images(self.p.id)])
        self.assertNotIn(head.scene_key, [s.scene_key for s in self.assets.needing_images(self.p.id)])

    def test_missing_folder(self):
        with self.assertRaises(ValidationError):
            self.assets.import_folder(self.p.id, Path(self.tmp.name) / "nope")


if __name__ == "__main__":
    unittest.main()
