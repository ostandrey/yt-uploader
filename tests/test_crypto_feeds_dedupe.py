"""Posted-article near-duplicate cache."""

from src.content.crypto_feeds import CryptoNewsFetcher


def test_mark_posted_blocks_similar_title(tmp_path):
    cache = tmp_path / "posted.json"
    fetcher = CryptoNewsFetcher(posted_cache_path=cache)
    first = {
        "title": "Fidelity files with SEC to add staking to Ethereum ETF",
        "link": "https://cointelegraph.com/a",
        "hash": "hash-a",
    }
    fetcher.mark_posted(first)
    second = {
        "title": "Fidelity files with the SEC to add staking to its Ethereum ETF",
        "link": "https://www.coindesk.com/b",
        "hash": "hash-b",
    }
    assert fetcher.is_duplicate_story(second) is True


def test_unrelated_not_duplicate(tmp_path):
    cache = tmp_path / "posted.json"
    fetcher = CryptoNewsFetcher(posted_cache_path=cache)
    fetcher.mark_posted(
        {
            "title": "Fidelity files with SEC to add staking to Ethereum ETF",
            "link": "https://cointelegraph.com/a",
            "hash": "hash-a",
        }
    )
    other = {
        "title": "Bitcoin ETF sees record weekly outflows",
        "link": "https://cointelegraph.com/c",
        "hash": "hash-c",
    }
    assert fetcher.is_duplicate_story(other) is False
