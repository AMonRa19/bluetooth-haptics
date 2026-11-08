"""Timed Bluetooth haptics stream for the DualSense 0x32 HID lane.

The stream is driven from the controller's single HID writer thread so PCM
reports never race trigger/lightbar output reports on the same handle.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from .bluetooth_haptics import (
    BluetoothHapticsReportBuilder,
    HapticsPCMGenerator,
    PCM_FRAMES,
    PCM_RATE,
)


class BluetoothHapticsStream:
    """Schedule init-prime and 3 kHz stereo PCM reports on one writer thread."""

    INTERVAL = PCM_FRAMES / PCM_RATE

    def __init__(
        self,
        write_report: Callable[[bytes], object],
        get_state_report: Callable[[], bytes],
    ) -> None:
        self._write_report = write_report
        self._get_state_report = get_state_report
        self._builder = BluetoothHapticsReportBuilder()
        self._generator = HapticsPCMGenerator()
        self._lock = threading.Lock()
        self._enabled = False
        self._values = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self._active = False
        self._next_report_at = 0.0

    def update(
        self,
        l_low: float,
        l_high: float,
        r_low: float,
        r_high: float,
        engine_freq: float,
        engine_vol: float,
        *,
        enabled: bool = True,
    ) -> None:
        values = (l_low, l_high, r_low, r_high, engine_freq, engine_vol)
        with self._lock:
            self._values = values
            self._enabled = bool(enabled)

    def reset(self) -> None:
        """Reset stream timing/counters after HID disconnect or reconnect."""
        with self._lock:
            self._active = False
            self._next_report_at = 0.0
            self._builder.reset()
            self._generator.reset()

    def tick(self, now: float | None = None) -> bool:
        """Send due reports. Returns True when at least one report was written."""
        if now is None:
            now = time.monotonic()

        with self._lock:
            if not self._enabled:
                if not self._active:
                    return False
                pcm = bytes(64)
                self._write_report(self._builder.build_haptics_report(pcm))
                self._active = False
                self._next_report_at = 0.0
                self._builder.reset()
                self._generator.reset()
                return True

            if not self._active:
                self._builder.reset()
                self._generator.reset()
                state = self._get_state_report()
                self._write_report(self._builder.build_init_prime(state))
                self._active = True
                self._next_report_at = now

            if now < self._next_report_at:
                return True

            pcm = self._generator.render(*self._values)
            self._write_report(self._builder.build_haptics_report(pcm))
            self._next_report_at = now + self.INTERVAL
            return True
