"""Documentary workflow: state machine rules + approval gates (feature 163)."""

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import Base
from app.modules.documentary import state_machine as sm
from app.modules.documentary.models import DocumentaryProject
from app.modules.documentary.research import ResearchService
from app.modules.documentary.schemas import ClaimIn, ProjectCreate, SourceIn
from app.modules.documentary.script import ScriptService
from app.modules.documentary.service import DocumentaryService


class StateMachineTests(unittest.TestCase):
    def test_chain_is_linear_and_gates_are_in_order(self):
        idx = [sm.state_index(sm.GATES[g][0]) for g in sm.GATE_ORDER]
        self.assertEqual(idx, sorted(idx))

    def test_required_gates_grow_with_target(self):
        self.assertEqual(sm.required_gates("research_review"), [])
        self.assertEqual(sm.required_gates("script_review"), ["research"])
        self.assertEqual(sm.required_gates("asset_generation"), ["research", "script"])
        self.assertEqual(sm.required_gates("exported"), list(sm.GATE_ORDER))

    def test_asset_generation_needs_script_gate(self):
        with self.assertRaises(ValidationError):
            sm.check_advance("storyboard_review", {"research"})
        self.assertEqual(sm.check_advance("storyboard_review", {"research", "script"}), "asset_generation")

    def test_failed_and_terminal_cannot_advance(self):
        with self.assertRaises(ValidationError):
            sm.check_advance("failed", set(sm.GATE_ORDER))
        with self.assertRaises(ValidationError):
            sm.check_advance("exported", set(sm.GATE_ORDER))

    def test_unknown_names_rejected(self):
        with self.assertRaises(ValidationError):
            sm.gate_state("nope")
        with self.assertRaises(ValidationError):
            sm.gates_invalidated_by_artifact("nope")


class _ServiceCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f"sqlite:///{Path(self.tmp.name) / 't.db'}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(
            bind=self.engine, tables=[t for n, t in Base.metadata.tables.items() if n.startswith("documentary_")]
        )
        self.db = sessionmaker(bind=self.engine)()
        self.svc = DocumentaryService(self.db)
        self.p = self.svc.create(ProjectCreate(title="T", topic="topic"))

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        try:
            self.tmp.cleanup()
        except PermissionError:  # known Windows SQLite tmpdir race
            pass

    def seed_for(self, state: str):
        """Give gates 1-2 the real content their content checks demand."""
        if state == "research_review" and not ResearchService(self.db).list_claims(self.p.id):
            r = ResearchService(self.db)
            src = r.add_source(self.p.id, SourceIn(title="Nguồn thử nghiệm"))
            r.add_claim(self.p.id, ClaimIn(text="Khẳng định thử.", status="verified", source_ids=[src.id]))
            self.svc.research_changed(self.p.id)
        if state == "script_review" and ScriptService(self.db).current_row(self.p.id) is None:
            scripts = ScriptService(self.db)
            p = self.svc.get(self.p.id)
            outline = scripts.generate_outline(p, "mock")
            self.svc.save_script(p.id, outline, "mock")
            self.svc.save_script(p.id, scripts.generate_script(p, "mock"), "mock")

    def go_to(self, state: str):
        """Walk the happy path, approving each gate when reached."""
        while self.svc.get(self.p.id).state != state:
            cur = self.svc.get(self.p.id).state
            self.seed_for(cur)
            for g, (review, _) in sm.GATES.items():
                if review == cur:
                    self.svc.approve(self.p.id, g)
            self.svc.advance(self.p.id)
        self.seed_for(state)

    def resave_script(self):
        scripts = ScriptService(self.db)
        row = scripts.current_row(self.p.id)
        from app.modules.documentary.schemas import ScriptSave
        self.svc.save_script(self.p.id, ScriptSave(outline=row.outline, sections=row.sections), "manual")


