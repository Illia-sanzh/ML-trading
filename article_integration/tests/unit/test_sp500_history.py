import json
from datetime import date
from unittest.mock import MagicMock

import pytest

import article_integration.infrastructure.sp500_history as sh
from article_integration.infrastructure.sp500_history import ChangeEvent, Status, build_universe

WINDOW_START = date(2016, 11, 14)


def ev(d, add=None, rem=None, reason="", add_name=None, rem_name=None):
    return ChangeEvent(d, add, add_name, rem, rem_name, reason)


def build(current, changes, delisted=None):
    return {c.ticker: c for c in build_universe(current, changes, WINDOW_START, delisted)}


@pytest.mark.parametrize(
    "d, years, expected",
    [
        (date(2026, 11, 14), 10, date(2016, 11, 14)),
        (date(2024, 2, 29), 10, date(2014, 2, 28)),  # leap day fallback
        (date(2026, 1, 1), 1, date(2025, 1, 1)),
    ],
)
def test_years_ago(d, years, expected):
    assert sh.years_ago(d, years) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2025-10-08", date(2025, 10, 8)),
        ("October 8, 2025", date(2025, 10, 8)),
        ("Oct 8, 2025", date(2025, 10, 8)),
        ("  2025-10-08  ", date(2025, 10, 8)),
        ("garbage", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_date(value, expected):
    assert sh.parse_date(value) == expected


@pytest.mark.parametrize(
    "reason, expected",
    [
        ("Acquired by Foo Corp.", True),
        ("Merged with Bar Inc.", True),
        ("Filed for Chapter 11 bankruptcy", True),
        ("Company liquidated", True),
        ("Taken private by investors", True),
        ("Market capitalization change", False),
        ("Replaced by a larger company", False),
        ("", False),
    ],
)
def test_is_terminal_reason(reason, expected):
    assert sh.is_terminal_reason(reason) is expected


@pytest.mark.parametrize(
    "reason, delisted, expected_status",
    [
        ("Acquired by Big Co.", None, Status.INACTIVE),
        ("Bankruptcy filing", None, Status.INACTIVE),
        ("Market capitalization change", None, Status.UNKNOWN),
        ("", None, Status.UNKNOWN),
        # provider delisted list upgrades UNKNOWN -> INACTIVE
        ("Market capitalization change", {"GONE": date(2022, 2, 2)}, Status.INACTIVE),
        # delisting date before the removal = ticker reuse by an older company, ignore
        ("Market capitalization change", {"GONE": date(2017, 1, 1)}, Status.UNKNOWN),
    ],
)
def test_removed_company_status(reason, delisted, expected_status):
    changes = [ev(date(2021, 5, 1), add="NEW", rem="GONE", reason=reason, rem_name="Gone Inc")]
    res = build([("NEW", "New Co")], changes, delisted)
    assert res["GONE"].status is expected_status
    assert res["GONE"].name == "Gone Inc"
    assert res["GONE"].last_active == date(2021, 5, 1)
    assert res["GONE"].is_inactive is (expected_status is Status.INACTIVE)


def test_delisted_date_is_recorded():
    changes = [ev(date(2021, 5, 1), add="NEW", rem="GONE", reason="Market cap")]
    res = build([("NEW", "New")], changes, {"GONE": date(2022, 2, 2)})
    assert res["GONE"].delisted_date == date(2022, 2, 2)


def test_current_member_since_before_window_is_clamped_and_active():
    c = build([("AAPL", "Apple")], [])["AAPL"]
    assert c.status is Status.ACTIVE
    assert c.periods[0].start_clamped
    assert c.first_active == WINDOW_START
    assert c.last_active is None


def test_recent_addition_has_exact_start_date():
    changes = [ev(date(2020, 12, 21), add="TSLA", rem="AIV", rem_name="Aimco")]
    res = build([("TSLA", "Tesla")], changes)
    assert res["TSLA"].first_active == date(2020, 12, 21)
    assert not res["TSLA"].periods[0].start_clamped


def test_removed_company_that_predates_window_is_clamped():
    changes = [ev(date(2019, 7, 1), add="NEW", rem="OLD", reason="Acquired")]
    old = build([("NEW", "New")], changes)["OLD"]
    assert old.periods[0].start_clamped
    assert old.first_active == WINDOW_START


def test_readded_ticker_has_two_periods_and_is_active():
    changes = [
        ev(date(2022, 1, 3), add="RE", rem="Z"),
        ev(date(2018, 6, 1), add="Y", rem="RE", reason="Market cap"),
    ]
    c = build([("RE", "ReCo"), ("Y", "Y")], changes)["RE"]
    assert len(c.periods) == 2
    assert c.periods[0].end == date(2018, 6, 1)
    assert c.periods[1].start == date(2022, 1, 3)
    assert c.periods[1].end is None
    assert c.status is Status.ACTIVE


def test_events_before_window_are_ignored():
    changes = [ev(date(2010, 1, 1), add="NEW", rem="ANCIENT", reason="Acquired")]
    res = build([("NEW", "New")], changes)
    assert "ANCIENT" not in res
    assert res["NEW"].periods[0].start_clamped


def test_orphan_addition_is_unknown():
    res = build([], [ev(date(2019, 1, 1), add="RENAMED")])
    assert res["RENAMED"].status is Status.UNKNOWN


def test_output_is_sorted_by_ticker():
    changes = [ev(date(2020, 1, 1), add="B", rem="C", reason="Acquired")]
    tickers = [c.ticker for c in build_universe([("B", "B"), ("A", "A")], changes, WINDOW_START)]
    assert tickers == sorted(tickers)


def test_to_json_roundtrip():
    companies = build_universe([("AAPL", "Apple")], [], WINDOW_START)
    out = json.loads(sh.to_json(companies, "fmp", 10, date(2026, 11, 14)))
    assert out["count"] == 1
    assert out["source"] == "fmp"
    assert out["window_start"] == "2016-11-14"
    assert out["companies"][0]["ticker"] == "AAPL"
    assert out["companies"][0]["status"] == "ACTIVE"
    assert out["companies"][0]["periods"][0]["start_clamped"] is True


def fake_session(*payloads):
    session = MagicMock()
    session.get.side_effect = [MagicMock(json=MagicMock(return_value=p)) for p in payloads]
    return session


def test_parse_fmp_changes():
    rows = [
        {"date": "2024-03-18", "symbol": "SMCI", "addedSecurity": "Super Micro",
         "removedTicker": "WHR", "removedSecurity": "Whirlpool", "reason": "Market cap"},
        {"dateAdded": "June 1, 2020", "symbol": "A", "removedTicker": ""},
        {"symbol": "NODATE"},  # skipped: no parseable date
    ]
    events = sh.parse_fmp_changes(rows)
    assert len(events) == 2
    assert events[0].removed_ticker == "WHR"
    assert events[1].date == date(2020, 6, 1)
    assert events[1].removed_ticker is None


def test_fmp_requires_key():
    with pytest.raises(ValueError):
        sh.FMPProvider("")


def test_fmp_fetch_current_skips_blank_symbols_and_sends_api_key():
    session = fake_session([{"symbol": "AAPL", "name": "Apple Inc."}, {"symbol": "", "name": "bad"}])
    provider = sh.FMPProvider("secret", session=session)
    assert provider.fetch_current() == [("AAPL", "Apple Inc.")]
    assert session.get.call_args.kwargs["params"]["apikey"] == "secret"


def test_fmp_delisted_paginates_and_filters_by_date():
    session = fake_session(
        [{"symbol": "AAA", "delistedDate": "2020-01-01"},
         {"symbol": "OLD", "delistedDate": "2001-01-01"}],
        [{"symbol": "BBB", "delistedDate": "2022-05-05"}],
        [],
    )
    out = sh.FMPProvider("k", session=session).fetch_delisted(date(2016, 1, 1))
    assert out == {"AAA": date(2020, 1, 1), "BBB": date(2022, 5, 5)}
    assert session.get.call_count == 3


def test_fmp_http_error_propagates():
    session = MagicMock()
    session.get.return_value.raise_for_status.side_effect = RuntimeError("403")
    with pytest.raises(RuntimeError):
        sh.FMPProvider("k", session=session).fetch_current()


def test_collect_end_to_end_with_fake_provider():
    class Fake:
        name = "fake"
        def fetch_current(self): return [("NEW", "New")]
        def fetch_changes(self):
            return [ev(date(2019, 7, 1), add="NEW", rem="OLD", reason="Acquired")]
        def fetch_delisted(self, since): return {}

    res = {c.ticker: c for c in sh.collect(Fake(), 10, today=date(2026, 11, 14))}
    assert res["OLD"].status is Status.INACTIVE
    assert res["NEW"].status is Status.ACTIVE


class FakeProvider:
    name = "fake"

    def fetch_current(self):
        return [("NEW", "New")]

    def fetch_changes(self):
        return [ev(date(2019, 7, 1), add="NEW", rem="OLD", reason="Acquired")]

    def fetch_delisted(self, since):
        return {}


TODAY = date(2026, 11, 14)


def test_get_sp500_history_with_injected_provider():
    res = {c.ticker: c for c in sh.get_sp500_history(years=10, today=TODAY, provider=FakeProvider())}
    assert res["OLD"].status is Status.INACTIVE
    assert res["NEW"].status is Status.ACTIVE


def test_get_sp500_history_years_argument_changes_window():
    # Removal in 2019 is inside a 10y window but outside a 3y window (from Nov 2026).
    ten = {c.ticker for c in sh.get_sp500_history(years=10, today=TODAY, provider=FakeProvider())}
    three = {c.ticker for c in sh.get_sp500_history(years=3, today=TODAY, provider=FakeProvider())}
    assert "OLD" in ten
    assert "OLD" not in three


@pytest.mark.parametrize("bad_years", [0, -5, 1.5, "10", None, True])
def test_get_sp500_history_rejects_invalid_years(bad_years):
    with pytest.raises(ValueError, match="years"):
        sh.get_sp500_history(years=bad_years, provider=FakeProvider())


def test_get_sp500_history_writes_json(tmp_path):
    out = tmp_path / "out.json"
    sh.get_sp500_history(years=10, today=TODAY, provider=FakeProvider(), output_path=str(out))
    data = json.loads(out.read_text())
    assert data["source"] == "fake"
    assert data["window_end"] == "2026-11-14"
    assert {c["ticker"] for c in data["companies"]} == {"OLD", "NEW"}


def test_get_sp500_history_requires_api_key(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key"):
        sh.get_sp500_history()


def test_get_sp500_history_uses_explicit_api_key_with_session():
    session = fake_session(
        [{"symbol": "NEW", "name": "New"}],
        [{"date": "2019-07-01", "symbol": "NEW", "removedTicker": "OLD", "reason": "Acquired"}],
        [],  # delisted page 0 is empty
    )
    res = {c.ticker: c for c in sh.get_sp500_history(
        years=10, api_key="explicit", today=TODAY, session=session)}
    assert res["OLD"].status is Status.INACTIVE
    assert all(c.kwargs["params"]["apikey"] == "explicit" for c in session.get.call_args_list)


def test_get_sp500_history_falls_back_to_env_var(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "from-env")
    session = fake_session([{"symbol": "NEW", "name": "New"}], [], [])
    sh.get_sp500_history(years=10, today=TODAY, session=session)
    assert session.get.call_args.kwargs["params"]["apikey"] == "from-env"


def test_main_cli_passes_arguments_through(tmp_path, monkeypatch, capsys):
    seen = {}

    def fake_get(**kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(sh, "get_sp500_history", fake_get)
    out = str(tmp_path / "x.json")
    assert sh.main(["--years", "5", "--out", out, "--api-key", "k", "--max-delisted-pages", "7"]) == 0
    assert seen == {"years": 5, "api_key": "k", "output_path": out, "max_delisted_pages": 7}
    assert "Wrote 0 companies" in capsys.readouterr().out
