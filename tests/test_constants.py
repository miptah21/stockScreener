"""
Test suite for utils/constants.py — Centralized constants.
"""

from utils.constants import MARKET_CAP_PRESETS


class TestMarketCapPresets:
    """Tests for MARKET_CAP_PRESETS centralized constant."""

    def test_presets_exist(self):
        assert MARKET_CAP_PRESETS is not None
        assert isinstance(MARKET_CAP_PRESETS, dict)

    def test_required_keys(self):
        expected_keys = ['all', 'micro', 'small', 'mid', 'large', 'mega']
        for key in expected_keys:
            assert key in MARKET_CAP_PRESETS, f"Missing preset key: {key}"

    def test_each_preset_has_label_min_max(self):
        for key, preset in MARKET_CAP_PRESETS.items():
            assert 'label' in preset, f"{key} missing 'label'"
            assert 'min' in preset, f"{key} missing 'min'"
            assert 'max' in preset, f"{key} missing 'max'"

    def test_all_preset_has_no_bounds(self):
        preset = MARKET_CAP_PRESETS['all']
        assert preset['min'] is None
        assert preset['max'] is None

    def test_mega_has_no_upper_bound(self):
        preset = MARKET_CAP_PRESETS['mega']
        assert preset['min'] is not None
        assert preset['max'] is None

    def test_micro_has_no_lower_bound(self):
        preset = MARKET_CAP_PRESETS['micro']
        assert preset['min'] is None
        assert preset['max'] is not None

    def test_presets_ordering_is_consistent(self):
        """Verify min/max values increase monotonically."""
        ordered = ['micro', 'small', 'mid', 'large', 'mega']
        for i in range(len(ordered) - 1):
            current = MARKET_CAP_PRESETS[ordered[i]]
            next_p = MARKET_CAP_PRESETS[ordered[i + 1]]
            c_max = current.get('max')
            n_min = next_p.get('min')
            if c_max is not None and n_min is not None:
                assert c_max <= n_min, f"{ordered[i]}.max should <= {ordered[i+1]}.min"

    def test_screeners_import_same_presets(self):
        """Verify both screeners import from centralized constants."""
        from screeners.technical_screener import MARKET_CAP_PRESETS as tech_presets
        from screeners.simple_screener import MARKET_CAP_PRESETS as simple_presets
        assert tech_presets is MARKET_CAP_PRESETS
        assert simple_presets is MARKET_CAP_PRESETS
