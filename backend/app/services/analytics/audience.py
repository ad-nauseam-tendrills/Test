"""
Audience timezone analysis.

An account's own posting history tells you which UTC hours it has posted
at, but not whether those hours are convenient for the people following
it. Meta's `follower_demographics` insight gives a country breakdown of
followers, which is enough to answer a narrower but genuinely factual
question: for a given posting hour, what fraction of this account's
followers are in their waking hours?

What this deliberately does NOT do is invent an engagement curve. There
is no claim here that posting when more people are awake produces more
engagement -- only that a given hour reaches more or fewer waking
followers, which is a fact about timezones rather than a prediction
about behaviour. The historical engagement data stays the separate,
account-specific signal it already was.
"""
from __future__ import annotations

from dataclasses import dataclass

# Waking window in each follower's local time. Deliberately generous:
# the point is to exclude the hours when a country is plainly asleep,
# not to guess when people feel like opening an app.
WAKING_START_HOUR = 7
WAKING_END_HOUR = 23

# Below this many followers with a known country, the breakdown is too
# thin to say anything.
MIN_FOLLOWERS_FOR_ANALYSIS = 50

CAVEAT = (
    "This shows what fraction of your followers are in their waking hours at each "
    "posting time, based on the countries Instagram reports for your audience. It "
    "does not predict engagement -- only that more or fewer people are plausibly "
    "awake. Offsets ignore daylight saving, and countries spanning several zones "
    "use their most populous one."
)

# Approximate standard UTC offset per ISO-3166 alpha-2 country code.
# DST is ignored (it shifts results by at most an hour), and countries
# spanning multiple zones are mapped to their most populous zone -- both
# noted in CAVEAT. This covers the countries that realistically appear
# in a follower breakdown; anything unlisted is excluded from the
# calculation rather than guessed at.
COUNTRY_UTC_OFFSETS: dict[str, float] = {
    # Americas
    "US": -6.0, "CA": -5.0, "MX": -6.0, "BR": -3.0, "AR": -3.0, "CL": -4.0,
    "CO": -5.0, "PE": -5.0, "VE": -4.0, "EC": -5.0, "GT": -6.0, "CU": -5.0,
    "DO": -4.0, "BO": -4.0, "CR": -6.0, "PA": -5.0, "UY": -3.0, "PR": -4.0,
    "JM": -5.0, "HN": -6.0, "PY": -4.0, "NI": -6.0, "SV": -6.0, "TT": -4.0,
    # Europe
    "GB": 0.0, "IE": 0.0, "PT": 0.0, "IS": 0.0,
    "FR": 1.0, "DE": 1.0, "ES": 1.0, "IT": 1.0, "NL": 1.0, "BE": 1.0,
    "CH": 1.0, "AT": 1.0, "SE": 1.0, "NO": 1.0, "DK": 1.0, "PL": 1.0,
    "CZ": 1.0, "HU": 1.0, "HR": 1.0, "RS": 1.0, "SK": 1.0, "SI": 1.0,
    "AL": 1.0, "BA": 1.0, "MK": 1.0, "LU": 1.0, "MT": 1.0,
    "FI": 2.0, "GR": 2.0, "RO": 2.0, "BG": 2.0, "UA": 2.0, "LT": 2.0,
    "LV": 2.0, "EE": 2.0, "MD": 2.0, "CY": 2.0, "BY": 3.0, "RU": 3.0,
    # Middle East & Africa
    "TR": 3.0, "IL": 2.0, "SA": 3.0, "AE": 4.0, "QA": 3.0, "KW": 3.0,
    "JO": 3.0, "LB": 2.0, "IQ": 3.0, "IR": 3.5, "EG": 2.0, "MA": 1.0,
    "DZ": 1.0, "TN": 1.0, "LY": 2.0, "NG": 1.0, "GH": 0.0, "KE": 3.0,
    "ZA": 2.0, "ET": 3.0, "TZ": 3.0, "UG": 3.0, "SN": 0.0, "CI": 0.0,
    "CM": 1.0, "ZW": 2.0, "ZM": 2.0, "AO": 1.0, "MZ": 2.0,
    # Asia & Oceania
    "IN": 5.5, "PK": 5.0, "BD": 6.0, "LK": 5.5, "NP": 5.75, "AF": 4.5,
    "TH": 7.0, "VN": 7.0, "ID": 7.0, "MY": 8.0, "SG": 8.0, "PH": 8.0,
    "CN": 8.0, "HK": 8.0, "TW": 8.0, "KR": 9.0, "JP": 9.0, "MM": 6.5,
    "KH": 7.0, "KZ": 5.0, "UZ": 5.0, "AZ": 4.0, "GE": 4.0, "AM": 4.0,
    "AU": 10.0, "NZ": 12.0, "FJ": 12.0, "PG": 10.0,
}


@dataclass
class HourAudienceStat:
    hour_utc: int
    awake_fraction: float  # 0-1
    # The same hour expressed in the account owner's local time, so the
    # UI can present something actionable rather than a UTC figure.
    hour_local: int


def _local_hour(hour_utc: int, offset: float) -> float:
    return (hour_utc + offset) % 24


def _is_waking(local_hour: float) -> bool:
    return WAKING_START_HOUR <= local_hour < WAKING_END_HOUR


def awake_fraction_for_hour(hour_utc: int, demographics: dict[str, int]) -> float | None:
    """
    Fraction of followers whose local time at `hour_utc` falls in the
    waking window. Countries with no known offset are excluded from both
    numerator and denominator rather than assumed.
    """
    known = {c: n for c, n in demographics.items() if c.upper() in COUNTRY_UTC_OFFSETS}
    total = sum(known.values())
    if total <= 0:
        return None

    awake = sum(
        n
        for c, n in known.items()
        if _is_waking(_local_hour(hour_utc, COUNTRY_UTC_OFFSETS[c.upper()]))
    )
    return round(awake / total, 4)


def analyze_audience_hours(
    demographics: dict[str, int], viewer_utc_offset: float = 0.0
) -> dict:
    """
    Awake-fraction across all 24 UTC hours, plus the coverage figure the
    UI needs to be honest about how much of the audience this accounts for.
    """
    total_followers = sum(demographics.values()) if demographics else 0
    known = {c: n for c, n in (demographics or {}).items() if c.upper() in COUNTRY_UTC_OFFSETS}
    known_followers = sum(known.values())

    if known_followers < MIN_FOLLOWERS_FOR_ANALYSIS:
        return {
            "has_enough_data": False,
            "message": (
                "Not enough audience data yet. Instagram reports follower "
                "demographics only for accounts with at least 100 followers."
            ),
            "hours": [],
            "top_countries": [],
            "coverage": 0.0,
            "caveat": CAVEAT,
        }

    hours = []
    for hour in range(24):
        fraction = awake_fraction_for_hour(hour, known)
        hours.append(
            HourAudienceStat(
                hour_utc=hour,
                awake_fraction=fraction if fraction is not None else 0.0,
                hour_local=int(_local_hour(hour, viewer_utc_offset)),
            )
        )

    top = sorted(known.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "has_enough_data": True,
        "message": None,
        "hours": hours,
        "top_countries": [
            {"country": c, "follower_count": n, "share": round(n / known_followers, 4)}
            for c, n in top
        ],
        # What proportion of the reported audience we could place in a
        # timezone at all -- makes an unmapped-heavy audience visible.
        "coverage": round(known_followers / total_followers, 4) if total_followers else 0.0,
        "caveat": CAVEAT,
    }
