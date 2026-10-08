from app.modules.manhua.fetch import _find_filler

A, B, C = "a" * 40, "b" * 40, "c" * 40
PH_A, PH_B, PH_C = "0" * 64, "f" * 64, "0f" * 32


def _cache() -> dict:
    return {"exact": {}, "phash": {}}


def test_page_served_twice_in_one_chapter_keeps_first_copy():
    filler = _find_filler([0, 0, 0, 0], ["ch1"], [A, A, B, B], [PH_A, PH_A, PH_B, PH_B], _cache())
    assert filler == [False, True, False, True]


def test_same_image_across_chapters_in_one_run_is_dropped_everywhere():
    filler = _find_filler([0, 0, 1, 1], ["ch1", "ch2"], [A, B, A, C], [PH_A, PH_B, PH_A, PH_C], _cache())
    assert filler == [True, False, True, False]


def test_refetching_the_same_chapter_does_not_flag_its_pages():
    cache = _cache()
    assert _find_filler([0, 0], ["ch1"], [A, B], [PH_A, PH_B], cache) == [False, False]
    assert _find_filler([0, 0], ["ch1"], [A, B], [PH_A, PH_B], cache) == [False, False]


def test_image_cached_from_another_chapter_is_filler():
    cache = _cache()
    _find_filler([0, 0], ["ch1"], [A, B], [PH_A, PH_B], cache)
    assert _find_filler([0, 0], ["ch2"], [A, C], [PH_A, PH_C], cache) == [True, False]


def test_legacy_count_cache_still_flags_known_filler():
    cache = {"exact": {A: 3}, "phash": {PH_A: 3}}
    assert _find_filler([0], ["ch9"], [A], [PH_A], cache) == [True]
