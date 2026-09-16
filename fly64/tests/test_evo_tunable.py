"""
Tests for EVO tunable parameter expansion.
Verifies all fix_template-critical parameters exist in brain_tunable_params.json.
"""

import json


class TestEvoTunable:

    def _load_params(self):
        with open('skills/brain_tunable_params.json', encoding='utf-8') as f:
            return json.load(f)

    def test_fallen_params_exist(self):
        """Fallen recovery parameters should be tunable."""
        d = self._load_params()
        p = d['params']
        assert 'escape.fallen_forward' in p
        assert 'escape.fallen_jump_boost' in p
        assert 'escape.fallen_switch_s' in p

    def test_reflex_params_exist(self):
        """Reflex cooldown parameters should be tunable."""
        d = self._load_params()
        p = d['params']
        assert 'reflex.cooldown_min' in p
        assert 'reflex.adaptive_cooldown_scale' in p

    def test_params_have_ranges(self):
        """All params should have min/max/default."""
        d = self._load_params()
        for name, spec in d['params'].items():
            assert 'min' in spec, '%s missing min' % name
            assert 'max' in spec, '%s missing max' % name
            assert 'default' in spec, '%s missing default' % name
            assert spec['min'] <= spec['default'] <= spec['max'], \
                '%s default %.2f not in [%.2f, %.2f]' % (name, spec['default'], spec['min'], spec['max'])