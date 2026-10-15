"""The dates a transaction can carry and still be analysed."""

import datetime as dt

# The dates analytics covers. A row outside them would be left out of every analysis.
MIN_DATE = dt.date(1900, 1, 1)
MAX_DATE = dt.date(2100, 12, 31)
