"""The dates a transaction can carry and still be analysed."""

import datetime as dt

# The dates analytics covers. An explicit bound outside them is a 422; a row outside them
# would be left out of every analysis, so the import rejects it instead of saving it.
MIN_DATE = dt.date(1900, 1, 1)
MAX_DATE = dt.date(2100, 12, 31)
