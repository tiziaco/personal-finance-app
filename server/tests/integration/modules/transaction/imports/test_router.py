"""Import routes against a real database. The two agents are stubbed."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import update
from sqlmodel import select

from app.agents.transaction_labeler import Label, LabelResult
from app.core.limiter import limiter
from app.main import app
from app.modules.transaction.imports.domain import column_key
from app.modules.transaction.imports.models import HeldUpload, MappingProfile
from app.modules.transaction.models import Transaction

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
            ("konto.csv", "Datum;Betrag\n15.01.2026;-3,00\n".encode("utf-16"), "malformed"),
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


def labelling(
    slug: str = "shopping", confidence: float = 0.8, fail: frozenset = frozenset(), all_failed: bool = False
):
    """A stand-in for the labeller: every merchant gets `slug`, except the keys in `fail`."""

    async def fake(merchants, categories, *, user_id, upload_id):
        labels = {m.key: Label("miscellaneous", 0.3) if m.key in fail else Label(slug, confidence) for m in merchants}
        fallback = {m.key for m in merchants if m.key in fail}
        return LabelResult(labels=labels, fallback_keys=fallback, all_failed=all_failed)

    return fake


@pytest.fixture
def labeller():
    with patch("app.modules.transaction.imports.service.label", new=labelling()) as stub:
        yield stub


async def confirm(client, upload_id: str, mapping=GERMAN_MAPPING):
    return await client.post(f"{BASE}/{upload_id}/confirm", json={"mapping": mapping})


async def upload_id(client, content: str = GERMAN) -> str:
    response = await upload(client, content)
    assert response.status_code == 201, response.text
    return response.json()["upload_id"]


async def rows(db_session, user_id) -> list[Transaction]:
    statement = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.date)
        .execution_options(populate_existing=True)
    )
    return list((await db_session.execute(statement)).scalars())


class TestConfirm:
    async def test_unauthenticated_is_401(self, client):
        assert (await confirm(client, str(uuid.uuid4()))).status_code == 401

    async def test_imports_and_categorises(self, authenticated_client, propose, labeller, db_session, test_user):
        response = await confirm(authenticated_client, await upload_id(authenticated_client))
        assert response.status_code == 200
        assert response.json() == {"imported": 2, "skipped_duplicates": 0, "uncategorised": 0, "rejected": []}
        saved = await rows(db_session, test_user.id)
        assert [(t.merchant, str(t.amount), t.description, t.category, t.confidence) for t in saved] == [
            ("REWE Markt GmbH", "-1234.56", "Einkauf", "shopping", 0.8),
            ("Arbeitgeber", "2450.00", "Gehalt", "shopping", 0.8),
        ]
        assert [t.recurring_source for t in saved] == ["detected", "detected"]
        held = (await db_session.execute(select(HeldUpload).where(HeldUpload.user_id == test_user.id))).scalars().all()
        assert held == []
        profile = (await db_session.execute(select(MappingProfile))).scalars().one()
        assert profile.mapping == GERMAN_MAPPING

    async def test_rejected_rows_are_reported(self, authenticated_client, propose, labeller):
        content = GERMAN + "31.02.2026;Bad;;-1,00\n"
        response = await confirm(authenticated_client, await upload_id(authenticated_client, content))
        assert response.json()["imported"] == 2
        assert response.json()["rejected"] == [{"row": 4, "reason": "unreadable date \u201c31.02.2026\u201d"}]

    async def test_reimporting_the_same_file_imports_nothing(self, authenticated_client, propose, labeller):
        await confirm(authenticated_client, await upload_id(authenticated_client))
        response = await confirm(authenticated_client, await upload_id(authenticated_client))
        assert response.json() == {"imported": 0, "skipped_duplicates": 2, "uncategorised": 0, "rejected": []}

    async def test_twin_rows_in_one_file_both_import(self, authenticated_client, propose, labeller):
        content = GERMAN + "15.01.2026;REWE Markt GmbH;Einkauf;-1.234,56\n"
        response = await confirm(authenticated_client, await upload_id(authenticated_client, content))
        assert response.json()["imported"] == 3

    async def test_a_second_confirm_is_404(self, authenticated_client, propose, labeller, db_session, test_user):
        held = await upload_id(authenticated_client)
        assert (await confirm(authenticated_client, held)).status_code == 200
        second = await confirm(authenticated_client, held)
        assert second.status_code == 404
        assert second.json()["error"] == "IMPORT_UPLOAD_NOT_FOUND"
        assert len(await rows(db_session, test_user.id)) == 2

    async def test_an_expired_upload_is_404(self, authenticated_client, propose, labeller, db_session):
        held = await upload_id(authenticated_client)
        await db_session.execute(update(HeldUpload).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
        assert (await confirm(authenticated_client, held)).status_code == 404

    async def test_another_users_upload_is_404(self, authenticated_client, labeller, db_session, other_user):
        theirs = HeldUpload(
            user_id=other_user.id, content=GERMAN, expires_at=datetime.now(UTC) + timedelta(minutes=30)
        )
        db_session.add(theirs)
        await db_session.flush()
        assert (await confirm(authenticated_client, str(theirs.id))).status_code == 404
        still = (await db_session.execute(select(HeldUpload.id).where(HeldUpload.user_id == other_user.id))).scalars()
        assert list(still) == [theirs.id]

    async def test_a_replaced_upload_is_404(self, authenticated_client, propose, labeller):
        first = await upload_id(authenticated_client)
        second = await upload_id(authenticated_client)
        assert (await confirm(authenticated_client, first)).status_code == 404
        assert (await confirm(authenticated_client, second)).status_code == 200

    async def test_a_bad_mapping_is_422(self, authenticated_client, propose, labeller):
        mapping = {**GERMAN_MAPPING, "Betrag": "ignore"}
        response = await confirm(authenticated_client, await upload_id(authenticated_client), mapping)
        assert response.status_code == 422
        assert response.json()["error"] == "INVALID_IMPORT_MAPPING"
        assert response.json()["details"] == {"reason": "missing_required"}

    async def test_categorisation_down_is_503_and_keeps_the_upload(
        self, authenticated_client, propose, db_session, test_user
    ):
        held = await upload_id(authenticated_client)
        with patch("app.modules.transaction.imports.service.label", new=labelling(all_failed=True)):
            response = await confirm(authenticated_client, held)
        assert response.status_code == 503
        assert response.json()["error"] == "CATEGORISATION_UNAVAILABLE"
        assert await rows(db_session, test_user.id) == []
        with patch("app.modules.transaction.imports.service.label", new=labelling()):
            assert (await confirm(authenticated_client, held)).json()["imported"] == 2

    async def test_a_partial_failure_is_counted(self, authenticated_client, propose, db_session, test_user):
        held = await upload_id(authenticated_client)
        with patch("app.modules.transaction.imports.service.label", new=labelling(fail=frozenset({"rewe markt"}))):
            response = await confirm(authenticated_client, held)
        assert response.json()["uncategorised"] == 1
        rewe = [t for t in await rows(db_session, test_user.id) if t.merchant_key == "rewe markt"][0]
        assert (rewe.category, rewe.confidence) == ("miscellaneous", 0.3)

    async def test_a_mapped_recurring_column_is_the_users(
        self, authenticated_client, propose, labeller, db_session, test_user
    ):
        content = "Datum;Empfaenger;Betrag;Abo\n15.01.2026;Gym;-20,00;x\n16.01.2026;Kiosk;-2,00;\n17.01.2026;Bar;-3,00;nein\n"
        mapping = {"Datum": "date", "Empfaenger": "merchant", "Betrag": "amount", "Abo": "recurring"}
        await confirm(authenticated_client, await upload_id(authenticated_client, content), mapping)
        saved = {t.merchant: (t.is_recurring, t.recurring_source) for t in await rows(db_session, test_user.id)}
        assert saved == {"Gym": (True, "user"), "Kiosk": (False, "detected"), "Bar": (False, "detected")}

    async def test_the_eleventh_confirm_in_a_minute_is_429(self, authenticated_client, monkeypatch):
        monkeypatch.setattr(app.state, "limiter", limiter, raising=False)
        for _ in range(10):
            assert (await confirm(authenticated_client, str(uuid.uuid4()))).status_code == 404
        assert (await confirm(authenticated_client, str(uuid.uuid4()))).status_code == 429
