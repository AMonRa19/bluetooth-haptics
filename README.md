# Bluetooth Haptics for HorizonHaptics

Development branch for adding native DualSense Bluetooth audio-haptics output
to HorizonHaptics v1.3.1.

## Stage 1: report builder

The first implementation is isolated in `dualsense/bluetooth_haptics.py`.
It builds standalone Bluetooth HID report `0x32` (142 bytes), including:

- init-prime state report;
- 32-frame stereo signed 8-bit PCM haptics payload at 3 kHz;
- sequence and packet counters;
- Bluetooth output CRC32.

This stage does not yet connect the report builder to the live HID writer or
the Forza telemetry worker. That integration must preserve the existing USB
audio path and must be validated on the actual DualSense over Bluetooth.

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
