"""The merchant key: the merchant text with a bank's noise removed (docs/data-model/transaction.md, D7)."""

import re
import unicodedata

_PROCESSOR_PREFIX = re.compile(r"^(?:paypal|sumup|lsp|spc|sq)\s*\*\s*|^zettle_\*?\s*")
_UBER_PREFIX = re.compile(r"^ubr\s*\*\s*")
_DOMAIN_SUFFIX = re.compile(r"\.(?:co\.uk|com|de|eu|it)$")
_LEGAL_FORMS = frozenset({"gmbh", "ag", "se", "kg", "bv", "b.v", "ltd", "inc", "srl", "spa"})
_PUNCTUATION = re.compile(r"[^\w&]|_")


def normalise_merchant(raw: str) -> str:
    """The key that groups one merchant's rows.

    Casefolded, with a payment processor's prefix, a web domain, a legal form and
    trailing reference numbers (a token with three or more digits) removed, and
    punctuation other than `&` turned into spaces. Conservative by design: it
    removes noise and never guesses that two names are one business. A change
    here changes stored keys, so it needs a backfill revision.
    """
    folded = unicodedata.normalize("NFKC", raw).casefold()
    text = folded.split("|", 1)[0].strip()
    text = _UBER_PREFIX.sub("uber ", text)
    text = _PROCESSOR_PREFIX.sub("", text)
    tokens = text.split()
    while tokens:
        last = _DOMAIN_SUFFIX.sub("", tokens[-1])
        if not last or sum(c.isdigit() for c in last) >= 3 or last.rstrip(".") in _LEGAL_FORMS:
            tokens.pop()
            continue
        tokens[-1] = last
        break
    key = " ".join(_PUNCTUATION.sub(" ", " ".join(tokens)).split())
    return key or " ".join(folded.split())
