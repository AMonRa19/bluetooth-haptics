"""DualSense Bluetooth audio-haptics output report builder.

Implements the standalone 0x32 Bluetooth HID audio-haptics lane.
The module deliberately does not open HID devices; transport integration is
kept separate so report construction can be tested without a controller.

Protocol layout is based on DualSenseClient's BluetoothAudioReportBuilder.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Iterable

REPORT_ID = 0x32
REPORT_SIZE = 142
CRC_SIZE = 4
CRC_OFFSET = REPORT_SIZE - CRC_SIZE
PCM_RATE = 3000
PCM_CHANNELS = 2
PCM_FRAMES = 32
PCM_BYTES = PCM_FRAMES * PCM_CHANNELS  # signed 8-bit stereo

DEFAULT_AUDIO_BUFFER_LENGTH = 48


def append_bluetooth_crc(report: bytearray) -> bytes:
    """Write the DualSense Bluetooth output CRC into the final four bytes."""
    if len(report) < CRC_SIZE + 1:
        raise ValueError("Report is too short for a Bluetooth CRC")
    crc = zlib.crc32(b"\xA2" + bytes(report[:-CRC_SIZE])) & 0xFFFFFFFF
    struct.pack_into("<I", report, len(report) - CRC_SIZE, crc)
    return bytes(report)


def validate_bluetooth_crc(report: bytes) -> bool:
    """Return whether the trailing CRC matches the Bluetooth output payload."""
    if len(report) < CRC_SIZE + 1:
        return False
    expected = zlib.crc32(b"\xA2" + report[:-CRC_SIZE]) & 0xFFFFFFFF
    actual = struct.unpack_from("<I", report, len(report) - CRC_SIZE)[0]
    return actual == expected


def _byte(value: int) -> int:
    return max(0, min(255, int(value)))


def _pcm_sample(value: float | int) -> int:
    """Convert a normalized float (-1..1) or signed PCM sample to int8."""
    sample = float(value)
    if -1.0 <= sample <= 1.0:
        sample *= 127.0
    return max(-127, min(127, int(round(sample))))


def interleave_stereo_pcm(left: Iterable[float | int],
                          right: Iterable[float | int]) -> bytes:
    """Encode 32 left/right samples as 64 interleaved signed 8-bit PCM bytes.

    Float samples are expected in -1.0..1.0. Integer samples in that range
    are interpreted as normalized floats; other integers are treated as
    signed PCM amplitudes and clamped to -127..127.
    """
    left_samples = list(left)
    right_samples = list(right)
    if len(left_samples) != PCM_FRAMES or len(right_samples) != PCM_FRAMES:
        raise ValueError(f"Expected {PCM_FRAMES} samples per channel")

    out = bytearray(PCM_BYTES)
    for index, (l_sample, r_sample) in enumerate(zip(left_samples, right_samples)):
        out[index * 2] = _pcm_sample(l_sample) & 0xFF
        out[index * 2 + 1] = _pcm_sample(r_sample) & 0xFF
    return bytes(out)


class BluetoothHapticsReportBuilder:
    """Build standalone DualSense Bluetooth 0x32 haptics reports.

    Sequence is encoded in the high nibble of byte 1 and wraps at 16.
    The packet counter is byte 7 and wraps at 256.
    """

    def __init__(self, audio_buffer_length: int = DEFAULT_AUDIO_BUFFER_LENGTH):
        if not 0 <= audio_buffer_length <= 255:
            raise ValueError("audio_buffer_length must fit in one byte")
        self.audio_buffer_length = audio_buffer_length
        self.sequence = 0
        self.packet_counter = 0

    def reset(self) -> None:
        self.sequence = 0
        self.packet_counter = 0

    def build_init_prime(self, state_report: bytes) -> bytes:
        """Build the initial 0x32 report carrying a 47-byte controller state."""
        if len(state_report) != 47:
            raise ValueError("state_report must contain exactly 47 bytes")

        report = bytearray(REPORT_SIZE)
        report[0] = REPORT_ID
        report[1] = 0x10
        report[2] = 0x90
        report[3] = 0x3F
        report[4:51] = state_report
        return append_bluetooth_crc(report)

    def build_haptics_report(self, pcm_stereo: bytes) -> bytes:
        """Build one 0x32 report containing 32 stereo signed-8-bit PCM frames."""
        if len(pcm_stereo) != PCM_BYTES:
            raise ValueError(f"pcm_stereo must contain exactly {PCM_BYTES} bytes")

        report = bytearray(REPORT_SIZE)
        report[0] = REPORT_ID
        report[1] = (self.sequence & 0x0F) << 4
        report[2] = 0x91
        report[3] = 0x04
        report[4] = 0x66
        report[5] = self.audio_buffer_length
        report[6] = self.audio_buffer_length
        report[7] = self.packet_counter
        report[8] = 0x92
        report[9] = PCM_BYTES
        report[10:10 + PCM_BYTES] = pcm_stereo

        result = append_bluetooth_crc(report)
        self.sequence = (self.sequence + 1) & 0x0F
        self.packet_counter = (self.packet_counter + 1) & 0xFF
        return result


class HapticsPCMGenerator:
    """Generate the project's six-channel haptics mix as 3 kHz signed-8 PCM.

    Input amplitudes use the same normalized 0..1 scale as AudioHaptics.
    The generator keeps oscillator phase between packets to avoid clicks.
    """

    def __init__(self, sample_rate: int = PCM_RATE, seed: int | None = None):
        import math
        import random

        if sample_rate != PCM_RATE:
            raise ValueError(f"DualSense Bluetooth haptics expects {PCM_RATE} Hz")
        self.sample_rate = sample_rate
        self._math = math
        self._rng = random.Random(seed)
        self._phase_low = 0.0
        self._phase_high = 0.0
        self._phase_engine = 0.0

    def reset(self) -> None:
        self._phase_low = 0.0
        self._phase_high = 0.0
        self._phase_engine = 0.0

    def render(
        self,
        l_low: float,
        l_high: float,
        r_low: float,
        r_high: float,
        engine_freq: float,
        engine_vol: float,
    ) -> bytes:
        """Render one 32-frame stereo packet (10.67 ms at 3 kHz)."""
        values = (l_low, l_high, r_low, r_high, engine_freq, engine_vol)
        if not all(self._math.isfinite(float(v)) for v in values):
            raise ValueError("Haptics parameters must be finite numbers")

        left = []
        right = []
        tau = 2.0 * self._math.pi
        low_step = 65.0 / self.sample_rate
        high_step = 200.0 / self.sample_rate
        engine_step = max(0.0, float(engine_freq)) / self.sample_rate

        for _ in range(PCM_FRAMES):
            low = self._math.sin(tau * self._phase_low)
            tone = self._math.sin(tau * self._phase_high)
            noise = self._rng.uniform(-1.0, 1.0)
            high = noise * 0.7 + tone * 0.3

            # Sawtooth engine texture, matching the USB audio renderer.
            engine = 2.0 * (self._phase_engine - self._math.floor(self._phase_engine + 0.5))
            engine *= float(engine_vol)

            left.append(max(-1.0, min(1.0, low * float(l_low) + high * float(l_high) + engine)))
            right.append(max(-1.0, min(1.0, low * float(r_low) + high * float(r_high) + engine)))

            self._phase_low = (self._phase_low + low_step) % 1.0
            self._phase_high = (self._phase_high + high_step) % 1.0
            self._phase_engine = (self._phase_engine + engine_step) % 1.0

        return interleave_stereo_pcm(left, right)
