from __future__ import annotations

import unicodedata


def normalize_text(text: str) -> str:
    """Lowercase and strip accents so 'Montréal' and 'montreal' compare equal."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
