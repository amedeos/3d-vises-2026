"""Shared fixtures: every model package exposes the same export interface.

`<model>.export` provides printable_parts(), colour_parts(), plates(), PLANNED_M600,
THIN_FEATURES and GAPS. Add a model to MODELS when it exists.
"""

import importlib
from functools import cache

MODELS = ["tux_clip"]


@cache
def export_module(model: str):
    return importlib.import_module(f"{model}.export")


@cache
def parts(model: str):
    return export_module(model).printable_parts()


@cache
def colour_parts(model: str):
    return export_module(model).colour_parts()


@cache
def plates(model: str):
    return export_module(model).plates()


def all_parts() -> list[tuple[str, str]]:
    return [(model, name) for model in MODELS for name in parts(model)]


def all_plates() -> list[tuple[str, str]]:
    return [(model, name) for model in MODELS for name in plates(model)]
