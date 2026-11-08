# Bluetooth Haptics for HorizonHaptics

Development branch for adding native DualSense Bluetooth audio-haptics output
to HorizonHaptics v1.3.1.

## Stage 1: report builder

The isolated module `dualsense/bluetooth_haptics.py` builds standalone
Bluetooth HID report `0x32` (142 bytes), including the init-prime state
report, 32-frame stereo signed 8-bit PCM payload at 3 kHz, sequence and packet
counters, and Bluetooth output CRC32.

## Stage 2: PCM renderer

`HapticsPCMGenerator` converts the six haptics parameters already produced by
the Forza parser into 32-frame stereo PCM packets. It preserves oscillator
phase across packets and mirrors the existing USB audio mix (65 Hz low tone,
200 Hz/noise surface texture, and RPM-driven sawtooth engine component).

The renderer and report builder are still transport-independent. They do not
yet write to the live HID device. The next integration stage must coordinate
the 0x32 haptics session with the existing controller state reports and retain
the USB audio path unchanged. Actual Bluetooth behavior must be validated on
the user's DualSense before claiming device compatibility.

## Tests

Run from the repository root:

```sh
python -m unittest discover -s tests -v
```

## Upstream and protocol attribution

The base application is HorizonHaptics v1.3.1 by Haritha Rathnayake.
The Bluetooth audio-haptics report layout is implemented from the
DualSenseClient Bluetooth output-report reference. Preserve the upstream
MIT license when incorporating upstream source files.
