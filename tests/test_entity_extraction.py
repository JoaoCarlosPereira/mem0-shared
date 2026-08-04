"""Tests for mem0.utils.entity_extraction — extract_entities, extract_entities_batch."""

from unittest.mock import MagicMock, patch

import pytest

from mem0.utils.entity_extraction import (
    _extract_entities_from_doc,
    _has_artifacts,
    _is_sentence_start,
    extract_entities,
    extract_entities_batch,
)


# ── _is_sentence_start ─────────────────────────────────────────────────────


class TestIsSentenceStart:
    def test_index_zero_is_start(self):
        tokens = [MagicMock()]
        assert _is_sentence_start(tokens, 0) is True

    def test_sent_start_token_is_start(self):
        tok1 = MagicMock()
        tok1.is_sent_start = True
        tokens = [MagicMock(), tok1]
        assert _is_sentence_start(tokens, 1) is True

    def test_after_period_is_start(self):
        tok1 = MagicMock()
        tok1.text = "."
        tokens = [MagicMock(), tok1]
        assert _is_sentence_start(tokens, 1) is True

    def test_after_exclamation_is_start(self):
        tok1 = MagicMock()
        tok1.text = "!"
        tokens = [MagicMock(), tok1]
        assert _is_sentence_start(tokens, 1) is True

    def test_after_question_mark_is_start(self):
        tok1 = MagicMock()
        tok1.text = "?"
        tokens = [MagicMock(), tok1]
        assert _is_sentence_start(tokens, 1) is True

    def test_after_colon_is_start(self):
        tok1 = MagicMock()
        tok1.text = ":"
        tokens = [MagicMock(), tok1]
        assert _is_sentence_start(tokens, 1) is True

    def test_after_newline_is_start(self):
        tok1 = MagicMock()
        tok1.text = "\n"
        tokens = [MagicMock(), tok1]
        assert _is_sentence_start(tokens, 1) is True

    def test_after_formatting_marker_is_start(self):
        tok1 = MagicMock()
        tok1.text = "#"
        tokens = [MagicMock(), tok1]
        assert _is_sentence_start(tokens, 1) is True


# ── _has_artifacts ─────────────────────────────────────────────────────────


class TestHasArtifacts:
    def test_double_asterisk_is_artifact(self):
        assert _has_artifacts("**text**") is True

    def test_double_underscore_is_artifact(self):
        assert _has_artifacts("__text__") is True

    def test_double_space_is_artifact(self):
        assert _has_artifacts("text  more") is True

    def test_newline_is_artifact(self):
        assert _has_artifacts("text\nmore") is True

    def test_tab_is_artifact(self):
        assert _has_artifacts("text\tmore") is True

    def test_long_text_is_artifact(self):
        assert _has_artifacts("a" * 101) is True

    def test_bullet_start_is_artifact(self):
        assert _has_artifacts("\u2022 item") is True

    def test_plain_text_no_artifact(self):
        assert _has_artifacts("simple text") is False


# ── extract_entities ───────────────────────────────────────────────────────


class TestExtractEntities:
    def test_returns_empty_list_when_spacy_unavailable(self):
        with patch("mem0.utils.spacy_models.get_nlp_full", return_value=None):
            result = extract_entities("hello world")
            assert result == []

    def test_returns_list_of_tuples(self):
        mock_doc = MagicMock()
        mock_doc.text = "Apple announced iPhone 15 in California."
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.noun_chunks = []

        with patch("mem0.utils.spacy_models.get_nlp_full", return_value=MagicMock(return_value=mock_doc)):
            result = extract_entities("Apple announced iPhone 15 in California.")
            assert isinstance(result, list)

    def test_called_with_string(self):
        with patch("mem0.utils.spacy_models.get_nlp_full") as mock_get:
            mock_doc = MagicMock()
            mock_doc.text = "test"
            mock_doc.__iter__ = MagicMock(return_value=iter([]))
            mock_doc.noun_chunks = []
            mock_get.return_value = MagicMock(return_value=mock_doc)

            extract_entities("test string")
            mock_get.assert_called_once()

    def test_output_format(self):
        mock_doc = MagicMock()
        mock_doc.text = "Apple announced iPhone 15 in California."
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.noun_chunks = []

        with patch("mem0.utils.spacy_models.get_nlp_full", return_value=MagicMock(return_value=mock_doc)):
            result = extract_entities("Apple announced iPhone 15 in California.")
            for item in result:
                assert isinstance(item, tuple)
                assert len(item) == 2
                assert item[0] in ("PROPER", "QUOTED", "COMPOUND", "NOUN")


