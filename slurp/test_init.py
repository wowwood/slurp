from flask import Flask

from slurp import create_app


def test_create_app():
    assert isinstance(create_app(), Flask)
