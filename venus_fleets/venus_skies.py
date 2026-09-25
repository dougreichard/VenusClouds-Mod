"""Whether this pack's skybox art actually arrived.

A `@media/skybox/...` label whose PNG is missing is NOT an error: `MediaLabel.test_file()`
answers False, `get_of_type` drops the label, and it is never picked again - in silence.
That is exactly what a mission gets when it lists the mastlib and forgets the media pack,
and the symptom is "the Venus skies never come up", with nothing in the log.

So count them at load. Nothing here changes behavior; it only makes that case say so.
"""
from sbs_utils.mast_sbs.story_nodes.media import MediaLabel

PREFIX = "venus_sky_"


def _venus_mine():
    """This pack's labels, picked out of the shared skybox folder by name prefix - the
    folder holds every mod's labels, so LM's own `sky1*` must not be counted here."""
    return [label for label in MediaLabel.folders.get("skybox", [])
            if label.path.startswith(PREFIX)]


def venus_skybox_resolved():
    """How many of this pack's skyboxes have their PNG on disk."""
    return sum(1 for label in _venus_mine() if label.test_file())


def venus_skybox_status():
    """One line for the log: resolved out of declared."""
    return str(venus_skybox_resolved()) + " of " + str(len(_venus_mine())) + " skyboxes resolved"


def venus_skybox_art_missing():
    """True when the mastlib loaded but none of its art did - the media pack is not there."""
    return len(_venus_mine()) > 0 and venus_skybox_resolved() == 0