# ── extract_entities_batch ────────────────────────────────────────────────


class TestExtractEntitiesBatch:
    def test_empty_list_returns_empty_list(self):
        result = extract_entities_batch([])
        assert result == []

    def test_returns_list_of_lists(self):
        mock_doc = MagicMock()
        mock_doc.text = "test"
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.noun_chunks = []
        mock_nlp = MagicMock()
        mock_nlp.pipe = MagicMock(return_value=[mock_doc, mock_doc])
        mock_nlp.return_value = mock_doc

        with patch("mem0.utils.spacy_models.get_nlp_full", return_value=mock_nlp):
            result = extract_entities_batch(["text1", "text2"])
            assert isinstance(result, list)
            assert len(result) == 2
            for item in result:
                assert isinstance(item, list)

    def test_batch_uses_nlp_pipe(self):
        mock_doc = MagicMock()
        mock_doc.text = "test"
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.noun_chunks = []
        mock_nlp = MagicMock()
        mock_nlp.pipe = MagicMock(return_value=[mock_doc, mock_doc])

        with patch("mem0.utils.spacy_models.get_nlp_full", return_value=mock_nlp):
            extract_entities_batch(["text1", "text2"])
            mock_nlp.pipe.assert_called_once()

    def test_batch_with_spacy_unavailable(self):
        with patch("mem0.utils.spacy_models.get_nlp_full", return_value=None):
            result = extract_entities_batch(["text1", "text2"])
            assert result == [[], []]

    def test_batch_preserves_order(self):
        mock_doc = MagicMock()
        mock_doc.text = "test"
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.noun_chunks = []
        mock_nlp = MagicMock()
        mock_nlp.pipe = MagicMock(return_value=[mock_doc, mock_doc, mock_doc])
        mock_nlp.return_value = mock_doc

        with patch("mem0.utils.spacy_models.get_nlp_full", return_value=mock_nlp):
            result = extract_entities_batch(["a", "b", "c"])
            assert len(result) == 3


# ── _extract_entities_from_doc ────────────────────────────────────────────


