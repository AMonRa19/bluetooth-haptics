import unittest

from Config.surface_settings import SurfaceSettings
from GameParsers.forza_parser import DataPacket
from GameParsers.parser import Parser
from preferences import _apply


class BodyHapticsGainTests(unittest.TestCase):
    def _packet(self):
        return DataPacket(
            is_race_on=True,
            surface_rumble_fl=0.5,
            surface_rumble_fr=0.5,
            surface_rumble_rl=0.5,
            surface_rumble_rr=0.5,
        )

    def test_motor_strength_and_vibration_gain_are_independent(self):
        settings = SurfaceSettings(
            enable_body_haptics=True,
            enable_slip_haptics=False,
            haptic_intensity=0.5,
            vibration_intensity=0.25,
            engine_haptics_volume=1.0,
        )
        parser = Parser(surface=settings)

        left_low, left_high, right_low, right_high, engine_freq, engine_vol = (
            parser._audio_haptics(self._packet())
        )

        self.assertEqual(left_low, 0.0)
        self.assertAlmostEqual(left_high, 0.09375)
        self.assertEqual(right_low, 0.0)
        self.assertAlmostEqual(right_high, 0.09375)
        self.assertEqual(engine_freq, 40.0)
        # The vibration control affects road/surface vibration, not the
        # separate engine channel; overall motor strength still applies.
        self.assertAlmostEqual(engine_vol, 0.04)

    def test_zero_vibration_gain_mutes_surface_but_not_engine_channel(self):
        settings = SurfaceSettings(
            enable_body_haptics=True,
            enable_slip_haptics=False,
            haptic_intensity=0.5,
            vibration_intensity=0.0,
            engine_haptics_volume=0.5,
        )
        parser = Parser(surface=settings)

        result = parser._audio_haptics(self._packet())

        self.assertEqual(result[:4], (0.0, 0.0, 0.0, 0.0))
        self.assertAlmostEqual(result[5], 0.02)

    def test_haptics_gains_default_to_reduced_levels(self):
        settings = SurfaceSettings()

        self.assertEqual(settings.haptic_intensity, 0.65)
        self.assertEqual(settings.vibration_intensity, 0.45)
        self.assertEqual(settings.engine_haptics_volume, 0.55)
        self.assertEqual(settings.collision_haptics_volume, 0.50)
        self.assertEqual(settings.slip_intensity, 0.50)

    def test_legacy_saved_gain_values_are_clamped(self):
        settings = SurfaceSettings()
        _apply(
            settings,
            {
                "haptic_intensity": 2.5,
                "vibration_intensity": -0.2,
                "engine_haptics_volume": 1.4,
                "collision_haptics_volume": 0.25,
                "slip_intensity": 4.0,
            },
            SurfaceSettings,
        )

        self.assertEqual(settings.haptic_intensity, 1.0)
        self.assertEqual(settings.vibration_intensity, 0.0)
        self.assertEqual(settings.engine_haptics_volume, 1.0)
        self.assertEqual(settings.collision_haptics_volume, 0.25)
        self.assertEqual(settings.slip_intensity, 1.0)


if __name__ == "__main__":
    unittest.main()
