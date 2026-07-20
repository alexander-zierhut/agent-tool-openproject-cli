"""ISO-8601 duration <-> decimal hours.

OpenProject stores time-ish values (``estimatedTime``, time-entry ``hours``)
as ISO-8601 durations like ``PT2H30M`` and *rejects* plain decimals. Humans and
agents want to type ``2.5``. These helpers bridge the two, both directions.
"""

from __future__ import annotations

import re

_ISO_RE = re.compile(
    r"^P(?:(?P<w>\d+(?:\.\d+)?)W)?(?:(?P<d>\d+(?:\.\d+)?)D)?"
    r"(?:T(?:(?P<h>\d+(?:\.\d+)?)H)?(?:(?P<m>\d+(?:\.\d+)?)M)?(?:(?P<s>\d+(?:\.\d+)?)S)?)?$"
)


def hours_to_iso(hours: float) -> str:
    """``2.5`` -> ``"PT2H30M"``. Uses hours/minutes/seconds only."""
    total = round(float(hours) * 3600)
    if total == 0:
        return "PT0S"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    out = "PT"
    if h:
        out += f"{h}H"
    if m:
        out += f"{m}M"
    if s:
        out += f"{s}S"
    return out


def iso_to_hours(value: str | None) -> float | None:
    """``"PT2H30M"`` -> ``2.5``. Returns ``None`` for falsy input.

    Days count as **24h** and weeks as **7 days (168h)** — the calendar
    convention OpenProject's serializer actually uses. Verified live: posting
    ``hours=PT40H`` comes back as ``"P1DT16H"`` (40 = 24 + 16, so a day is 24h)
    and ``P1W`` normalises to ``"P7D"`` (168h). This holds regardless of the
    instance's hours-per-day setting, because the ``hours`` field is a raw
    ``ActiveSupport::Duration``, not scheduling time. (A "working day" of 8h is
    logged as ``PT8H``, not ``P1D``.) OP never emits year/month components.
    """
    if not value:
        return None
    m = _ISO_RE.match(value.strip())
    if not m:
        return None
    parts = {k: float(v) if v else 0.0 for k, v in m.groupdict().items()}
    return parts["w"] * 168 + parts["d"] * 24 + parts["h"] + parts["m"] / 60 + parts["s"] / 3600


def parse_hours_input(value: str) -> str:
    """Accept either a decimal (``"2.5"``) or an ISO duration (``"PT2H30M"``)
    from the user and normalise to the ISO form the API wants."""
    v = value.strip()
    if v.upper().startswith("P"):
        return v  # already ISO
    return hours_to_iso(float(v))
