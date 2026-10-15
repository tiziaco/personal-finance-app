"""The import's rules: reading a bank's CSV and the values in it (spec §5.2, §5.4).

Pure: no ORM and no framework (R9). Messages on CsvFormatError and MappingProblem
are for logs and the API's message field; the web words each `reason` itself.
"""

import csv
import datetime as dt
import hashlib
import io
import re
from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 3000
SAMPLE_SIZE = 3
# A column is labelled a date or an amount column when this share of its non-empty cells parse.
FORMAT_SHARE = 0.8

IGNORE = "ignore"
FIELDS = ("date", "merchant", "amount", "description", "original_category", "recurring", IGNORE)
REQUIRED = ("date", "merchant", "amount")

COMMA_DECIMAL = "1.234,56"
DOT_DECIMAL = "1,234.56"
ISO = "iso"
# strptime format (or ISO) → the label the review shows. Order breaks ties: day-first before month-first.
DATE_FORMATS: dict[str, str] = {
    "%Y-%m-%d": "yyyy-mm-dd",
    ISO: "yyyy-mm-dd hh:mm",
    "%d.%m.%Y": "dd.mm.yyyy",
    "%d.%m.%y": "dd.mm.yy",
    "%d/%m/%Y": "dd/mm/yyyy",
    "%m/%d/%Y": "mm/dd/yyyy",
    "%Y/%m/%d": "yyyy/mm/dd",
    "%d-%m-%Y": "dd-mm-yyyy",
}

_DELIMITERS = ",;\t|"
_CENT = Decimal("0.01")
_MAX_AMOUNT = Decimal("1e10")  # NUMERIC(12,2)
_CURRENCY = re.compile(r"€|(?i:\beur\b)")
_AMOUNT_PATTERNS = {
    COMMA_DECIMAL: (re.compile(r"^(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$"), ".", ","),
    DOT_DECIMAL: (re.compile(r"^(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$"), ",", "."),
}
_TRUE = frozenset({"true", "yes", "ja", "si", "sì", "1", "x"})
_FALSE = frozenset({"false", "no", "nein", "0"})
_SHOWN = 40


class CsvFormatError(ValueError):
    """The file cannot be read as a bank export."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class MappingProblem:
    """Why a confirmed mapping cannot be used."""

    reason: str
    message: str


@dataclass(frozen=True)
class CsvRow:
    """A data line: its line number in the file and its cells, stripped, one per column.

    wide is True when the line has cells beyond the header that are not all empty; read_rows rejects it.
    """

    number: int
    cells: list[str]
    wide: bool = False


@dataclass(frozen=True)
class ParsedCsv:
    """A file read into its header and data rows."""

    columns: list[str]
    rows: list[CsvRow]


@dataclass(frozen=True)
class ColumnProfile:
    """What the review shows about a column."""

    name: str
    empty_rate: float
    date_format: Optional[str]
    amount_style: Optional[str]


@dataclass(frozen=True)
class ImportRow:
    """A row to save, read through a confirmed mapping. is_recurring None leaves it to the rule."""

    number: int
    date: dt.date
    merchant: str
    amount: Decimal
    description: Optional[str]
    original_category: Optional[str]
    is_recurring: Optional[bool]


@dataclass(frozen=True)
class Rejection:
    """A row left out, and why — shown to the user."""

    number: int
    reason: str


def decode(raw: bytes) -> str:
    """UTF-8 (a BOM dropped), else Windows-1252, which reads any byte string."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _widths(lines: list[str], delimiter: str) -> list[int]:
    return [len(row) for row in csv.reader(lines, delimiter=delimiter) if any(c.strip() for c in row)]


def sniff_delimiter(text: str) -> str:
    """The delimiter that splits the most lines into one common number (at least two) of fields.

    Not csv.Sniffer: on `15.01.2026;REWE;-12,50` both `;` and `,` occur once a
    line, and the Sniffer then prefers the comma.
    """
    lines = text.splitlines()[:50]
    best, best_score = ",", (0.0, 0)
    for delimiter in _DELIMITERS:
        widths = _widths(lines, delimiter)
        if not widths:
            continue
        width, count = Counter(widths).most_common(1)[0]
        score = (count / len(widths), width)
        if width >= 2 and score > best_score:
            best, best_score = delimiter, score
    return best


def _width(row: list[str]) -> int:
    """A line's width, not counting one trailing empty field (a delimiter that ends the line)."""
    return len(row) - 1 if len(row) > 1 and not row[-1] else len(row)


