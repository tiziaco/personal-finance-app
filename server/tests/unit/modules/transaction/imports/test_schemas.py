"""The API's field list and the domain's are one list."""

import pytest

from app.modules.transaction.imports.domain import FIELDS
from app.modules.transaction.imports.schemas import ImportField

pytestmark = pytest.mark.unit


def test_fields_agree():
    assert set(FIELDS) == {f.value for f in ImportField}
