from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Iterable, Optional

import requests

__all__ = [
    "get_sp500_history", "save_json", "to_json", "build_universe", "collect",
    "FMPProvider", "Company", "MembershipPeriod", "ChangeEvent", "Status",
]

log = logging.getLogger("sp500_history")

FMP_BASE = "https://financialmodelingprep.com/stable"

TERMINAL_REASON_RE = re.compile(
    r"acquir|merge|bankrupt|chapter\s*11|liquidat|delist|"
    r"taken private|going private|buyout|take-private",
    re.IGNORECASE,
)


class Status(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ChangeEvent:
    """One row of the index change log."""
    date: date
    added_ticker: Optional[str] = None
    added_name: Optional[str] = None
    removed_ticker: Optional[str] = None
    removed_name: Optional[str] = None
    reason: str = ""


@dataclass
class MembershipPeriod:

    start: Optional[date]
    end: Optional[date]
    start_clamped: bool = False
    end_reason: str = ""
    def to_dict(self) -> dict:
        return {
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "start_clamped": self.start_clamped,
            "end_reason": self.end_reason,
        }


@dataclass
class Company:
    ticker: str
    name: str
    periods: list[MembershipPeriod]
    status: Status
    status_reason: str = ""
    delisted_date: Optional[date] = None

    @property
    def first_active(self) -> Optional[date]:
        return self.periods[0].start if self.periods else None

    @property
    def last_active(self) -> Optional[date]:
        """None means still active in the index."""
        return self.periods[-1].end if self.periods else None

    @property
    def is_inactive(self) -> bool:
        return self.status is Status.INACTIVE

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "status": self.status.value,
            "status_reason": self.status_reason,
            "first_active": self.first_active.isoformat() if self.first_active else None,
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "delisted_date": self.delisted_date.isoformat() if self.delisted_date else None,
            "periods": [p.to_dict() for p in self.periods],
        }


def years_ago(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - years, day=28)


