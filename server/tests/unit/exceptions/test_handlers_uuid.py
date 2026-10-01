"""A ServiceError whose context carries a uuid.UUID keeps its status; the id is text in `details`."""

import uuid

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.exceptions.base import AuthorizationError, ServiceError
from app.exceptions.handlers import service_exception_handler

pytestmark = pytest.mark.unit

USER_ID = uuid.UUID("0199a8b0-0000-7000-8000-000000000001")


def test_uuid_in_context_is_served_as_text():
    app = FastAPI()
    app.add_exception_handler(ServiceError, service_exception_handler)

    @app.get("/denied")
    async def denied() -> None:
        raise AuthorizationError("no", user_id=USER_ID)

    response = TestClient(app, raise_server_exceptions=False).get("/denied")

    assert response.status_code == 403
    assert response.json()["details"] == {"user_id": str(USER_ID)}
