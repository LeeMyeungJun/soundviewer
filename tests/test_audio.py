"""Regression checks for audible mono exports, short calls, and the shipped catalog."""
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from download_audio import normalize_audio


def tone(path, amplitude, seconds=2, opposite_stereo=False):
    samples = bytearray()
    for index in range(round(seconds * 44100)):
        value = round(32767 * amplitude * math.sin(2 * math.pi * 700 * index / 44100))
        samples.extend(struct.pack("<hh", value, -value) if opposite_stereo else struct.pack("<h", value))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2 if opposite_stereo else 1)
        output.setsampwidth(2)
        output.setframerate(44100)
        output.writeframes(samples)


class AudioRegressionTests(unittest.TestCase):
    def test_opposite_phase_stereo_keeps_audible_call(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "phase.wav", Path(directory) / "phase.mp3"
            tone(source, 0.2, opposite_stereo=True)
            measured = normalize_audio(source, output)
            self.assertLessEqual(abs(measured["integratedLufs"] + 20), 0.5)
            self.assertLessEqual(measured["truePeakDbtp"], -2.5)

    def test_quiet_short_call_and_loud_call_match_after_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            levels = []
            for ident, amplitude, duration in [("quiet", 0.003, 0.3), ("loud", 0.8, 2)]:
                source, output = Path(directory) / (ident + ".wav"), Path(directory) / (ident + ".mp3")
                tone(source, amplitude, duration)
                levels.append(normalize_audio(source, output)["integratedLufs"])
            self.assertLessEqual(abs(levels[0] - levels[1]), 0.5)

    def test_every_shipped_mp3_has_matching_loudness_and_peak_headroom(self):
        raw = (ROOT / "catalog.js").read_text(encoding="utf-8")
        items = json.loads(raw.removeprefix("globalThis.SOUND_CATALOG = ").rstrip(";\n"))
        for item in items:
            with self.subTest(sound=item["id"]):
                result = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(ROOT / item["audio"]),
                                         "-af", "ebur128=peak=true", "-f", "null", "-"],
                                        check=True, capture_output=True, text=True, encoding="utf-8")
                summary = result.stderr.rsplit("Summary:", 1)[-1]
                integrated = float(re.search(r"I:\s*([-\d.]+) LUFS", summary)[1])
                peak = float(re.search(r"Peak:\s*([-\d.]+) dBFS", summary)[1])
                self.assertLessEqual(abs(integrated + 20), 0.5, f"{integrated} LUFS")
                self.assertLessEqual(peak, -2.5, f"{peak} dBTP")


if __name__ == "__main__":
    unittest.main()
