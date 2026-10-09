"""Documentary research + script (feature 164): claim/source rules, script
versions, factual review gating, providers (LLM call mocked -- no network)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.db.base import Base
from app.modules.documentary import state_machine as sm
from app.modules.documentary.research import ResearchService
from app.modules.documentary.schemas import (
    ClaimIn,
    ProjectCreate,
    ScriptParagraph,
    ScriptSave,
    ScriptSection,
    SourceIn,
)
from app.modules.documentary.script import ScriptService
from app.modules.documentary.script_providers import available_providers, get_provider
from app.modules.documentary.service import DocumentaryService


class _Case(unittest.TestCase):
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
        self.research = ResearchService(self.db)
        self.scripts = ScriptService(self.db)
        self.p = self.svc.create(ProjectCreate(title="T", topic="chủ đề thử"))

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        try:
            self.tmp.cleanup()
        except PermissionError:  # known Windows SQLite tmpdir race
            pass

    def source(self, title="S"):
        return self.research.add_source(self.p.id, SourceIn(title=title))

    def verified_claim(self, text="Sự kiện A xảy ra."):
        return self.research.add_claim(
            self.p.id, ClaimIn(text=text, status="verified", source_ids=[self.source().id])
        )


class SourceTests(_Case):
    def test_url_must_be_http(self):
        for bad in ("file:///etc/passwd", "javascript:alert(1)", "not a url"):
            with self.assertRaises(PydanticValidationError):
                SourceIn(title="x", url=bad)
        self.assertEqual(SourceIn(title="x", url="https://example.org/a").url, "https://example.org/a")
        self.assertIsNone(SourceIn(title="x", url="  ").url)

    def test_source_scoped_to_project(self):
        other = self.svc.create(ProjectCreate(title="O", topic="o"))
        s = self.source()
        with self.assertRaises(NotFoundError):
            self.research.update_source(other.id, s.id, SourceIn(title="hack"))


class ClaimTests(_Case):
    def test_verified_requires_a_source(self):
        with self.assertRaises(ValidationError):
            self.research.add_claim(self.p.id, ClaimIn(text="x", status="verified"))
        with self.assertRaises(ValidationError):
            self.research.add_claim(self.p.id, ClaimIn(text="x", status="disputed"))
        self.research.add_claim(self.p.id, ClaimIn(text="x", status="unverified"))

    def test_cannot_link_foreign_source(self):
        other = self.svc.create(ProjectCreate(title="O", topic="o"))
        foreign = self.research.add_source(other.id, SourceIn(title="f"))
        with self.assertRaises(ValidationError):
            self.research.add_claim(self.p.id, ClaimIn(text="x", status="verified", source_ids=[foreign.id]))

    def test_cannot_delete_last_source_of_verified_claim(self):
        c = self.verified_claim()
        with self.assertRaises(ValidationError):
            self.research.delete_source(self.p.id, c.source_ids[0])
        # after downgrading the claim the source can go
        self.research.update_claim(self.p.id, c.id, ClaimIn(text=c.text, status="unverified"))
        self.research.delete_source(self.p.id, c.source_ids[0])
        self.assertEqual(self.research.list_claims(self.p.id)[0].source_ids, [])

    def test_review_rules(self):
        self.assertEqual(self.research.review(self.p.id)[0].code, "no_claims")
        self.research.add_claim(self.p.id, ClaimIn(text="x"))
        self.assertEqual(self.research.review(self.p.id)[0].code, "nothing_sourced")
        s = self.source()
        self.research.add_claim(self.p.id, ClaimIn(text="y", status="disputed", source_ids=[s.id]))
        self.assertEqual(self.research.review(self.p.id)[0].code, "disputed_without_note")
        self.research.update_claim(
            self.p.id, 2, ClaimIn(text="y", status="disputed", uncertainty_note="hai cách giải thích", source_ids=[s.id])
        )
        self.assertEqual(self.research.review(self.p.id), [])


class ScriptTests(_Case):
    def drafted(self):
        self.verified_claim("Sự kiện A xảy ra.")
        self.verified_claim("Sự kiện B xảy ra sau đó.")
        outline = self.scripts.generate_outline(self.svc.get(self.p.id), "mock")
        self.svc.save_script(self.p.id, outline, "mock")
        full = self.scripts.generate_script(self.svc.get(self.p.id), "mock")
        return self.svc.save_script(self.p.id, full, "mock")

    def test_outline_needs_claims(self):
        with self.assertRaises(ValidationError):
            self.scripts.generate_outline(self.svc.get(self.p.id), "mock")

    def test_script_needs_outline_first(self):
        self.verified_claim()
        with self.assertRaises(ValidationError):
            self.scripts.generate_script(self.svc.get(self.p.id), "mock")

    def test_mock_covers_seven_sections_and_invents_nothing(self):
        row = self.drafted()
        out = self.scripts.to_out(row)
        self.assertEqual(len(out.sections), 7)
        factual = [p for s in out.sections for p in s.paragraphs if p.factual]
        self.assertEqual({p.text for p in factual}, {"Sự kiện A xảy ra.", "Sự kiện B xảy ra sau đó."})
        self.assertTrue(all(p.claim_ids for p in factual))
        self.assertTrue(all(not p.claim_ids for s in out.sections for p in s.paragraphs if not p.factual))

    def test_versions_append_and_match_project_version(self):
        self.drafted()
        hist = self.scripts.history(self.p.id)
        self.assertEqual([h.version for h in hist], [2, 3])
        self.assertEqual(self.svc.get(self.p.id).script_version, 3)

    def test_review_passes_for_sourced_mock_script(self):
        self.drafted()
        r = self.scripts.review(self.p.id)
        self.assertTrue(r.ok, r.issues)
        self.assertIn("mock_origin", [w.code for w in r.warnings])

    def test_review_flags_uncited_unverified_and_missing(self):
        c = self.verified_claim()
        unv = self.research.add_claim(self.p.id, ClaimIn(text="chưa rõ"))
        data = ScriptSave(
            sections=[
                ScriptSection(
                    kind="hook",
                    heading="h",
                    paragraphs=[
                        ScriptParagraph(text="Khẳng định không có nguồn."),
                        ScriptParagraph(text="Dựa trên claim chưa xác minh.", claim_ids=[unv.id]),
                        ScriptParagraph(text="OK.", claim_ids=[c.id]),
                    ],
                )
            ]
        )
        self.svc.save_script(self.p.id, data, "manual")
        codes = [i.code for i in self.scripts.review(self.p.id).issues]
        self.assertIn("uncited_claim", codes)
        self.assertIn("unverified_claim", codes)
        self.assertEqual(codes.count("missing_section"), 6)

    def test_save_rejects_unknown_claim_and_does_not_bump(self):
        before = self.svc.get(self.p.id).script_version
        data = ScriptSave(
            sections=[ScriptSection(kind="hook", heading="h", paragraphs=[ScriptParagraph(text="x", claim_ids=[999])])]
        )
        with self.assertRaises(ValidationError):
            self.svc.save_script(self.p.id, data, "manual")
        self.assertEqual(self.svc.get(self.p.id).script_version, before)

    def test_duplicate_section_kind_rejected(self):
        sec = ScriptSection(kind="hook", heading="h", paragraphs=[ScriptParagraph(text="x", factual=False)])
        with self.assertRaises(ValidationError):
            self.svc.save_script(self.p.id, ScriptSave(sections=[sec, sec]), "manual")

    def test_stale_script_cannot_be_approved(self):
        self.drafted()
        self.svc.bump_artifact(self.p.id, "script")  # version moved, no new text saved
        self.assertEqual(self.scripts.review(self.p.id).issues[0].code, "stale_script")

    def test_gate_refuses_bad_script_and_accepts_good_one(self):
        self.drafted()
        # walk to script_review
        self.svc.advance(self.p.id)  # draft -> research_review
        self.svc.approve(self.p.id, "research")
        self.svc.advance(self.p.id)
        self.assertEqual(self.svc.get(self.p.id).state, "script_review")
        self.svc.approve(self.p.id, "script")
        self.assertEqual(self.svc.advance(self.p.id).state, "storyboard_review")

    def test_editing_research_after_script_approval_sends_project_back(self):
        self.drafted()
        self.svc.advance(self.p.id)
        self.svc.approve(self.p.id, "research")
        self.svc.advance(self.p.id)
        self.svc.approve(self.p.id, "script")
        self.svc.advance(self.p.id)
        self.research.add_claim(self.p.id, ClaimIn(text="thêm"))
        self.svc.research_changed(self.p.id)
        p = self.svc.get(self.p.id)
        self.assertEqual(p.state, "research_review")
        status = {g.gate: g.status for g in self.svc.gate_statuses(p)}
        self.assertEqual((status["research"], status["script"]), ("pending", "pending"))

    def test_research_gate_refused_without_claims(self):
        self.svc.advance(self.p.id)
        with self.assertRaises(ValidationError):
            self.svc.approve(self.p.id, "research")


class ProviderTests(_Case):
    def test_mock_registered_and_unknown_rejected(self):
        self.assertIn("mock", available_providers())
        with self.assertRaises(ValidationError):
            get_provider("does-not-exist")

    def test_llm_provider_not_configured_is_clear_error(self):
        from app.api.v1.endpoints import documentary_llm as m

        self.verified_claim()
        with patch.object(m, "resolve_ai_credentials", return_value=None):
            with self.assertRaises(ValidationError):
                get_provider("llm").make_outline(self.scripts.context(self.svc.get(self.p.id)))

    def test_llm_provider_parses_structured_output(self):
        from app.api.v1.endpoints import documentary_llm as m
        from app.modules.ai.llm_client import AICredentials, LLMCallResult

        c = self.verified_claim()
        payload = {
            "outline": [{"kind": "hook", "summary": "Mở đầu", "claim_ids": [c.id]}]
        }
        fake = LLMCallResult(
            text=json.dumps(payload), refused=False, provider="openai", model="m",
            input_tokens=1, output_tokens=1, latency_ms=1,
        )
        with patch.object(m, "resolve_ai_credentials", return_value=AICredentials("openai", "k")), patch.object(
            m, "call_structured", return_value=fake
        ):
            draft = self.scripts.generate_outline(self.svc.get(self.p.id), "llm")
        self.assertEqual(draft.outline[0].claim_ids, [c.id])

    def test_llm_hallucinated_claim_id_blocked_at_save(self):
        from app.api.v1.endpoints import documentary_llm as m
        from app.modules.ai.llm_client import AICredentials, LLMCallResult

        self.verified_claim()
        payload = {"outline": [{"kind": "hook", "summary": "x", "claim_ids": [4242]}]}
        fake = LLMCallResult(json.dumps(payload), False, "openai", "m", 1, 1, 1)
        with patch.object(m, "resolve_ai_credentials", return_value=AICredentials("openai", "k")), patch.object(
            m, "call_structured", return_value=fake
        ):
            draft = self.scripts.generate_outline(self.svc.get(self.p.id), "llm")
        with self.assertRaises(ValidationError):
            self.svc.save_script(self.p.id, draft, "llm")

    def test_llm_refusal_and_bad_json(self):
        from app.api.v1.endpoints import documentary_llm as m
        from app.modules.ai.llm_client import AICredentials, LLMCallResult

        self.verified_claim()
        ctx = self.scripts.context(self.svc.get(self.p.id))
        for result in (
            LLMCallResult("", True, "openai", "m", 1, 1, 1),
            LLMCallResult("not json", False, "openai", "m", 1, 1, 1),
        ):
            with patch.object(m, "resolve_ai_credentials", return_value=AICredentials("openai", "k")), patch.object(
                m, "call_structured", return_value=result
            ):
                with self.assertRaises(ExternalServiceError):
                    get_provider("llm").make_outline(ctx)


if __name__ == "__main__":
    unittest.main()
