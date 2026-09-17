"""Pure-function tests: text chunking + caption line grouping. No network,
no ffmpeg."""

import unittest

from app.modules.storyteller.service import (
    CHUNK_TARGET_CHARS,
    _group_words_into_lines,
    chunk_script,
)


class ChunkScriptTests(unittest.TestCase):
    def test_short_text_is_one_chunk(self):
        text = "Một đoạn ngắn.\n\nMột đoạn nữa."
        chunks = chunk_script(text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].split(), text.split())

    def test_splits_on_paragraph_boundaries_when_over_target(self):
        para_a = "A " * 900  # ~1800 chars
        para_b = "B " * 900
        chunks = chunk_script(f"{para_a}\n\n{para_b}", target_chars=1000)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), 1200)  # some slack for sentence splitting

    def test_never_produces_empty_chunks(self):
        chunks = chunk_script("Word. " * 2000, target_chars=CHUNK_TARGET_CHARS)
        self.assertTrue(all(c.strip() for c in chunks))

    def test_reassembling_chunks_preserves_all_words(self):
        text = "Xin chào các bạn. " * 100
        chunks = chunk_script(text, target_chars=200)
        reassembled_words = " ".join(chunks).split()
        original_words = text.split()
        self.assertEqual(len(reassembled_words), len(original_words))

    def test_single_very_long_sentence_still_splits(self):
        # No paragraph breaks, no sentence-ending punctuation -- must not
        # infinite-loop or produce one giant unsplit chunk.
        text = "word " * 2000
        chunks = chunk_script(text, target_chars=500)
        self.assertGreater(len(chunks), 1)


def _word(text: str, start: float, end: float) -> dict:
    return {"text": text, "start": start, "end": end}


class GroupWordsIntoLinesTests(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(_group_words_into_lines([]), [])

    def test_breaks_on_gap(self):
        words = [_word("a", 0.0, 0.3), _word("b", 2.0, 2.3)]  # 1.7s gap
        lines = _group_words_into_lines(words)
        self.assertEqual(len(lines), 2)

    def test_breaks_on_max_words_per_line(self):
        words = [_word(str(i), i * 0.3, i * 0.3 + 0.2) for i in range(25)]
        lines = _group_words_into_lines(words)
        self.assertTrue(all(len(line) <= 10 for line in lines))
        self.assertGreater(len(lines), 1)

    def test_no_word_is_lost(self):
        words = [_word(str(i), i * 0.3, i * 0.3 + 0.2) for i in range(17)]
        lines = _group_words_into_lines(words)
        flat = [w for line in lines for w in line]
        self.assertEqual(len(flat), 17)


if __name__ == "__main__":
    unittest.main()
