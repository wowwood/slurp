"""
conftest.py defines the fixtures and settings that pytest uses when running the test suite.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-huge-dl",
        action="store_true",
        default=False,
        help="run tests with huge download implications",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-huge-dl"):
        # --run-huge-dl given in cli: do not skip slow tests
        return
    skip_huge = pytest.mark.skip(reason="skipping huge download")
    for item in items:
        if "huge_dl" in item.keywords:
            item.add_marker(skip_huge)
