"""Import routes against a real database. The two agents are stubbed."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from app.core.limiter import limiter
from app.main import app
from app.modules.transaction.imports.domain import column_key
from app.modules.transaction.imports.models import HeldUpload, MappingProfile

pytestmark = pytest.mark.integration

BASE = "/api/v1/transactions/imports"
GERMAN = (
    "Buchungsdatum;Empfaenger;Verwendungszweck;Betrag\n"
    "15.01.2026;REWE Markt GmbH;Einkauf;-1.234,56\n"
    "16.01.2026;Arbeitgeber;Gehalt;2.450,00\n"
)
GERMAN_MAPPING = {
    "Buchungsdatum": "date",
    "Empfaenger": "merchant",
    "Verwendungszweck": "description",
    "Betrag": "amount",
}


@pytest.fixture(autouse=True)
def fresh_limits():
    """The limiter's memory outlives a test; 10 uploads a minute would trip across the file."""
    limiter.reset()


@pytest.fixture
def propose():
    with patch(
        "app.modules.transaction.imports.service.propose_mapping", new=AsyncMock(return_value=GERMAN_MAPPING)
    ) as stub:
        yield stub


async def upload(client, content: str | bytes, name: str = "konto.csv"):
    body = content.encode("utf-8") if isinstance(content, str) else content
    return await client.post(BASE, files={"file": (name, body, "text/csv")})


class TestUpload:
    async def test_unauthenticated_is_401(self, client):
        assert (await upload(client, GERMAN)).status_code == 401

    async def test_returns_the_preview(self, authenticated_client, propose):
        response = await upload(authenticated_client, GERMAN)
        assert response.status_code == 201
        body = response.json()
        assert uuid.UUID(body["upload_id"])
        assert (body["filename"], body["row_count"], body["mapping_source"]) == ("konto.csv", 2, "proposed")
        assert [(c["name"], c["proposed_field"]) for c in body["columns"]] == list(GERMAN_MAPPING.items())
        assert body["columns"][0]["date_format"] == "dd.mm.yyyy"
        assert body["columns"][3]["amount_style"] == "1.234,56"
        assert body["sample_rows"][0] == ["15.01.2026", "REWE Markt GmbH", "Einkauf", "-1.234,56"]
        hints = propose.await_args.args[0]
        assert [h.name for h in hints] == list(GERMAN_MAPPING)

    async def test_reads_windows_1252(self, authenticated_client, propose):
        content = GERMAN.replace("Empfaenger", "Empfänger").encode("cp1252")
        response = await upload(authenticated_client, content)
        assert response.status_code == 201
        assert response.json()["columns"][1]["name"] == "Empfänger"

    async def test_the_agent_failing_leaves_every_column_to_the_user(
        self, authenticated_client, propose, db_session, test_user
    ):
        propose.return_value = None
        body = (await upload(authenticated_client, GERMAN)).json()
        held = (
            (await db_session.execute(select(HeldUpload.id).where(HeldUpload.user_id == test_user.id))).scalars().all()
        )
        assert held == [uuid.UUID(body["upload_id"])]
        assert body["mapping_source"] == "none"
        assert {c["proposed_field"] for c in body["columns"]} == {"ignore"}

    @pytest.mark.parametrize(
        ("name", "content", "reason"),
        [
            ("notes.txt", GERMAN, "not_csv"),
            ("konto.csv", "", "empty"),
            ("konto.csv", "a;b\n", "no_rows"),
            ("konto.csv", "Betrag;betrag\n1;2\n", "duplicate_column"),
            ("konto.csv", 'd,m,a\n"' + "x" * 140_000, "malformed"),
        ],
    )
    async def test_refusals_carry_a_reason(self, authenticated_client, propose, name, content, reason):
        response = await upload(authenticated_client, content, name)
        assert response.status_code == 422
        assert response.json()["error"] == "INVALID_IMPORT_FILE"
        assert response.json()["details"] == {"reason": reason}

    async def test_more_than_5_mb_is_refused(self, authenticated_client, propose):
        response = await upload(authenticated_client, b"a,b\n" + b"1,2\n" * (1_400_000))
        assert response.status_code == 422
        assert response.json()["details"] == {"reason": "too_large"}

    async def test_an_uppercase_extension_is_fine(self, authenticated_client, propose):
        assert (await upload(authenticated_client, GERMAN, "KONTO.CSV")).status_code == 201

    async def test_a_new_upload_replaces_the_held_one(self, authenticated_client, propose, db_session, test_user):
        await upload(authenticated_client, GERMAN)
        second = (await upload(authenticated_client, GERMAN)).json()
        held = (
            (await db_session.execute(select(HeldUpload.id).where(HeldUpload.user_id == test_user.id))).scalars().all()
        )
        assert held == [uuid.UUID(second["upload_id"])]

    async def test_the_eleventh_upload_in_a_minute_is_429(self, authenticated_client, propose, monkeypatch):
        monkeypatch.setattr(
            app.state, "limiter", limiter, raising=False
        )  # the lifespan sets it; tests skip the lifespan
        for _ in range(10):
            assert (await upload(authenticated_client, GERMAN)).status_code == 201
        assert (await upload(authenticated_client, GERMAN)).status_code == 429

    async def test_a_remembered_mapping_matches_headers_by_case_and_spacing(
        self, authenticated_client, propose, db_session, test_user
    ):
        db_session.add(
            MappingProfile(user_id=test_user.id, column_key=column_key(list(GERMAN_MAPPING)), mapping=GERMAN_MAPPING)
        )
        await db_session.flush()
        shouted = GERMAN.replace(
            "Buchungsdatum;Empfaenger;Verwendungszweck;Betrag", "BUCHUNGSDATUM; empfaenger;VERWENDUNGSZWECK;Betrag "
        )
        body = (await upload(authenticated_client, shouted)).json()
        assert body["mapping_source"] == "remembered"
        assert [c["proposed_field"] for c in body["columns"]] == ["date", "merchant", "description", "amount"]
        propose.assert_not_awaited()
