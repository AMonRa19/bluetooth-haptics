# Bluetooth Haptics for HorizonHaptics

Development branch for adding native DualSense Bluetooth audio-haptics output
to HorizonHaptics v1.3.1.

## Bluetooth output

The module `dualsense/bluetooth_haptics.py` builds the standalone Bluetooth HID
report `0x32` (142 bytes), including the init-prime state report, 32-frame
stereo signed 8-bit PCM payload at 3 kHz, sequence and packet counters, and
Bluetooth output CRC32.

`HapticsPCMGenerator` converts the six haptics parameters produced by the
Forza parser into 32-frame stereo PCM packets. It preserves oscillator phase
across packets and mirrors the existing USB audio mix (65 Hz low tone,
200 Hz/noise surface texture, and RPM-driven sawtooth engine component).

`dualsense/bluetooth_stream.py` manages the Bluetooth haptics session: it
sends init-prime using the current 47-byte DualSense output-state payload, then
schedules PCM reports at 3 kHz (one 32-frame packet every 10.67 ms). The stream
runs from the existing single HID writer thread, so trigger/lightbar and PCM
writes are serialized on the same device handle.

`worker.py` forwards the Forza parser's six body-haptics values to that
stream. Bluetooth uses the native HID PCM lane; the existing USB
`AudioHaptics` path remains in place. Steam Input itself is not disabled.

The **Motor & Vibration Tuning** section provides separate controls for
overall left/right motor strength and the vibration layer. Engine, collision,
and tire-slip levels can also be adjusted independently. The lower starting
gains are 65% overall motor strength, 45% vibration, 55% engine, 50% collision,
and 50% tire-slip intensity. These controls affect body haptics only; L2/R2
adaptive trigger strength is unchanged.

## Windows preview release

The `Windows Release` GitHub Actions workflow builds a Windows x64
single-file executable named `HorizonHaptics-Bluetooth.exe`, packages it in
a portable ZIP, and publishes both files as assets of a prerelease in the
repository's **Releases** section.

The workflow can be started manually from Actions or by pushing a commit to
`bluetooth-haptics` with `[build-exe]` in its commit message. The current
preview version is `1.0.0`. The packaged updater checks this repository
and installs future `*-win64.zip` releases.

## Tests

Run from the repository root:

```sh
python -m compileall -q .
python -m unittest discover -s tests -v
```

Automated tests cover report layout/CRC, init-prime, PCM rendering, stream
cadence, disabling/silence, session reset, and independent motor/vibration
gain behavior. **Real-controller Bluetooth
validation is still pending**; no claim is made yet that every DualSense
hardware revision accepts the stream identically.

## Upstream and protocol attribution

The application is published as HorizonHaptics Bluetooth v1.0.0 and is based on HorizonHaptics v1.3.1 by Haritha Rathnayake.
The Bluetooth audio-haptics report layout is implemented from the
DualSenseClient Bluetooth output-report reference. Preserve the upstream
MIT license when incorporating upstream source files.
