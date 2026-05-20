from ai_local.tools.web_search import DuckDuckGoHTMLParser, build_search_url


def test_build_search_url_supports_duckduckgo_and_bing() -> None:
    assert build_search_url("hello world", "duckduckgo").startswith(
        "https://html.duckduckgo.com/html/?q=hello+world"
    )
    assert build_search_url("hello world", "bing").startswith(
        "https://www.bing.com/search?q=hello+world"
    )


def test_duckduckgo_parser_extracts_result_links() -> None:
    parser = DuckDuckGoHTMLParser()
    parser.feed('<a class="result__a" href="https://example.com">Example Result</a>')

    assert len(parser.results) == 1
    assert parser.results[0].title == "Example Result"
    assert parser.results[0].url == "https://example.com"

