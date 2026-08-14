import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.db.base import Base
from app.modules.asset.models import Asset
from app.modules.asset.schemas import AssetRegisterIn
from app.modules.asset.service import AssetService, _normalize_path, _normalize_tags


class AssetServiceTestCase(unittest.TestCase):
    """Each test gets its own in-memory SQLite DB with *only* the asset
    table created (not the whole app schema) -- proof this module doesn't
    need any other table to exist, matching its "must remain completely
    self-contained" requirement.
    """

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine, tables=[Asset.__table__])
        self.db = Session(bind=self.engine)
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.service = AssetService(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmpdir.cleanup()

    def _write_file(self, name: str, content: bytes = b"fake-media-bytes") -> Path:
        path = self.tmp_path / name
        path.write_bytes(content)
        return path

    def _register(self, name: str, **overrides) -> Asset:
        file_path = overrides.pop("path", None) or self._write_file(name)
        payload = AssetRegisterIn(
            filename=overrides.pop("filename", name),
            path=str(file_path),
            type=overrides.pop("type", "image"),
            tags=overrides.pop("tags", []),
            **overrides,
        )
        return self.service.register(payload)


class RegistrationTests(AssetServiceTestCase):
    def test_register_creates_asset_with_computed_fields(self):
        asset = self._register("woman_portrait.jpg", type="image", tags=["Woman", "Emotional"])

        self.assertIsNotNone(asset.id)
        self.assertEqual(asset.filename, "woman_portrait.jpg")
        self.assertEqual(asset.type, "image")
        self.assertEqual(asset.tags, ["Woman", "Emotional"])
        self.assertEqual(asset.filesize_bytes, len(b"fake-media-bytes"))
        self.assertTrue(Path(asset.path).is_absolute())
        self.assertTrue(asset.is_ready)

    def test_register_normalizes_and_dedupes_tags_case_insensitively(self):
        asset = self._register("clip.mp4", type="video", tags=["Woman", " woman ", "Portrait", ""])
        self.assertEqual(asset.tags, ["Woman", "Portrait"])

    def test_register_persists_across_a_fresh_session(self):
        created = self._register("clip.mp4", type="video")
        fetched = self.service.get(created.id)
        self.assertEqual(fetched.id, created.id)
        self.assertEqual(fetched.path, created.path)


class InvalidAssetTests(AssetServiceTestCase):
    def test_register_missing_file_rejected(self):
        missing_path = self.tmp_path / "does_not_exist.mp4"
        with self.assertRaises(ValidationError):
            self._register("does_not_exist.mp4", path=missing_path, type="video")

    def test_register_directory_path_rejected(self):
        directory = self.tmp_path / "a_directory"
        directory.mkdir()
        with self.assertRaises(ValidationError):
            self._register("a_directory", path=directory, type="video")

    def test_register_duplicate_path_rejected(self):
        file_path = self._write_file("dup.mp4")
        self._register("dup.mp4", path=file_path, type="video")
        with self.assertRaises(ValidationError):
            self._register("dup.mp4", path=file_path, type="video")


class MissingAssetTests(AssetServiceTestCase):
    def test_get_unknown_asset_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            self.service.get(999)

    def test_delete_unknown_asset_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            self.service.delete(999)

    def test_delete_removes_asset(self):
        asset = self._register("clip.mp4", type="video")
        self.service.delete(asset.id)
        with self.assertRaises(NotFoundError):
            self.service.get(asset.id)


class GetImageTests(AssetServiceTestCase):
    def test_get_image_returns_an_image_asset(self):
        asset = self._register("woman_portrait.jpg", type="image")
        fetched = self.service.get_image(asset.id)
        self.assertEqual(fetched.id, asset.id)
        self.assertEqual(fetched.type, "image")

    def test_get_image_for_missing_asset_raises_not_found(self):
        with self.assertRaises(NotFoundError):
            self.service.get_image(999)

    def test_get_image_for_video_asset_is_rejected(self):
        asset = self._register("clip.mp4", type="video")
        with self.assertRaises(ValidationError):
            self.service.get_image(asset.id)

    def test_get_image_for_audio_asset_is_rejected(self):
        asset = self._register("voice.mp3", type="audio")
        with self.assertRaises(ValidationError):
            self.service.get_image(asset.id)


class SearchAndRankingTests(AssetServiceTestCase):
    def setUp(self):
        super().setUp()
        self.woman_exact = self._register(
            "portrait_1.jpg", type="image", tags=["woman", "emotional", "portrait"]
        )
        self.woman_partial = self._register(
            "portrait_2.jpg", type="image", tags=["woman-group", "joyful"]
        )
        self.unrelated = self._register("landscape.jpg", type="image", tags=["mountain", "nature"])
        self.man_video = self._register("man_clip.mp4", type="video", tags=["man", "emotional"])

        # Pin explicit, strictly increasing created_at values so the
        # "sorted by recency" test is deterministic regardless of how fast
        # registrations happen to run back-to-back (datetime.now() calls
        # made microseconds apart can otherwise tie).
        base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for index, asset in enumerate(
            [self.woman_exact, self.woman_partial, self.unrelated, self.man_video]
        ):
            asset.created_at = base_time + timedelta(seconds=index)
        self.db.commit()

    def test_search_returns_only_matching_assets_ranked_by_score(self):
        results = self.service.search(query=["woman", "emotional"])
        result_ids = [asset.id for asset in results]

        # woman_exact matches "woman" (exact tag) + "emotional" (exact tag) -> highest score
        self.assertEqual(result_ids[0], self.woman_exact.id)
        # unrelated has no match at all and must be excluded entirely
        self.assertNotIn(self.unrelated.id, result_ids)

    def test_search_partial_tag_match_ranks_below_exact_tag_match(self):
        results = self.service.search(query=["woman"])
        result_ids = [asset.id for asset in results]
        self.assertIn(self.woman_exact.id, result_ids)
        self.assertIn(self.woman_partial.id, result_ids)
        self.assertLess(result_ids.index(self.woman_exact.id), result_ids.index(self.woman_partial.id))

    def test_search_is_case_insensitive(self):
        results = self.service.search(query=["WOMAN", "Emotional"])
        result_ids = [asset.id for asset in results]
        self.assertIn(self.woman_exact.id, result_ids)

    def test_search_filters_by_asset_type(self):
        results = self.service.search(query=["emotional"], asset_type="video")
        self.assertEqual([asset.id for asset in results], [self.man_video.id])

    def test_search_with_no_query_returns_all_sorted_by_recency(self):
        results = self.service.search(query=None)
        self.assertEqual(len(results), 4)
        # most recently registered (man_video, registered last in setUp) first
        self.assertEqual(results[0].id, self.man_video.id)

    def test_search_with_no_matches_returns_empty_list(self):
        results = self.service.search(query=["nonexistent-keyword-xyz"])
        self.assertEqual(results, [])


class FilesystemPathHandlingTests(unittest.TestCase):
    def test_normalize_path_resolves_dot_segments_to_same_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clip.mp4"
            target.write_bytes(b"data")

            direct = _normalize_path(str(target))
            via_dot_segment = _normalize_path(str(tmp_path / "." / "clip.mp4"))
            via_parent_and_back = _normalize_path(str(tmp_path / "sub" / ".." / "clip.mp4"))

            self.assertEqual(direct, via_dot_segment)
            self.assertEqual(direct, via_parent_and_back)
            self.assertTrue(direct.is_absolute())

    def test_normalize_tags_dedupes_case_insensitively_preserving_first_casing(self):
        self.assertEqual(
            _normalize_tags(["Woman", " woman ", "WOMAN", "Portrait", ""]),
            ["Woman", "Portrait"],
        )


if __name__ == "__main__":
    unittest.main()
