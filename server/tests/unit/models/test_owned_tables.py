"""Every table is user-owned or listed here with a reason (architecture §9).

A new table fails this test until it either carries UserOwnedMixin or gets a
row in ALLOWLIST. That is the entire mechanism: the decision cannot be
skipped, only made.
"""

import importlib
import pkgutil

import pytest
from sqlmodel import SQLModel

import app.modules
from app.models.base import UserOwnedMixin

pytestmark = pytest.mark.unit

# Table name -> why it carries no user_id. Delete a row when the table adopts the mixin.
ALLOWLIST: dict[str, str] = {
    "user": "the owner itself: every owned table's user_id points at it",
}


def _import_every_models_slot() -> None:
    for module in pkgutil.iter_modules(app.modules.__path__):
        try:
            importlib.import_module(f"app.modules.{module.name}.models")
        except ModuleNotFoundError as e:
            if e.name != f"app.modules.{module.name}.models":
                raise


def _subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    for sub in cls.__subclasses__():
        found.add(sub)
        found |= _subclasses(sub)
    return found


def _owned_tables() -> set[str]:
    return {
        getattr(cls, "__tablename__", None)
        for cls in _subclasses(SQLModel)
        if issubclass(cls, UserOwnedMixin)
        and cls is not UserOwnedMixin
        and getattr(cls, "__tablename__", None) in SQLModel.metadata.tables
    }


def test_every_table_is_user_owned_or_allowlisted():
    _import_every_models_slot()
    tables = set(SQLModel.metadata.tables)
    offenders = sorted(tables - _owned_tables() - set(ALLOWLIST))
    assert not offenders, (
        f"table(s) {offenders} carry no user_id: add UserOwnedMixin to the model, "
        "or add the table to ALLOWLIST in this file with the reason it is not user-owned"
    )


def test_allowlist_names_only_tables_that_exist():
    _import_every_models_slot()
    stale = sorted(set(ALLOWLIST) - set(SQLModel.metadata.tables))
    assert not stale, f"ALLOWLIST names table(s) {stale} that no models slot defines — remove the rows"


def test_allowlist_does_not_shadow_an_owned_table():
    _import_every_models_slot()
    shadowed = sorted(set(ALLOWLIST) & _owned_tables())
    assert not shadowed, f"table(s) {shadowed} carry UserOwnedMixin; remove them from ALLOWLIST"
