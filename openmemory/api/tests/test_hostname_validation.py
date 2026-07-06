"""Tests for Sysmo hostname validation (S + 4 digits)."""

import re

import pytest

from app.utils.hostname_validation import (
    SYSMO_HOSTNAME_MESSAGE,
    normalize_sysmo_hostname,
    require_sysmo_hostname,
)


class TestNormalizeSysmoHostname:
    def test_valid_uppercase(self):
        assert normalize_sysmo_hostname("S0281") == "S0281"

    def test_valid_lowercase_normalized(self):
        assert normalize_sysmo_hostname("s0293") == "S0293"

    def test_rejects_suffix_with_name(self):
        assert normalize_sysmo_hostname("S0281 - Ana Paula") is None

    def test_rejects_desktop_style(self):
        assert normalize_sysmo_hostname("DESKTOP-01") is None

    def test_rejects_wrong_digit_count(self):
        assert normalize_sysmo_hostname("S281") is None
        assert normalize_sysmo_hostname("S02810") is None


class TestRequireSysmoHostname:
    def test_raises_with_message(self):
        with pytest.raises(ValueError, match=re.escape(SYSMO_HOSTNAME_MESSAGE)):
            require_sysmo_hostname("invalid")