def parse(text: str) -> ParsedCsv:
    """Read a file into a header and rows, or raise CsvFormatError.

    Lines above the header (a bank's account summary) are skipped: the header is
    the first line whose width is the file's usual width. A line counts both as
    its width and as its width less a trailing empty field, so a header with no
    trailing delimiter still matches rows that end in one. Blank lines are
    skipped; short rows are padded; cells beyond the header are kept out of
    `cells` and flagged on the row. A trailing column with no name and no
    values — a delimiter ending every line — is dropped. A file the csv module
    cannot read is malformed.
    """
    try:
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=sniff_delimiter(text))
        records = [(reader.line_num, [c.strip() for c in row]) for row in reader if any(c.strip() for c in row)]
    except csv.Error as error:
        raise CsvFormatError("malformed", "The file isn't a well-formed CSV.") from error
    if not records:
        raise CsvFormatError("empty", "The file is empty.")
    counts: Counter[int] = Counter()
    for _, row in records:
        counts[len(row)] += 1
        counts[_width(row)] += 1
    width = counts.most_common(1)[0][0]
    if width < 2:
        raise CsvFormatError("no_header", "The file needs a header row and at least two columns.")
    start = next((i for i, (_, row) in enumerate(records) if _width(row) == width), None)
    if start is None:
        start = next(i for i, (_, row) in enumerate(records) if len(row) == width)
    header = records[start][1][:width]
    rows = [CsvRow(n, (row + [""] * width)[:width], wide=any(row[width:])) for n, row in records[start + 1 :]]
    if not header[-1] and all(not r.cells[-1] for r in rows):
        header.pop()
        rows = [CsvRow(r.number, r.cells[:-1], r.wide) for r in rows]
    if any(not name for name in header):
        raise CsvFormatError("unnamed_column", "Every column needs a name in the header row.")
    folded = [name.casefold() for name in header]
    if len(set(folded)) != len(folded):
        raise CsvFormatError("duplicate_column", "Two columns have the same name.")
    if not rows:
        raise CsvFormatError("no_rows", "The file has a header but no rows.")
    if len(rows) > MAX_ROWS:
        raise CsvFormatError("too_many_rows", f"The file has more than {MAX_ROWS} rows.")
    return ParsedCsv(columns=header, rows=rows)


def column_key(columns: list[str]) -> str:
    """A remembered mapping's key: sha256 of the names stripped, casefolded, sorted, joined by U+001F."""
    names = sorted(name.strip().casefold() for name in columns)
    return hashlib.sha256("\x1f".join(names).encode("utf-8")).hexdigest()


def parse_date(value: str, date_format: str) -> Optional[dt.date]:
    """The day `value` names in `date_format`, or None. A date-time keeps its date as written."""
    try:
        if date_format == ISO:
            return dt.datetime.fromisoformat(value).date()
        return dt.datetime.strptime(value, date_format).date()
    except ValueError:
        return None


