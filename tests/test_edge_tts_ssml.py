from src.media.edge_tts_audio import emphasize_ssml, strip_ssml


def test_emphasize_ssml_wraps_entity_and_date():
    out = emphasize_ssml("The CFTC meets August 20 on crypto rules.")
    assert "<prosody" in out
    assert "CFTC" in out
    assert "20" in out
    assert "The " in strip_ssml(out)
    assert "crypto" in strip_ssml(out)
    assert "<prosody" not in strip_ssml(out)


def test_emphasize_ssml_skips_filler_words():
    out = emphasize_ssml("Follow Coin Wire for daily crypto news.")
    assert "Follow" in out
    assert out.count("<prosody") <= 1
