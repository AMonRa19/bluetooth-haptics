# Bluetooth Haptics for HorizonHaptics

Development branch for adding native DualSense Bluetooth audio-haptics output
to HorizonHaptics v1.3.1.

## Stage 1: report builder

The module `dualsense/bluetooth_haptics.py` builds standalone Bluetooth HID
report `0x32` (142 bytes), including the init-prime state report, 32-frame
stereo signed 8-bit PCM payload at 3 kHz, sequence and packet counters, and
Bluetooth output CRC32.

## Stage 2: PCM renderer

`HapticsPCMGenerator` converts the six haptics parameters already produced by
the Forza parser into 32-frame stereo PCM packets. It preserves oscillator
phase across packets and mirrors the existing USB audio mix (65 Hz low tone,
200 Hz/noise surface texture, and RPM-driven sawtooth engine component).

## Stage 3: live HID integration

`dualsense/bluetooth_stream.py` now manages the Bluetooth haptics session:
it sends the init-prime report using the current 47-byte DualSense output-state
payload, then schedules PCM reports at 3 kHz (one 32-frame packet every
10.67 ms). The stream runs from the existing single HID writer thread, so
trigger/lightbar and PCM writes are serialized on the same device handle.

`worker.py` now forwards the Forza parser's six body-haptics values to that
stream. Bluetooth uses the native HID PCM lane; the existing USB
`AudioHaptics` path remains in place. Steam Input is not disabled by this
integration. When body haptics are enabled, the existing output flags select
the controller's audio-haptics path as defined by the upstream project.

Automated tests cover report layout/CRC, init-prime, PCM rendering, stream
cadence, disabling/silence, and session reset. **Real-controller Bluetooth
validation is still pending**; no claim is made yet that every DualSense
hardware revision accepts the stream identically.

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
