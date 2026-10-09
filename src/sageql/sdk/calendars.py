"""Bounded date-only Persian calendar conversion for explicit month selections.

The supported Solar Hijri years are 1300 through 1499. Report SQL still receives
Gregorian dates; this module does not convert timestamps or implement grouping.
"""

from datetime import date, timedelta


JALALI_MONTH_NAMES = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)
MIN_JALALI_YEAR = 1300
MAX_JALALI_YEAR = 1499


# The Nowruz calculation is adapted from jalaali-js's Borkowski algorithm:
# https://github.com/jalaali/jalaali-js/blob/master/src/index.ts
# https://www.astro.uni.torun.pl/~kb/Papers/EMP/PersianC-EMP.htm
#
# MIT License
#
# Copyright (c) 2020 Behrang Norouzinia
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
_CYCLE_BREAKS = (
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181,
    1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178,
)


def _nowruz(year: int) -> date:
    """Gregorian date of Farvardin 1; callers bound years to 1300..1500."""
    gregorian_year = year + 621
    persian_leaps = -14
    previous = _CYCLE_BREAKS[0]
    for following in _CYCLE_BREAKS[1:]:
        jump = following - previous
        if year < following:
            break
        persian_leaps += (jump // 33) * 8 + (jump % 33) // 4
        previous = following
    offset = year - previous
    persian_leaps += (offset // 33) * 8 + (offset % 33 + 3) // 4
    if jump % 33 == 4 and jump - offset == 4:
        persian_leaps += 1
    gregorian_leaps = (
        gregorian_year // 4 - ((gregorian_year // 100 + 1) * 3) // 4 - 150
    )
    return date(gregorian_year, 3, 20 + persian_leaps - gregorian_leaps)


def jalali_month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return inclusive/exclusive Gregorian bounds of one Solar Hijri month.

    Both inputs must be integers, excluding booleans. Years outside 1300..1499
    and months outside 1..12 raise ``ValueError``. Esfand ends on the following
    Nowruz, including the leap day when present.
    """
    if type(year) is not int or not MIN_JALALI_YEAR <= year <= MAX_JALALI_YEAR:
        raise ValueError("Jalali year must be an integer between 1300 and 1499.")
    if type(month) is not int or not 1 <= month <= 12:
        raise ValueError("Jalali month must be an integer between 1 and 12.")
    start = _nowruz(year) + timedelta(days=(month - 1) * 31 - max(month - 7, 0))
    if month == 12:
        end = _nowruz(year + 1)
    else:
        end = start + timedelta(days=31 if month <= 6 else 30)
    return start, end


def gregorian_to_jalali(value: date) -> tuple[int, int, int]:
    """Convert a date-only value for display within Solar Hijri 1300..1499.

    Reject timestamps and dates outside the bounded supported interval with
    ``ValueError``; no timezone or implicit time truncation is performed.
    """
    if type(value) is not date:
        raise ValueError("A Gregorian date-only value is required.")
    if not _nowruz(MIN_JALALI_YEAR) <= value < _nowruz(MAX_JALALI_YEAR + 1):
        raise ValueError("Gregorian date is outside Solar Hijri years 1300..1499.")
    year = value.year - 621
    anchor = _nowruz(year)
    if value < anchor:
        year -= 1
        anchor = _nowruz(year)
    offset = (value - anchor).days
    if offset < 186:
        return year, offset // 31 + 1, offset % 31 + 1
    offset -= 186
    return year, offset // 30 + 7, offset % 30 + 1
