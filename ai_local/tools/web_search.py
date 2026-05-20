from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._in_result_link = False
        self._current_url = ""
        self._current_title: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        if tag == "a" and attrs_map.get("class") == "result__a":
            self._in_result_link = True
            self._current_url = attrs_map.get("href") or ""
            self._current_title = []

    def handle_data(self, data: str) -> None:
        if self._in_result_link:
            self._current_title.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result_link:
            title = " ".join(part.strip() for part in self._current_title if part.strip())
            if title and self._current_url:
                self.results.append(SearchResult(title=title, url=self._current_url, snippet=""))
            self._in_result_link = False


def build_search_url(query: str, provider: str = "duckduckgo") -> str:
    encoded = quote_plus(query)
    if provider == "bing":
        return f"https://www.bing.com/search?q={encoded}"
    if provider == "duckduckgo":
        return f"https://html.duckduckgo.com/html/?q={encoded}"
    msg = f"Unsupported web search provider: {provider}"
    raise ValueError(msg)


def web_search(query: str, *, provider: str = "duckduckgo", limit: int = 5) -> list[SearchResult]:
    url = build_search_url(query, provider)
    request = Request(url, headers={"User-Agent": "ai-local/0.1"})
    with urlopen(request, timeout=10) as response:
        html = response.read().decode("utf-8", errors="replace")
    parser = DuckDuckGoHTMLParser()
    parser.feed(html)
    return parser.results[:limit]

