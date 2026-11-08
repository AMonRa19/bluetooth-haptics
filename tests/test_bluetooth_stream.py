import unittest

from dualsense.bluetooth_stream import BluetoothHapticsStream
from dualsense.bluetooth_haptics import REPORT_ID, validate_bluetooth_crc


class BluetoothHapticsStreamTests(unittest.TestCase):
    def setUp(self):
        self.reports = []
        self.state = bytes(range(47))
        self.stream = BluetoothHapticsStream(self.reports.append, lambda: self.state)

    def test_first_tick_primes_then_sends_pcm(self):
        self.stream.update(0.2, 0.1, 0.3, 0.15, 90.0, 0.2, enabled=True)
        self.assertTrue(self.stream.tick(now=10.0))
        self.assertEqual(len(self.reports), 2)

        prime, pcm = self.reports
        self.assertEqual(prime[0], REPORT_ID)
        self.assertEqual(prime[1:4], bytes((0x10, 0x90, 0x3F)))
        self.assertEqual(prime[4:51], self.state)
        self.assertTrue(validate_bluetooth_crc(prime))

        self.assertEqual(pcm[0], REPORT_ID)
        self.assertEqual(pcm[2:5], bytes((0x91, 0x04, 0x66)))
        self.assertTrue(validate_bluetooth_crc(pcm))

    def test_tick_respects_pcm_interval(self):
        self.stream.update(0.2, 0.1, 0.3, 0.15, 90.0, 0.2, enabled=True)
        self.stream.tick(now=1.0)
        count = len(self.reports)
        self.stream.tick(now=1.005)
        self.assertEqual(len(self.reports), count)
        self.stream.tick(now=1.011)
        self.assertEqual(len(self.reports), count + 1)

    def test_disabling_stream_sends_silence_and_resets(self):
        self.stream.update(0.2, 0.1, 0.3, 0.15, 90.0, 0.2, enabled=True)
        self.stream.tick(now=2.0)
        self.stream.update(0, 0, 0, 0, 0, 0, enabled=False)
        self.assertTrue(self.stream.tick(now=2.02))
        self.assertEqual(self.reports[-1][10:74], bytes(64))
        count = len(self.reports)
        self.assertFalse(self.stream.tick(now=2.04))
        self.assertEqual(len(self.reports), count)

    def test_reset_restarts_session_with_init_prime(self):
        self.stream.update(0.2, 0.1, 0.3, 0.15, 90.0, 0.2, enabled=True)
        self.stream.tick(now=3.0)
        count = len(self.reports)
        self.stream.reset()
        self.stream.tick(now=4.0)
        self.assertEqual(len(self.reports), count + 2)
        self.assertEqual(self.reports[-2][1], 0x10)


if __name__ == "__main__":
    unittest.main()