class WorkflowTests(_ServiceCase):
    def test_new_project_is_draft_and_persists(self):
        self.assertEqual(self.p.state, "draft")
        other_db = sessionmaker(bind=self.engine)()
        try:
            self.assertEqual(DocumentaryService(other_db).get(self.p.id).title, "T")
        finally:
            other_db.close()

    def test_cannot_pass_gate_without_approval(self):
        self.go_to("research_review")
        with self.assertRaises(ValidationError):
            self.svc.advance(self.p.id)
        self.svc.approve(self.p.id, "research")
        self.assertEqual(self.svc.advance(self.p.id).state, "script_review")

    def test_gate_only_approvable_in_its_state(self):
        with self.assertRaises(ValidationError):
            self.svc.approve(self.p.id, "script")  # still draft

    def test_full_path_to_exported(self):
        self.go_to("exported")
        detail = self.svc.detail(self.svc.get(self.p.id))
        self.assertTrue(all(g.status == "approved" for g in detail.gates))
        self.assertIsNone(detail.next_state)

    def test_cannot_export_without_final_approval(self):
        self.go_to("final_review")
        with self.assertRaises(ValidationError):
            self.svc.advance(self.p.id)  # -> approved needs "final"
        self.svc.approve(self.p.id, "final")
        self.svc.advance(self.p.id)
        self.assertEqual(self.svc.get(self.p.id).state, "approved")

    def test_reject_blocks_advance(self):
        self.go_to("script_review")
        self.svc.reject(self.p.id, "script", "needs work")
        with self.assertRaises(ValidationError):
            self.svc.advance(self.p.id)

    def test_editing_approved_script_invalidates_downstream(self):
        self.go_to("audio_ready")
        self.svc.approve(self.p.id, "narration_timing")
        before = self.svc.get(self.p.id).script_version
        p = self.svc.bump_artifact(self.p.id, "script")
        self.assertEqual(p.state, "script_review")
        self.assertEqual(p.script_version, before + 1)
        status = {g.gate: g.status for g in self.svc.gate_statuses(p)}
        self.assertEqual(status["research"], "approved")  # upstream untouched
        for g in ("script", "storyboard_assets", "narration_timing", "final"):
            self.assertEqual(status[g], "pending")

    def test_stale_approval_is_not_valid(self):
        self.go_to("script_review")
        self.svc.approve(self.p.id, "script")
        # Bump without going through the service's revoke path -> stale.
        self.p.script_version += 1
        self.db.commit()
        gate = next(g for g in self.svc.gate_statuses(self.p) if g.gate == "script")
        self.assertEqual(gate.status, "stale")
        with self.assertRaises(ValidationError):
            self.svc.advance(self.p.id)

    def test_approval_history_is_append_only_and_records_version(self):
        self.go_to("script_review")
        self.svc.approve(self.p.id, "script")
        self.resave_script()  # bumps to v+1 and revokes
        self.svc.approve(self.p.id, "script")
        rows = [r for r in self.svc.history(self.p.id) if r.gate == "script"]
        v = self.svc.get(self.p.id).script_version
        self.assertEqual([(r.decision, r.artifact_version) for r in rows],
                         [("approved", v - 1), ("revoked", v - 1), ("approved", v)])

    def test_rewind_revokes_gates_from_that_stage(self):
        self.go_to("audio_ready")
        p = self.svc.rewind(self.p.id, "asset_review")
        self.assertEqual(p.state, "asset_review")
        status = {g.gate: g.status for g in self.svc.gate_statuses(p)}
        self.assertEqual(status["script"], "approved")
        self.assertEqual(status["storyboard_assets"], "pending")

    def test_rewind_forward_rejected(self):
        self.go_to("script_review")
        with self.assertRaises(ValidationError):
            self.svc.rewind(self.p.id, "asset_review")

    def test_fail_and_resume(self):
        self.go_to("asset_generation")
        p = self.svc.fail(self.p.id, "provider down")
        self.assertEqual((p.state, p.failed_from_state), ("failed", "asset_generation"))
        with self.assertRaises(ValidationError):
            self.svc.advance(self.p.id)
        p = self.svc.resume(self.p.id)
        self.assertEqual((p.state, p.error_message), ("asset_generation", None))
        with self.assertRaises(ValidationError):
            self.svc.resume(self.p.id)

    def test_demo_is_idempotent_and_labelled(self):
        a = self.svc.create_demo()
        b = self.svc.create_demo()
        self.assertEqual(a.id, b.id)
        self.assertTrue(a.is_demo)
        self.assertTrue(a.title.startswith("[MẪU]"))

    def test_missing_project(self):
        with self.assertRaises(NotFoundError):
            self.svc.get(9999)


if __name__ == "__main__":
    unittest.main()
