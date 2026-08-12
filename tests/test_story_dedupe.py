"""Story near-duplicate fingerprints."""

from src.content.story_dedupe import story_fingerprint, titles_similar


def test_same_story_different_wording():
    a = "Fidelity files with SEC to add staking to Ethereum ETF"
    b = "Fidelity's move to add staking to its Ethereum ETF challenges traditional fund structures"
    assert titles_similar(a, b)


def test_unrelated_titles_not_similar():
    a = "Bitcoin slips toward $64,000 ahead of CPI"
    b = "Solana NFT marketplace launches new fee schedule"
    assert not titles_similar(a, b)


def test_fingerprint_stable_for_same_title():
    title = "Fidelity files with SEC to add staking to Ethereum ETF"
    assert story_fingerprint(title) == story_fingerprint(title)
