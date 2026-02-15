"""Basic tests for qwire_mock package."""

import pytest

from qwire_mock import __version__


def test_version() -> None:
    assert __version__ == "0.1.0"
