"""Half-body reference path helper stays inside the storage root."""

from __future__ import annotations

import app.core.paths as paths


def test_avatar_halfbody_path_under_storage() -> None:
    p = paths.avatar_halfbody_path(42)
    assert p.name == "reference_halfbody.png"
    assert p.parent.name == "42"
    assert paths.is_within_storage(p)
