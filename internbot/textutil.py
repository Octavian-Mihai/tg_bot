from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser


def normalize_text(text: str) -> str:
    """Lowercase and strip accents so 'Montréal' and 'montreal' compare equal."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        self.parts.append(" ")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def html_to_text(html: object) -> str:
    """Strip HTML to prose. Descriptions often arrive entity-escaped twice, so tags are
    stripped again after the first decode."""
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(str(html))
    parser.close()
    text = _TAG_RE.sub(" ", "".join(parser.parts))
    return _WS_RE.sub(" ", text).strip()
