"""Tests for adaptive frame skipping."""

from gesturemute.camera.capture import AdaptiveFrameSkip


class TestAdaptiveFrameSkip:
    def test_initial_skip(self):
        a = AdaptiveFrameSkip(initial_skip=2)
        assert a.current_skip == 2

    def test_clamps_initial_skip(self):
        assert AdaptiveFrameSkip(initial_skip=0).current_skip == 1
        assert AdaptiveFrameSkip(initial_skip=10).current_skip == 6

    def test_high_times_increase_skip(self):
        a = AdaptiveFrameSkip(initial_skip=1)
        # Feed 30 high processing times to trigger an adjustment
        for _ in range(30):
            a.record_frame_time(60.0)
        result = a.maybe_adjust()
        assert result == 2
        assert a.current_skip == 2

    def test_low_times_decrease_skip(self):
        a = AdaptiveFrameSkip(initial_skip=4)
        for _ in range(30):
            a.record_frame_time(10.0)
        result = a.maybe_adjust()
        assert result == 3
        assert a.current_skip == 3

    def test_no_adjust_before_interval(self):
        a = AdaptiveFrameSkip(initial_skip=1)
        for _ in range(15):
            a.record_frame_time(60.0)
        result = a.maybe_adjust()
        assert result == 1  # No change yet

    def test_does_not_exceed_max(self):
        a = AdaptiveFrameSkip(initial_skip=6)
        for _ in range(30):
            a.record_frame_time(100.0)
        result = a.maybe_adjust()
        assert result == 6

    def test_does_not_go_below_min(self):
        a = AdaptiveFrameSkip(initial_skip=1)
        for _ in range(30):
            a.record_frame_time(5.0)
        result = a.maybe_adjust()
        assert result == 1

    def test_hysteresis_prevents_oscillation(self):
        """Times between 20-40ms should cause no change."""
        a = AdaptiveFrameSkip(initial_skip=3)
        for _ in range(30):
            a.record_frame_time(30.0)
        result = a.maybe_adjust()
        assert result == 3  # No change in the dead zone

    def test_gradual_increase(self):
        """Multiple adjustment intervals should increase skip gradually."""
        a = AdaptiveFrameSkip(initial_skip=1)
        for cycle in range(3):
            for _ in range(30):
                a.record_frame_time(60.0)
            a.maybe_adjust()
        assert a.current_skip == 4  # 1 -> 2 -> 3 -> 4
