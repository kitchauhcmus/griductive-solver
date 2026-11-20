"""Resolve local player art without probing missing URLs in the browser."""
from pathlib import Path

from ..roster import BY_SLUG

MIME = {".png": "image/png", ".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def portrait_index(directory: Path) -> dict[str, Path]:
    # Sorting also resolves case-only duplicates consistently on Linux.
    priority = {suffix: index for index, suffix in enumerate(MIME)}
    try:
        entries = sorted(directory.iterdir(), key=lambda p: (
            priority.get(p.suffix.lower(), len(priority)), p.name.casefold(), p.name
        ))
    except FileNotFoundError:
        return {}
    found = {}
    for path in entries:
        slug = path.stem.casefold()
        if (slug in BY_SLUG and path.suffix.lower() in MIME and not path.is_symlink()
                and path.is_file()):
            found.setdefault(slug, path)
    return found
