"""Ensure a QApplication exists for every test (some tests build QObjects directly)."""

import pytest


@pytest.fixture(autouse=True)
def _ensure_qapp(qapp):
    return qapp
