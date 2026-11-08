import unittest

from dualsense.bluetooth_haptics import (
    BluetoothHapticsReportBuilder,
    HapticsPCMGenerator,
    PCM_BYTES,
    REPORT_ID,
    REPORT_SIZE,
    interleave_stereo_pcm,
    validate_bluetooth_crc,
)


class BluetoothHapticsReportTests(unittest.TestCase):
    def setUp(self):
        self.builder = BluetoothHapticsReportBuilder()
        self.pcm = bytes(range(PCM_BYTES))

    def test_haptics_report_layout_and_crc(self):
        report = self.builder.build_haptics_report(self.pcm)
        self.assertEqual(len(report), REPORT_SIZE)
        self.assertEqual(report[0], REPORT_ID)
        self.assertEqual(report[1], 0x00)
        self.assertEqual(report[2:5], bytes((0x91, 0x04, 0x66)))
        self.assertEqual(report[5:8], bytes((48, 48, 0)))
        self.assertEqual(report[8:10], bytes((0x92, PCM_BYTES)))
        self.assertEqual(report[10:74], self.pcm)
        self.assertTrue(validate_bluetooth_crc(report))

    def test_sequence_and_counter_wrap(self):
        self.builder.sequence = 15
        self.builder.packet_counter = 255
        first = self.builder.build_haptics_report(self.pcm)
        second = self.builder.build_haptics_report(self.pcm)
        self.assertEqual(first[1], 0xF0)
        self.assertEqual(first[7], 255)
        self.assertEqual(second[1], 0x00)
        self.assertEqual(second[7], 0)

    def test_init_prime(self):
        state = bytes(range(47))
        report = self.builder.build_init_prime(state)
        self.assertEqual(len(report), REPORT_SIZE)
        self.assertEqual(report[0:4], bytes((0x32, 0x10, 0x90, 0x3F)))
        self.assertEqual(report[4:51], state)
        self.assertTrue(validate_bluetooth_crc(report))

    def test_init_prime_rejects_wrong_state_size(self):
        with self.assertRaises(ValueError):
            self.builder.build_init_prime(b"short")

    def test_pcm_stereo_interleave(self):
        left = [0.0] * 32
        right = [1.0] * 32
        pcm = interleave_stereo_pcm(left, right)
        self.assertEqual(len(pcm), PCM_BYTES)
        self.assertEqual(pcm[0:4], bytes((0, 127, 0, 127)))

    def test_pcm_rejects_wrong_frame_count(self):
        with self.assertRaises(ValueError):
            interleave_stereo_pcm([0.0], [0.0] * 32)

    def test_bad_crc_is_rejected(self):
        report = bytearray(self.builder.build_haptics_report(self.pcm))
        report[20] ^= 0x01
        self.assertFalse(validate_bluetooth_crc(bytes(report)))


class HapticsPCMGeneratorTests(unittest.TestCase):
    def test_render_packet_size_and_range(self):
        generator = HapticsPCMGenerator(seed=1234)
        pcm = generator.render(0.4, 0.2, 0.3, 0.1, 90.0, 0.15)
        self.assertEqual(len(pcm), PCM_BYTES)
        self.assertTrue(all(0 <= byte <= 255 for byte in pcm))

    def test_silence_is_zero(self):
        generator = HapticsPCMGenerator(seed=1234)
        pcm = generator.render(0, 0, 0, 0, 0, 0)
        self.assertEqual(pcm, bytes(PCM_BYTES))

    def test_non_finite_input_rejected(self):
        generator = HapticsPCMGenerator()
        with self.assertRaises(ValueError):
            generator.render(float("nan"), 0, 0, 0, 0, 0)


if __name__ == "__main__":
    unittest.main()
