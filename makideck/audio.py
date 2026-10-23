"""System-audio levels for the music visualizer, from a loopback input.

macOS can't tap the output mix directly, so this listens to a loopback device:
install BlackHole (`brew install blackhole-2ch`), then run
`swift tools/multi_output.swift` (or build a Multi-Output Device of your
speakers + BlackHole 2ch in Audio MIDI Setup) and make it the system output.
Without such a device `start()` returns False and the visualizer falls back
to a synthetic beat.
"""
from __future__ import annotations

import logging
import math
import threading
import time

log = logging.getLogger(__name__)

_BANDS = ((30, 150), (150, 2000), (2000, 10000))   # bass, mid, high (Hz)
_SILENCE_RMS = 1e-4


class Analyzer:
    def __init__(self, device_hint: str = "BlackHole") -> None:
        self.device_hint = device_hint
        self._lock = threading.Lock()
        self._levels = (0.0, 0.0, 0.0)
        self._peaks = [1e-6] * len(_BANDS)
        self._avg_bass = 0.0
        self._beat_at = 0.0
        self._heard_at = 0.0
        self._stream = None

    def start(self) -> bool:
        try:
            import numpy as np
            import sounddevice as sd
        except Exception as e:                       # PortAudio missing etc.
            log.info("audio: unavailable (%s)", e)
            return False
        devices = [i for i, d in enumerate(sd.query_devices())
                   if self.device_hint.lower() in d["name"].lower()
                   and d["max_input_channels"] > 0]
        if not devices:
            log.info("audio: no '%s' input — synthetic beat", self.device_hint)
            return False
        info = sd.query_devices(devices[0])
        rate = int(info["default_samplerate"])
        block = 1024
        freqs = np.fft.rfftfreq(block, 1 / rate)
        masks = [(freqs >= lo) & (freqs < hi) for lo, hi in _BANDS]
        window = np.hanning(block)

        def callback(indata, frames, t, status) -> None:
            mono = indata.mean(axis=1)
            if len(mono) != block:
                return
            now = time.monotonic()
            if float(np.sqrt(np.mean(mono ** 2))) < _SILENCE_RMS:
                with self._lock:
                    self._levels = (0.0, 0.0, 0.0)
                return
            spec = np.abs(np.fft.rfft(mono * window))
            levels = []
            for i, m in enumerate(masks):
                v = float(spec[m].mean())
                # Slow-decaying peak = automatic gain, so quiet tracks still move.
                self._peaks[i] = max(v, self._peaks[i] * 0.998)
                levels.append(min(1.0, v / self._peaks[i]))
            bass = levels[0]
            self._avg_bass += (bass - self._avg_bass) * 0.05
            with self._lock:
                self._levels = tuple(levels)
                self._heard_at = now
                if (bass > self._avg_bass * 1.3 and bass > 0.35
                        and now - self._beat_at > 0.22):
                    self._beat_at = now

        self._stream = sd.InputStream(device=devices[0], channels=min(2, info["max_input_channels"]),
                                      samplerate=rate, blocksize=block,
                                      callback=callback)
        self._stream.start()
        log.info("audio: listening on %s @ %d Hz", info["name"], rate)
        return True

    @property
    def active(self) -> bool:
        """Audio is flowing (not just a silent loopback)."""
        with self._lock:
            return time.monotonic() - self._heard_at < 0.5

    def levels(self) -> tuple[float, float, float, float]:
        """(bass, mid, high, beat) in 0..1; beat decays after each onset."""
        with self._lock:
            bass, mid, high = self._levels
            since = time.monotonic() - self._beat_at
        return bass, mid, high, math.exp(-since * 6)

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.close()
