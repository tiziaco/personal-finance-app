"""Well-known merchants and their category, ported from legacy v1.0 (German/European).

Keys are merchant keys — already normalised, so they match the import's keys
exactly; tests/unit/agents/transaction_labeler/test_known_merchants.py holds
them to that. Values are category slugs.
"""

# Generic or bank names that mislabel at 0.95 (user decision, 15 Oct 2026). Removed deliberately; "db" stays.
EXCLUDED = frozenset(
    {"bank", "sparkasse", "ing", "n26", "gas", "uni", "sky", "spa", "gym", "sos", "deutsche bank", "comdirect"}
)

KNOWN_MERCHANTS: dict[str, str] = {
    "netflix": "leisure_entertainment",
    "spotify": "leisure_entertainment",
    "prime video": "leisure_entertainment",
    "amazon prime": "leisure_entertainment",
    "apple tv": "leisure_entertainment",
    "disney": "leisure_entertainment",
    "wolt": "food_delivery",
    "deliveroo": "food_delivery",
    "uber eats": "food_delivery",
    "rewe": "food_groceries",
    "lidl": "food_groceries",
    "edeka": "food_groceries",
    "aldi": "food_groceries",
    "aldi nord": "food_groceries",
    "aldi süd": "food_groceries",
    "penny": "food_groceries",
    "netto": "food_groceries",
    "metro": "food_groceries",
    "kaufland": "food_groceries",
    "biomarkt": "food_groceries",
    "bio company": "food_groceries",
    "db": "transportation",
    "bvg": "transportation",
    "deutsche bahn": "transportation",
    "deutsche post": "transportation",
    "dhl": "transportation",
    "flixbus": "transportation",
    "taxi": "transportation",
    "uber": "transportation",
    "bolt": "transportation",
    "tier": "transportation",
    "voi": "transportation",
    "lyft": "transportation",
    "shell": "transportation",
    "aral": "transportation",
    "esso": "transportation",
    "bp": "transportation",
    "total": "transportation",
    "ev charging": "transportation",
    "mc donald": "bars_restaurants",
    "mcdonald s": "bars_restaurants",
    "burger king": "bars_restaurants",
    "starbucks": "bars_restaurants",
    "subway": "bars_restaurants",
    "pizza hut": "bars_restaurants",
    "dominos": "bars_restaurants",
    "rueya": "bars_restaurants",
    "klunkerkranich": "bars_restaurants",
    "renate": "bars_restaurants",
    "sage": "bars_restaurants",
    "paloma": "bars_restaurants",
    "amazon": "shopping",
    "amzn mktp": "shopping",
    "zalando": "shopping",
    "ebay": "shopping",
    "dm": "shopping",
    "rossmann": "shopping",
    "h&m": "shopping",
    "zara": "shopping",
    "primark": "shopping",
    "obi": "shopping",
    "hornbach": "shopping",
    "baumarkt": "shopping",
    "poco": "shopping",
    "ikea": "shopping",
    "vattenfall": "household_utilities",
    "stadtwerke": "household_utilities",
    "eon": "household_utilities",
    "eon energy": "household_utilities",
    "strom": "household_utilities",
    "wasser": "household_utilities",
    "telekom": "household_utilities",
    "vodafone": "household_utilities",
    "o2": "household_utilities",
    "1&1": "household_utilities",
    "congstar": "household_utilities",
    "fraenk": "household_utilities",
    "apotheke": "healthcare_drug_stores",
    "pharmacy": "healthcare_drug_stores",
    "zahnarzt": "healthcare_drug_stores",
    "arzt": "healthcare_drug_stores",
    "dentist": "healthcare_drug_stores",
    "krankenhaus": "healthcare_drug_stores",
    "kino": "leisure_entertainment",
    "cinema": "leisure_entertainment",
    "theater": "leisure_entertainment",
    "fitnessstudio": "leisure_entertainment",
    "decathlon": "leisure_entertainment",
    "museum": "leisure_entertainment",
    "zoo": "leisure_entertainment",
    "fitness": "leisure_entertainment",
    "playtomic": "leisure_entertainment",
    "booking": "travel_holidays",
    "airbnb": "travel_holidays",
    "hotel": "travel_holidays",
    "hilton": "travel_holidays",
    "marriott": "travel_holidays",
    "ibis": "travel_holidays",
    "lufthansa": "travel_holidays",
    "easyjet": "travel_holidays",
    "ryanair": "travel_holidays",
    "tui": "travel_holidays",
    "allianz": "insurances",
    "axa": "insurances",
    "debeka": "insurances",
    "ergo": "insurances",
    "versicherung": "insurances",
    "aok": "insurances",
    "feather": "insurances",
    "vhs": "education",
    "universität": "education",
    "kurse": "education",
    "schule": "education",
    "udemy": "education",
    "coursera": "education",
    "savings": "savings_investments",
    "instant savings": "savings_investments",
}

# Longest names first, so "amazon prime" wins over a shorter name inside it.
_BY_LENGTH = sorted(KNOWN_MERCHANTS.items(), key=lambda item: -len(item[0].split()))


def match_known(key: str) -> str | None:
    """The slug of the first known merchant whose words appear whole and in order in `key`, or None.

    Whole words, not substrings: "dm" matches "dm drogerie" but not "dmitri".
    """
    tokens = key.split()
    for known, slug in _BY_LENGTH:
        words = known.split()
        if any(tokens[i : i + len(words)] == words for i in range(len(tokens) - len(words) + 1)):
            return slug
    return None