def parse_amount(value: str, style: str) -> Optional[Decimal]:
    """`value` as a signed Decimal at two places in `style`, or None.

    Spaces, `€` and `EUR` are dropped; a trailing minus (`12,50-`) counts as a leading one.
    """
    text = _CURRENCY.sub("", value).replace("\u00a0", "").replace(" ", "")
    negative = False
    if text.endswith("-"):
        negative, text = True, text[:-1]
    elif text[:1] in ("+", "-"):
        negative, text = text[0] == "-", text[1:]
    pattern, thousands, decimal = _AMOUNT_PATTERNS[style]
    if not pattern.match(text):
        return None
    try:
        amount = Decimal(text.replace(thousands, "").replace(decimal, ".")).quantize(_CENT, ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if amount >= _MAX_AMOUNT:
        return None
    return -amount if negative else amount


def parse_recurring(value: str) -> Optional[bool]:
    """A recurring cell as the user's assertion, or None — blank or unrecognised — to let the rule decide."""
    folded = value.strip().casefold()
    if folded in _TRUE:
        return True
    if folded in _FALSE:
        return False
    return None


def best_date_format(values: list[str]) -> tuple[str, float]:
    """The format that parses the most non-empty values, and the share it parses. Ties go day-first."""
    filled = [v for v in values if v]
    order = list(DATE_FORMATS)
    if not filled:
        return order[0], 0.0
    best = max(order, key=lambda f: (sum(parse_date(v, f) is not None for v in filled), -order.index(f)))
    return best, sum(parse_date(v, best) is not None for v in filled) / len(filled)


def best_amount_style(values: list[str]) -> tuple[str, float]:
    """The style that parses the most non-empty values, and the share. A tie is the comma style if any value has a comma."""
    filled = [v for v in values if v]
    if not filled:
        return DOT_DECIMAL, 0.0
    counts = {style: sum(parse_amount(v, style) is not None for v in filled) for style in (COMMA_DECIMAL, DOT_DECIMAL)}
    if counts[COMMA_DECIMAL] == counts[DOT_DECIMAL]:
        style = COMMA_DECIMAL if any("," in v for v in filled) else DOT_DECIMAL
    else:
        style = max(counts, key=counts.__getitem__)
    return style, counts[style] / len(filled)


def profile_columns(parsed: ParsedCsv) -> list[ColumnProfile]:
    """Each column's empty rate, and its date format or amount style when one fits most of its cells."""
    profiles = []
    for index, name in enumerate(parsed.columns):
        values = [row.cells[index] for row in parsed.rows]
        date_format, date_share = best_date_format(values)
        style, amount_share = best_amount_style(values)
        is_date = date_share >= FORMAT_SHARE
        profiles.append(
            ColumnProfile(
                name=name,
                empty_rate=sum(not v for v in values) / len(values),
                date_format=DATE_FORMATS[date_format] if is_date else None,
                amount_style=style if not is_date and amount_share >= FORMAT_SHARE else None,
            )
        )
    return profiles


def pick_samples(parsed: ParsedCsv, size: int = SAMPLE_SIZE) -> list[CsvRow]:
    """Up to `size` rows covering as many non-empty columns as possible, returned in file order.

    Greedy: each pick covers the most columns no earlier pick filled, ties to
    the earliest row; slots left over take the next rows in file order.
    """
    chosen: list[int] = []
    covered: set[int] = set()
    for _ in range(size):
        best, gain = None, 0
        for i, row in enumerate(parsed.rows):
            if i in chosen:
                continue
            new = len({j for j, cell in enumerate(row.cells) if cell} - covered)
            if new > gain:
                best, gain = i, new
        if best is None:
            break
        chosen.append(best)
        covered |= {j for j, cell in enumerate(parsed.rows[best].cells) if cell}
    for i in range(len(parsed.rows)):
        if len(chosen) >= size:
            break
        if i not in chosen:
            chosen.append(i)
    return [parsed.rows[i] for i in sorted(chosen)]


def clean_proposal(columns: list[str], proposal: dict[str, str]) -> dict[str, str]:
    """A proposal made valid: every column present, known fields only, each field once (the first column keeps it)."""
    taken: set[str] = set()
    cleaned = {}
    for column in columns:
        field = proposal.get(column, IGNORE)
        if field not in FIELDS or (field != IGNORE and field in taken):
            field = IGNORE
        taken.add(field)
        cleaned[column] = field
    return cleaned


def mapping_problem(columns: list[str], mapping: dict[str, str]) -> Optional[MappingProblem]:
    """Why a confirmed mapping cannot be used, or None."""
    if set(mapping) - set(columns):
        return MappingProblem("unknown_column", "The mapping names a column the file does not have.")
    if any(field not in FIELDS for field in mapping.values()):
        return MappingProblem("unknown_field", "The mapping uses an unknown field.")
    used = [field for field in mapping.values() if field != IGNORE]
    if len(used) != len(set(used)):
        return MappingProblem("field_twice", "Each field can be mapped to one column only.")
    if any(field not in used for field in REQUIRED):
        return MappingProblem("missing_required", "Map a date, a merchant and an amount.")
    return None


def _shown(value: str) -> str:
    return value if len(value) <= _SHOWN else value[: _SHOWN - 1] + "…"


def read_rows(parsed: ParsedCsv, mapping: dict[str, str]) -> tuple[list[ImportRow], list[Rejection]]:
    """Every row through a valid mapping: the rows to save and the rows rejected, in file order.

    The date format and amount style are the best for the mapped column. A row
    is rejected for cells beyond the header, an unreadable date, an unreadable
    amount or an empty merchant, checked in that order. Text is cut to the
    column sizes.
    """
    index = {field: parsed.columns.index(column) for column, field in mapping.items() if field != IGNORE}

    def cell(row: CsvRow, field: str) -> str:
        return row.cells[index[field]] if field in index else ""

    date_format, _ = best_date_format([cell(r, "date") for r in parsed.rows])
    style, _ = best_amount_style([cell(r, "amount") for r in parsed.rows])
    rows: list[ImportRow] = []
    rejected: list[Rejection] = []
    for row in parsed.rows:
        if row.wide:
            rejected.append(Rejection(row.number, "more cells than the header"))
            continue
        raw_date, raw_amount, merchant = cell(row, "date"), cell(row, "amount"), cell(row, "merchant")
        date = parse_date(raw_date, date_format)
        if date is None:
            rejected.append(Rejection(row.number, f"unreadable date “{_shown(raw_date)}”"))
            continue
        amount = parse_amount(raw_amount, style)
        if amount is None:
            rejected.append(Rejection(row.number, f"unreadable amount “{_shown(raw_amount)}”"))
            continue
        if not merchant:
            rejected.append(Rejection(row.number, "no merchant"))
            continue
        rows.append(
            ImportRow(
                number=row.number,
                date=date,
                merchant=merchant[:255],
                amount=amount,
                description=cell(row, "description")[:1000] or None,
                original_category=cell(row, "original_category")[:255] or None,
                is_recurring=parse_recurring(cell(row, "recurring")) if "recurring" in index else None,
            )
        )
    return rows, rejected
