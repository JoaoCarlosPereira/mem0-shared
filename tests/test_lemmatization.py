"""Tests for mem0.utils.lemmatization — lemmatize_for_bm25."""

from unittest.mock import MagicMock, patch

import pytest

from mem0.utils.lemmatization import lemmatize_for_bm25


class TestLemmatizeForBM25:
    def test_returns_original_when_spacy_unavailable(self):
        with patch("mem0.utils.spacy_models.get_nlp_lemma", return_value=None):
            result = lemmatize_for_bm25("hello world")
            assert result == "hello world"

    def test_returns_lemmatized_text(self):
        mock_token1 = MagicMock()
        mock_token1.text = "running"
        mock_token1.lemma_ = "run"
        mock_token1.is_punct = False
        mock_token1.is_stop = False
        mock_token1.isalnum = MagicMock(return_value=True)

        mock_token2 = MagicMock()
        mock_token2.text = "fast"
        mock_token2.lemma_ = "fast"
        mock_token2.is_punct = False
        mock_token2.is_stop = False
        mock_token2.isalnum = MagicMock(return_value=True)

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_token1, mock_token2]))

        mock_nlp = MagicMock()
        mock_nlp.return_value = mock_doc

        with patch("mem0.utils.spacy_models.get_nlp_lemma", return_value=mock_nlp):
            result = lemmatize_for_bm25("running fast")
            assert isinstance(result, str)

    def test_filters_punctuation(self):
        mock_token = MagicMock()
        mock_token.text = "hello,"
        mock_token.lemma_ = "hello"
        mock_token.is_punct = True
        mock_token.is_stop = False

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_token]))

        mock_nlp = MagicMock()
        mock_nlp.return_value = mock_doc

        with patch("mem0.utils.spacy_models.get_nlp_lemma", return_value=mock_nlp):
            result = lemmatize_for_bm25("hello, world")
            # "hello," should be skipped due to is_punct
            assert "hello," not in result

    def test_filters_stop_words(self):
        mock_token = MagicMock()
        mock_token.text = "the"
        mock_token.lemma_ = "the"
        mock_token.is_punct = False
        mock_token.is_stop = True
        mock_token.isalnum = MagicMock(return_value=True)

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_token]))

        mock_nlp = MagicMock()
        mock_nlp.return_value = mock_doc

        with patch("mem0.utils.spacy_models.get_nlp_lemma", return_value=mock_nlp):
            result = lemmatize_for_bm25("the cat")
            assert "the" not in result

    def test_adds_ing_forms(self):
        """Original -ing forms are added alongside lemmas when different."""
        mock_token = MagicMock()
        mock_token.text = "meeting"
        mock_token.lemma_ = "meet"
        mock_token.is_punct = False
        mock_token.is_stop = False
        mock_token.isalnum = MagicMock(return_value=True)
        pass
        pass

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_token]))

        mock_nlp = MagicMock()
        mock_nlp.return_value = mock_doc

        with patch("mem0.utils.spacy_models.get_nlp_lemma", return_value=mock_nlp):
            result = lemmatize_for_bm25("meeting")
            # Should contain both "meet" and "meeting"
            assert "meet" in result
            assert "meeting" in result

    def test_ing_not_added_when_same_as_lemma(self):
        """Original -ing not added if same as lemma."""
        mock_token = MagicMock()
        mock_token.text = "running"
        mock_token.lemma_ = "running"  # same
        mock_token.is_punct = False
        mock_token.is_stop = False
        mock_token.isalnum = MagicMock(return_value=True)
        pass
        pass

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_token]))

        mock_nlp = MagicMock()
        mock_nlp.return_value = mock_doc

        with patch("mem0.utils.spacy_models.get_nlp_lemma", return_value=mock_nlp):
            result = lemmatize_for_bm25("running")
            # "running" is lemma, so it's added once (not duplicated)
            assert "running" in result

    def test_non_alnum_lemma_skipped(self):
        """Tokens with a non-alphanumeric lemma are skipped."""
        mock_token = MagicMock()
        mock_token.text = "test"
        mock_token.lemma_ = "test!"
        mock_token.is_punct = False
        mock_token.is_stop = False

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_token]))

        mock_nlp = MagicMock()
        mock_nlp.return_value = mock_doc

        with patch("mem0.utils.spacy_models.get_nlp_lemma", return_value=mock_nlp):
            result = lemmatize_for_bm25("test")
            assert "test!" not in result

    def test_returns_lowercase(self):
        """Input text is lowercased before processing."""
        mock_token = MagicMock()
        mock_token.text = "hello"
        mock_token.lemma_ = "hello"
        mock_token.is_punct = False
        mock_token.is_stop = False
        mock_token.isalnum = MagicMock(return_value=True)
        pass
        pass

        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_token]))

        mock_nlp = MagicMock()
        mock_nlp.return_value = mock_doc

        with patch("mem0.utils.spacy_models.get_nlp_lemma", return_value=mock_nlp):
            result = lemmatize_for_bm25("HELLO")
            # nlp is called with lowercased text
            mock_nlp.assert_called_once_with("hello")

    def test_empty_string(self):
        with patch("mem0.utils.spacy_models.get_nlp_lemma", return_value=None):
            result = lemmatize_for_bm25("")
            assert result == ""

    def test_whitespace_only(self):
        with patch("mem0.utils.spacy_models.get_nlp_lemma", return_value=None):
            result = lemmatize_for_bm25("   ")
            assert result == "   "
