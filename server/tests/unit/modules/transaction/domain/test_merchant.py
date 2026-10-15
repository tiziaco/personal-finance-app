"""The merchant key (spec §4.2), pinned to fixed vectors."""

import pytest

from app.modules.transaction.domain import normalise_merchant

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("PAYPAL *NETFLIX 4029357733", "netflix"),
        ("NETFLIX.COM", "netflix"),
        ("Netflix", "netflix"),
        ("FEATHER - INSURANCE", "feather insurance"),
        ("REWE Markt GmbH 3112", "rewe markt"),
        ("REWE", "rewe"),
        ("Netflix International B.V.", "netflix international"),
        ("1&1 Telecom", "1&1 telecom"),
        ("Zettle_*Golda-delux", "golda delux"),
        ("SUMUP  *Café Kranzler", "café kranzler"),
        ("AMZNPrime DE*TX1FF8RV4", "amznprime"),
        ("Späti | Ref 99812", "späti"),
        ("  Bäckerei   Müller  ", "bäckerei müller"),
    ],
)
def test_vectors(raw, key):
    assert normalise_merchant(raw) == key


def test_different_businesses_stay_apart():
    assert normalise_merchant("REWE") != normalise_merchant("REWE Markt GmbH")
    assert normalise_merchant("Netflix") != normalise_merchant("Netflix International B.V.")


def test_only_a_reference_number_falls_back_to_the_folded_text():
    assert normalise_merchant("  123456 ") == "123456"


def test_ubr_prefix_becomes_uber():
    assert normalise_merchant("UBR* PENDING") == "uber pending"
