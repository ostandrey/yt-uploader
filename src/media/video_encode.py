"""Shared FFmpeg video quality settings for Coin Wire Shorts."""

# Intermediate passes (normalize, xfade) — high quality to limit generation loss
INTERMEDIATE_ENCODE_ARGS = [
    "-c:v", "libx264",
    "-preset", "slow",
    "-crf", "8",
    "-profile:v", "high",
    "-pix_fmt", "yuv420p",
]

# Final export with burned subtitles — high CRF + VBV floor for YouTube re-encode survival
FINAL_ENCODE_ARGS = [
    "-c:v", "libx264",
    "-preset", "slow",
    "-crf", "8",
    "-profile:v", "high",
    "-level", "4.2",
    "-minrate", "10M",
    "-maxrate", "22M",
    "-bufsize", "44M",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    "-x264-params", "ref=5:aq-mode=3:deadzone-inter=6:deadzone-intra=6",
]

AUDIO_ENCODE_ARGS = ["-c:a", "aac", "-b:a", "256k", "-ar", "48000"]