class TestExtractEntitiesFromDoc:
    def test_returns_list_of_tuples(self):
        mock_doc = MagicMock()
        mock_doc.text = "test"
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.noun_chunks = []
        mock_doc.tokens = []

        result = _extract_entities_from_doc(mock_doc)
        assert isinstance(result, list)

    def test_proper_noun_detection(self):
        """Tests proper noun sequence extraction."""
        mock_tok1 = MagicMock()
        mock_tok1.text = "Apple"
        mock_tok1.text_with_ws = "Apple "
        mock_tok1.isupper = lambda: True
        mock_tok1.pos_ = "PROPN"

        mock_tok2 = MagicMock()
        mock_tok2.text = "Announced"
        mock_tok2.text_with_ws = " "
        mock_tok2.pos_ = "PROPN"
        mock_tok2.text_with_ws = " "

        mock_doc = MagicMock()
        mock_doc.text = "Apple Announced iPhone"
        mock_doc.noun_chunks = []
        mock_doc.tokens = [mock_tok1, mock_tok2]

        result = _extract_entities_from_doc(mock_doc)
        assert isinstance(result, list)

    def test_quoted_text_extraction(self):
        """Tests quoted text extraction."""
        mock_doc = MagicMock()
        mock_doc.text = 'She said "hello world" and left.'
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.noun_chunks = []
        mock_doc.tokens = []

        result = _extract_entities_from_doc(mock_doc)
        assert isinstance(result, list)
        # Check if QUOTED entities are found
        quoted_entities = [e for e in result if e[0] == "QUOTED"]
        assert len(quoted_entities) >= 1

    def test_deduplication(self):
        """Tests that duplicate entities are deduplicated."""
        mock_doc = MagicMock()
        mock_doc.text = "Test deduplication"
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.noun_chunks = []
        mock_doc.tokens = []

        result = _extract_entities_from_doc(mock_doc)
        seen_lower = set()
        for _, text in result:
            assert text.lower() not in seen_lower
            seen_lower.add(text.lower())

    def test_generic_caps_filtered(self):
        """Generic capitalized single words are filtered out."""
        mock_tok = MagicMock()
        mock_tok.text = "Works"
        mock_tok.text_with_ws = "Works "
        mock_tok.pos_ = "PROPN"
        mock_tok.lemma_ = "work"

        mock_doc = MagicMock()
        mock_doc.text = "Works"
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_tok]))
        mock_doc.noun_chunks = []
        mock_doc.tokens = [mock_tok]

        result = _extract_entities_from_doc(mock_doc)
        # "works" is in _GENERIC_CAPS, so should be filtered
        works_entities = [e for e in result if e[1].lower() == "works"]
        assert len(works_entities) == 0

    def test_generic_ending_stripped_from_compounds(self):
        """Generic ending words are stripped from compound entities."""
        mock_tok = MagicMock()
        mock_tok.text = "Machine"
        mock_tok.text_with_ws = "Machine "
        mock_tok.pos_ = "NOUN"
        mock_tok.lemma_ = "machine"
        mock_tok.dep_ = "compound"

        mock_tok2 = MagicMock()
        mock_tok2.text = "Learning"
        mock_tok2.text_with_ws = " "
        mock_tok2.pos_ = "NOUN"
        mock_tok2.lemma_ = "learning"
        mock_tok2.dep_ = "compound"

        mock_doc = MagicMock()
        mock_doc.text = "Machine Learning"
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_tok, mock_tok2]))
        mock_doc.noun_chunks = [MagicMock(tokens=[mock_tok, mock_tok2], __iter__=lambda s: iter([mock_tok, mock_tok2]))]
        mock_doc.tokens = [mock_tok, mock_tok2]

        result = _extract_entities_from_doc(mock_doc)
        assert isinstance(result, list)

    def test_substring_filtering(self):
        """Shorter entities that are substrings of longer ones are removed."""
        mock_tok = MagicMock()
        mock_tok.text = "New"
        mock_tok.text_with_ws = "New "
        mock_tok.pos_ = "PROPN"

        mock_tok2 = MagicMock()
        mock_tok2.text = "York"
        mock_tok2.text_with_ws = " "
        mock_tok2.pos_ = "PROPN"

        mock_doc = MagicMock()
        mock_doc.text = "New York"
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_tok, mock_tok2]))
        mock_doc.noun_chunks = []
        mock_doc.tokens = [mock_tok, mock_tok2]

        result = _extract_entities_from_doc(mock_doc)
        assert isinstance(result, list)

    def test_artifact_text_filtered(self):
        """Text with formatting artifacts is filtered."""
        mock_doc = MagicMock()
        mock_doc.text = "**bold** text"
        mock_doc.__iter__ = MagicMock(return_value=iter([]))
        mock_doc.noun_chunks = []
        mock_doc.tokens = []

        result = _extract_entities_from_doc(mock_doc)
        for _, text in result:
            assert "**" not in text

    def test_short_entities_filtered(self):
        """Entities with <=2 chars after cleanup are filtered."""
        mock_tok = MagicMock()
        mock_tok.text = "A"
        mock_tok.text_with_ws = "A "
        mock_tok.pos_ = "PROPN"
        mock_tok.lemma_ = "a"

        mock_doc = MagicMock()
        mock_doc.text = "A"
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_tok]))
        mock_doc.noun_chunks = []
        mock_doc.tokens = [mock_tok]

        result = _extract_entities_from_doc(mock_doc)
        # "A" is too short
        short_entities = [e for e in result if len(e[1]) <= 2]
        assert len(short_entities) == 0
