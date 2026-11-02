"""Single home for timezone handling. Session and weekday boundaries are
computed in the *user's* zone (User.timezone, an IANA name); everything stored
stays timestamptz/UTC."""
from zoneinfo import ZoneInfo, available_timezones

# What existing users were silently on before per-user zones existed, and what
# a user gets if they never state one. Also the migration's backfill value.
DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_TZ = ZoneInfo(DEFAULT_TIMEZONE)


def is_valid_timezone(name: str) -> bool:
    # available_timezones() is the authoritative set; ZoneInfo() alone would
    # also accept odd keys (e.g. relative-looking paths) on some platforms.
    return name in available_timezones()


def zone_for(name: str | None) -> ZoneInfo:
    """ZoneInfo for a stored name, falling back to the default if it is
    missing or no longer resolves (e.g. tzdata dropped a legacy alias)."""
    if not name:
        return DEFAULT_TZ
    try:
        return ZoneInfo(name)
    except Exception:
        return DEFAULT_TZ


def user_tz(user) -> ZoneInfo:
    return zone_for(getattr(user, "timezone", None))
