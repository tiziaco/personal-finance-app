"""Reading a bank's CSV (spec §5.2, §5.4). Pure: no database, no model."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.transaction.imports.domain import (
    COMMA_DECIMAL,
    DOT_DECIMAL,
    MAX_ROWS,
    CsvFormatError,
    clean_proposal,
    column_key,
    decode,
    mapping_problem,
    parse,
    parse_amount,
    parse_date,
    parse_recurring,
    pick_samples,
    profile_columns,
    read_rows,
    sniff_delimiter,
)

pytestmark = pytest.mark.unit

GERMAN = (
    "Buchungsdatum;Empfaenger;Verwendungszweck;Betrag\n"
    "15.01.2026;REWE Markt GmbH;Einkauf;-1.234,56\n"
    "16.01.2026;Arbeitgeber;Gehalt;2.450,00\n"
    "17.01.2026;Kiosk;;12,50-\n"
)
N26 = '"Date","Payee","Amount (EUR)"\n"2026-01-15","Spotify","-9.99"\n"2026-01-16","Employer","1,204.00"\n'
GERMAN_MAPPING = {
    "Buchungsdatum": "date",
    "Empfaenger": "merchant",
    "Verwendungszweck": "description",
    "Betrag": "amount",
}


class TestDecode:
    def test_utf8_and_its_bom(self):
        assert decode("Späti".encode()) == "Späti"
        assert decode("\ufeffDate".encode()) == "Date"

    def test_windows_1252_when_not_utf8(self):
        assert decode("Empfänger".encode("cp1252")) == "Empfänger"


class TestParse:
    def test_semicolon_wins_over_a_decimal_comma(self):
        assert sniff_delimiter(GERMAN) == ";"

    @pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
    def test_each_delimiter(self, delimiter):
        assert sniff_delimiter(f"a{delimiter}b\n1{delimiter}2\n") == delimiter

    def test_header_and_stripped_cells(self):
        parsed = parse(N26)
        assert parsed.columns == ["Date", "Payee", "Amount (EUR)"]
        assert [r.cells for r in parsed.rows] == [
            ["2026-01-15", "Spotify", "-9.99"],
            ["2026-01-16", "Employer", "1,204.00"],
        ]
        assert [r.number for r in parsed.rows] == [2, 3]

    def test_preamble_and_trailing_delimiter(self):
        text = "Kontonummer:;DE12 3456;\nZeitraum:;Januar;\n\nDatum;Empfaenger;Betrag;\n15.01.2026;REWE;-3,00;\n\n16.01.2026;Lidl;-4,00;\n"
        parsed = parse(text)
        assert parsed.columns == ["Datum", "Empfaenger", "Betrag"]
        assert [r.number for r in parsed.rows] == [5, 7]
        assert parsed.rows[0].cells == ["15.01.2026", "REWE", "-3,00"]

    def test_cr_only_line_endings(self):
        parsed = parse("d,m,a\r2026-01-01,Foo,1\r")
        assert parsed.columns == ["d", "m", "a"]
        assert [(r.number, r.cells) for r in parsed.rows] == [(2, ["2026-01-01", "Foo", "1"])]

    def test_an_unbalanced_quote_is_a_malformed_file(self):
        with pytest.raises(CsvFormatError) as caught:
            parse('a,b\n1,"' + "x" * 140_000 + "\n")
        assert caught.value.reason == "malformed"

    def test_a_header_without_a_trailing_delimiter_beats_rows_with_one(self):
        parsed = parse("Datum;Empfaenger;Betrag\n15.01.2026;REWE;-3,00;\n16.01.2026;Lidl;-4,00;\n")
        assert parsed.columns == ["Datum", "Empfaenger", "Betrag"]
        assert [r.number for r in parsed.rows] == [2, 3]

    def test_short_rows_are_padded(self):
        assert parse("a,b,c\n1,2\n1,2,3\n").rows[0].cells == ["1", "2", ""]

    @pytest.mark.parametrize(
        ("text", "reason"),
        [
            ("", "empty"),
            ("\n\n", "empty"),
            ("justonecolumn\n1\n", "no_header"),
            ("a,,c\n1,2,3\n", "unnamed_column"),
            ("Betrag,betrag\n1,2\n", "duplicate_column"),
            ("a,b\n", "no_rows"),
        ],
    )
    def test_refusals(self, text, reason):
        with pytest.raises(CsvFormatError) as caught:
            parse(text)
        assert caught.value.reason == reason

    def test_too_many_rows(self):
        with pytest.raises(CsvFormatError) as caught:
            parse("a,b\n" + "1,2\n" * (MAX_ROWS + 1))
        assert caught.value.reason == "too_many_rows"
        parse("a,b\n" + "1,2\n" * MAX_ROWS)  # the limit itself is fine


class TestValues:
    @pytest.mark.parametrize(
        ("value", "style", "amount"),
        [
            ("-1.234,56", COMMA_DECIMAL, "-1234.56"),
            ("12,50-", COMMA_DECIMAL, "-12.50"),
            ("€ 1.204,00", COMMA_DECIMAL, "1204.00"),
            ("+3,5", COMMA_DECIMAL, "3.50"),
            ("1,234.56", DOT_DECIMAL, "1234.56"),
            ("-9.99 EUR", DOT_DECIMAL, "-9.99"),
            ("1,234", DOT_DECIMAL, "1234.00"),
            ("12.505", DOT_DECIMAL, "12.51"),
        ],
    )
    def test_amounts(self, value, style, amount):
        assert parse_amount(value, style) == Decimal(amount)

    @pytest.mark.parametrize(
        ("value", "style"),
        [
            ("15.01.2026", COMMA_DECIMAL),
            ("12,50", DOT_DECIMAL),
            ("abc", DOT_DECIMAL),
            ("", DOT_DECIMAL),
            ("1e5", DOT_DECIMAL),
            ("99999999999", DOT_DECIMAL),
        ],
    )
    def test_unreadable_amounts(self, value, style):
        assert parse_amount(value, style) is None

    @pytest.mark.parametrize(
        ("value", "fmt", "day"),
        [
            ("2026-01-15", "%Y-%m-%d", dt.date(2026, 1, 15)),
            ("2026-01-15T23:30:00+02:00", "iso", dt.date(2026, 1, 15)),
            ("15.01.2026", "%d.%m.%Y", dt.date(2026, 1, 15)),
            ("15.01.26", "%d.%m.%y", dt.date(2026, 1, 15)),
            ("01/15/2026", "%m/%d/%Y", dt.date(2026, 1, 15)),
        ],
    )
    def test_dates(self, value, fmt, day):
        assert parse_date(value, fmt) == day

    def test_an_impossible_date(self):
        assert parse_date("31.02.2026", "%d.%m.%Y") is None

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("x", True),
            ("Ja", True),
            ("sì", True),
            ("1", True),
            ("nein", False),
            ("FALSE", False),
            ("", None),
            ("monthly", None),
        ],
    )
    def test_recurring_cells(self, value, expected):
        assert parse_recurring(value) is expected


class TestProfiles:
    def test_formats_are_labelled(self):
        profiles = {p.name: p for p in profile_columns(parse(GERMAN))}
        assert profiles["Buchungsdatum"].date_format == "dd.mm.yyyy"
        assert profiles["Buchungsdatum"].amount_style is None
        assert profiles["Betrag"].amount_style == COMMA_DECIMAL
        assert profiles["Empfaenger"].date_format is None and profiles["Empfaenger"].amount_style is None
        assert profiles["Verwendungszweck"].empty_rate == pytest.approx(1 / 3)

    def test_an_ambiguous_date_goes_day_first(self):
        profiles = profile_columns(parse("d,m\n01/02/2026,x\n03/04/2026,y\n"))
        assert profiles[0].date_format == "dd/mm/yyyy"

    def test_samples_cover_the_most_columns_in_file_order(self):
        parsed = parse("a,b,c\n1,,\n2,,\n,5,\n,,6\n7,8,9\n")
        assert [r.number for r in pick_samples(parsed)] == [2, 3, 6]

    def test_column_key_ignores_order_case_and_spacing(self):
        assert column_key(["Betrag", " Datum"]) == column_key(["datum", "BETRAG "])
        assert column_key(["Betrag"]) != column_key(["Betrag", "Datum"])


class TestMapping:
    def test_a_proposal_is_made_valid(self):
        columns = ["A", "B", "C", "D"]
        cleaned = clean_proposal(columns, {"A": "date", "B": "date", "C": "nonsense", "Z": "amount"})
        assert cleaned == {"A": "date", "B": "ignore", "C": "ignore", "D": "ignore"}

    @pytest.mark.parametrize(
        ("mapping", "reason"),
        [
            ({"Nope": "date"}, "unknown_column"),
            ({"Buchungsdatum": "when"}, "unknown_field"),
            ({"Buchungsdatum": "date", "Empfaenger": "date"}, "field_twice"),
            ({"Buchungsdatum": "date", "Empfaenger": "merchant"}, "missing_required"),
        ],
    )
    def test_problems(self, mapping, reason):
        assert mapping_problem(parse(GERMAN).columns, mapping).reason == reason

    def test_a_good_mapping_has_no_problem(self):
        assert mapping_problem(parse(GERMAN).columns, GERMAN_MAPPING) is None


class TestReadRows:
    def test_rows_and_rejections_in_file_order(self):
        text = GERMAN + "31.02.2026;Bad;;-1,00\n18.01.2026;;;-3,00\n19.01.2026;Bar;;abc\n"
        rows, rejected = read_rows(parse(text), GERMAN_MAPPING)
        assert [(r.number, r.date, r.merchant, r.amount, r.description) for r in rows] == [
            (2, dt.date(2026, 1, 15), "REWE Markt GmbH", Decimal("-1234.56"), "Einkauf"),
            (3, dt.date(2026, 1, 16), "Arbeitgeber", Decimal("2450.00"), "Gehalt"),
            (4, dt.date(2026, 1, 17), "Kiosk", Decimal("-12.50"), None),
        ]
        assert [(r.number, r.reason) for r in rejected] == [
            (5, "unreadable date “31.02.2026”"),
            (6, "no merchant"),
            (7, "unreadable amount “abc”"),
        ]

    def test_recurring_is_none_unless_mapped(self):
        rows, _ = read_rows(parse(GERMAN), GERMAN_MAPPING)
        assert {r.is_recurring for r in rows} == {None}
        rows, _ = read_rows(
            parse("d,m,a,r\n2026-01-01,X,1,x\n2026-01-02,Y,1,\n"),
            {"d": "date", "m": "merchant", "a": "amount", "r": "recurring"},
        )
        assert [r.is_recurring for r in rows] == [True, None]

    def test_a_row_wider_than_the_header_is_rejected_not_cut(self):
        text = "d,a,m,desc\n2026-01-01,-12.00,Foo, Inc,desc\n2026-01-02,-1.00,Bar,x,\n2026-01-03,-2.00,Baz,y\n"
        rows, rejected = read_rows(parse(text), {"d": "date", "a": "amount", "m": "merchant", "desc": "description"})
        assert [(r.number, r.merchant) for r in rows] == [(3, "Bar"), (4, "Baz")]
        assert [(r.number, r.reason) for r in rejected] == [(2, "more cells than the header")]

    def test_long_text_is_cut_to_the_column_sizes(self):
        rows, _ = read_rows(parse(f"d,m,a\n2026-01-01,{'m' * 300},1\n"), {"d": "date", "m": "merchant", "a": "amount"})
        assert len(rows[0].merchant) == 255