def parse_date(value) -> Optional[date]:
    if value is None:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _clean(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def is_terminal_reason(reason: str) -> bool:
    return bool(reason and TERMINAL_REASON_RE.search(reason))


def parse_fmp_changes(rows: Iterable[dict]) -> list[ChangeEvent]:
    out = []
    for r in rows:
        d = parse_date(r.get("date")) or parse_date(r.get("dateAdded"))
        if d is None:
            continue
        out.append(ChangeEvent(
            date=d,
            added_ticker=_clean(r.get("symbol")),
            added_name=_clean(r.get("addedSecurity")),
            removed_ticker=_clean(r.get("removedTicker")),
            removed_name=_clean(r.get("removedSecurity")),
            reason=_clean(r.get("reason")) or "",
        ))
    return out


class FMPProvider:
    name = "fmp"

    def __init__(self, api_key: str, session=None, max_delisted_pages: int = 300):
        if not api_key:
            raise ValueError("FMP API key required (set FMP_API_KEY).")
        self._key = api_key
        self._session = session or requests
        self._max_pages = max_delisted_pages

    def _get(self, path: str, **params):
        resp = self._session.get(f"{FMP_BASE}/{path}",
                                 params={**params, "apikey": self._key}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def fetch_current(self) -> list[tuple[str, str]]:
        out = []
        for r in self._get("sp500-constituent"):
            sym = _clean(r.get("symbol"))
            if sym:
                out.append((sym, _clean(r.get("name")) or sym))
        return out

    def fetch_changes(self) -> list[ChangeEvent]:
        return parse_fmp_changes(self._get("historical-sp500-constituent"))

    def fetch_delisted(self, since: date) -> dict[str, date]:
        out: dict[str, date] = {}
        for page in range(self._max_pages):
            rows = self._get("delisted-companies", page=page, limit=100)
            if not rows:
                break
            for r in rows:
                d = parse_date(r.get("delistedDate"))
                sym = _clean(r.get("symbol"))
                if sym and d and d >= since:
                    out[sym] = max(d, out.get(sym, d))
        return out


def build_universe(
    current: Iterable[tuple[str, str]],
    changes: Iterable[ChangeEvent],
    window_start: date,
    delisted: Optional[dict[str, date]] = None,
) -> list[Company]:
    """Walk the change log newest -> oldest starting from today's constituents."""
    delisted = delisted or {}
    periods: dict[str, list[MembershipPeriod]] = defaultdict(list)
    names: dict[str, str] = {}
    pending: dict[str, MembershipPeriod] = {} 
    orphans: set[str] = set()

    for ticker, name in current:
        p = MembershipPeriod(start=None, end=None)
        periods[ticker].append(p)
        pending[ticker] = p
        names[ticker] = name

    for ev in sorted(changes, key=lambda e: e.date, reverse=True):
        if ev.date < window_start:
            break
        if ev.removed_ticker:
            t = ev.removed_ticker
            names.setdefault(t, ev.removed_name or t)
            if t in pending:  # inconsistent log: two removals without an addition
                log.warning("%s: removal on %s but later period has no addition", t, ev.date)
                pending.pop(t).start = ev.date
            p = MembershipPeriod(start=None, end=ev.date, end_reason=ev.reason)
            periods[t].append(p)
            pending[t] = p
        if ev.added_ticker:
            t = ev.added_ticker
            names.setdefault(t, ev.added_name or t)
            if t in pending:
                pending.pop(t).start = ev.date
            else: 
                log.warning("%s: added %s but no matching removal/current entry", t, ev.date)
                periods[t].append(MembershipPeriod(start=ev.date, end=None))
                orphans.add(t)

    for p in pending.values():  
        p.start = window_start
        p.start_clamped = True

    companies = []
    for t, plist in periods.items():
        plist.sort(key=lambda p: p.start)
        last = plist[-1]
        delisted_date = None
        if t in orphans:
            status, reason = Status.UNKNOWN, "no matching removal found (possible ticker change)"
        elif last.end is None:
            status, reason = Status.ACTIVE, "current S&P 500 constituent"
        elif t in delisted and delisted[t] >= last.end - timedelta(days=30):
            status, reason = Status.INACTIVE, "listed as delisted by FMP"
            delisted_date = delisted[t]
        elif is_terminal_reason(last.end_reason):
            status, reason = Status.INACTIVE, last.end_reason
        else:
            status = Status.UNKNOWN
            reason = last.end_reason or "removed from index; trading status unverified"
        companies.append(Company(t, names[t], plist, status, reason, delisted_date))

    return sorted(companies, key=lambda c: c.ticker)


def collect(provider, years: int = 10, today: Optional[date] = None) -> list[Company]:
    """`provider` needs fetch_current(), fetch_changes() and fetch_delisted(since)."""
    today = today or date.today()
    start = years_ago(today, years)
    return build_universe(
        provider.fetch_current(),
        provider.fetch_changes(),
        start,
        provider.fetch_delisted(start),
    )


def to_json(companies: list[Company], source: str, years: int, today: date) -> str:
    return json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "window_start": years_ago(today, years).isoformat(),
        "window_end": today.isoformat(),
        "count": len(companies),
        "companies": [c.to_dict() for c in companies],
    }, indent=2)


def save_json(companies: list[Company], path: str, source: str = "fmp",
              years: int = 10, today: Optional[date] = None) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_json(companies, source, years, today or date.today()))


def get_sp500_history(
    years: int = 10,
    api_key: Optional[str] = None,
    today: Optional[date] = None,
    output_path: Optional[str] = None,
    max_delisted_pages: int = 300,
    session=None,
    provider=None,
) -> list[Company]:

    if isinstance(years, bool) or not isinstance(years, int) or years < 1:
        raise ValueError(f"years must be a positive integer, got {years!r}")

    if provider is None:
        key = api_key or os.environ.get("FMP_API_KEY", "")
        provider = FMPProvider(key, session=session, max_delisted_pages=max_delisted_pages)

    today = today or date.today()
    companies = collect(provider, years, today)
    if output_path:
        save_json(companies, output_path, getattr(provider, "name", "custom"), years, today)
    return companies


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--out", default="sp500_history.json")
    ap.add_argument("--api-key", default=None, help="FMP key (default: FMP_API_KEY env var)")
    ap.add_argument("--max-delisted-pages", type=int, default=300)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    companies = get_sp500_history(
        years=args.years,
        api_key=args.api_key,
        output_path=args.out,
        max_delisted_pages=args.max_delisted_pages,
    )
    counts: dict[str, int] = defaultdict(int)
    for c in companies:
        counts[c.status.value] += 1
    print(f"Wrote {len(companies)} companies to {args.out}: {dict(counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
