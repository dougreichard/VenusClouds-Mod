"""Altitude as a lethal axis - the one system this setting has that space does not.

THE IDEA. In space, y is decoration. Here it is the whole tactical dial: there is a FLOOR
(pressure and heat in the deep deck) and a CEILING (air too thin to hold lift), and a
damaged airship does not explode - it SINKS. That turns every fight into a race against your
own altitude and makes Engineering matter in a way weapons cannot.

Three bands, matching the six skies the mod ships so the art tells the player where they are
before any console does:

    HAZE    above CEILING_Y   thin, bright, cold. Lift falls off; you cannot stay.
    LANES   the working band  free cities, cargo, ordinary life.
    DECK    below FLOOR_Y     dark, hot, crushing. Salvage, the Armada, the Brood.

WHY THE HAZARD IS A CURVE, NOT A LINE. A hard boundary teaches players to sit exactly on it.
A curve that starts biting gently and grows means the deep deck is somewhere you CHOOSE to
go, at a cost you can feel accumulating - which is the dramatic shape the story wants,
because Act 2 is a descent the crew elects to make.

Everything here is pure arithmetic on positions and inventory values. It deliberately
applies no damage and schedules no tasks: the mission owns the ticker, so a mission that
wants a gentler world just calls it less often. See `venus_altitude_report`.
"""

# The band edges, in engine units of y. Chosen so the lanes are a comfortable working slab
# and the deck is reachable but never accidental.
CEILING_Y = 6000.0
FLOOR_Y = -6000.0

# Where the hazard reaches full strength - beyond this you are simply dying.
CEILING_LETHAL_Y = 11000.0
FLOOR_LETHAL_Y = -11000.0

# Lift is a 0..1 fraction of envelope integrity. At full lift a hull can hold the ceiling;
# as lift bleeds away the altitude it can hold sinks with it.
LIFT_KEY = "venus_lift"
LIFT_FULL = 1.0

BAND_HAZE = "haze"
BAND_LANES = "lanes"
BAND_DECK = "deck"

# The sky each band should be wearing. A mission can hand these straight to the skybox
# scheduler, so the art and the mechanic can never disagree about where the player is.
BAND_SKY = {
    BAND_HAZE: "venus_sky_high_haze",
    BAND_LANES: "venus_sky_midday",
    BAND_DECK: "venus_sky_deep",
}


def venus_band(y):
    """Which of the three bands an altitude is in."""
    if y > CEILING_Y:
        return BAND_HAZE
    if y < FLOOR_Y:
        return BAND_DECK
    return BAND_LANES


def venus_band_sky(band):
    """The skybox label for a band. Unknown band -> the working altitude."""
    return BAND_SKY.get(band, BAND_SKY[BAND_LANES])


def venus_hazard(y):
    """How dangerous this altitude is, 0.0 (safe) to 1.0 (lethal).

    Ramps from the band edge to the lethal depth rather than switching on, so the pressure
    is something the crew watches climb rather than a wall they bounce off.
    """
    if y > CEILING_Y:
        span = CEILING_LETHAL_Y - CEILING_Y
        return min(1.0, (y - CEILING_Y) / span) if span > 0 else 1.0
    if y < FLOOR_Y:
        span = FLOOR_Y - FLOOR_LETHAL_Y
        return min(1.0, (FLOOR_Y - y) / span) if span > 0 else 1.0
    return 0.0


def venus_lift_get(obj):
    """An object's remaining lift, 0..1. Anything that has never been given lift is full -
    so terrain, stations and any hull the mission does not manage behave normally."""
    try:
        v = obj.get_inventory_value(LIFT_KEY, LIFT_FULL)
    except AttributeError:
        return LIFT_FULL
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return LIFT_FULL


def venus_lift_set(obj, value):
    try:
        obj.set_inventory_value(LIFT_KEY, max(0.0, min(1.0, float(value))))
    except AttributeError:
        pass


def venus_lift_bleed(obj, amount):
    """Take lift away. Returns what is left.

    This is what damage should call instead of, or as well as, dealing hull damage: a hit to
    the envelope does not kill the ship, it starts the clock.
    """
    left = venus_lift_get(obj) - max(0.0, float(amount))
    venus_lift_set(obj, left)
    return max(0.0, left)


def venus_ceiling_for_lift(lift):
    """The highest altitude a hull with this much lift can hold.

    At full lift that is the top of the lanes; at no lift it is the floor. A ship losing
    lift therefore gets squeezed downward into exactly the band it least wants to be in,
    which is the whole point.
    """
    lift = max(0.0, min(1.0, float(lift)))
    return FLOOR_Y + (CEILING_Y - FLOOR_Y) * lift


def venus_is_sinking(obj, y):
    """True when this hull is above the altitude its remaining lift can hold."""
    return y > venus_ceiling_for_lift(venus_lift_get(obj))


def venus_altitude_report(obj, y):
    """Everything the mission needs for one hull, in one call.

    Returns a dict rather than applying anything, because how a mission punishes altitude is
    a mission's decision - and because a dict is easy to put on a console.
    """
    lift = venus_lift_get(obj)
    band = venus_band(y)
    hazard = venus_hazard(y)
    return {
        "band": band,
        "sky": venus_band_sky(band),
        "hazard": hazard,
        "lift": lift,
        "ceiling": venus_ceiling_for_lift(lift),
        "sinking": venus_is_sinking(obj, y),
    }


def venus_altitude_text(report):
    """One short ASCII line for a console. Kept free of braces: MAST re-runs an assigned
    string through f-string formatting, so a '{' here would blow up at the caller."""
    band = report.get("band", BAND_LANES).upper()
    hazard = int(round(report.get("hazard", 0.0) * 100))
    lift = int(round(report.get("lift", 1.0) * 100))
    line = band + "  lift " + str(lift) + "%"
    if hazard > 0:
        line += "  HULL STRESS " + str(hazard) + "%"
    if report.get("sinking"):
        line += "  SINKING"
    return line
