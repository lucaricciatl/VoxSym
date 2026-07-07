"""Test ion-intercalation dependent MXene conductivity."""

import numpy as np
import pytest

from voxsym.material import Material


def test_effective_conductivity_power_law():
    m = Material(
        name="mxene_test",
        conductivity=1e3,
        conductivity_ion_min=1e2,
        conductivity_ion_max=1e4,
        conductivity_ion_exponent=2.0,
        ion_conc_max=1000.0,
    )
    assert m.effective_conductivity(0.0) == pytest.approx(1e2, rel=1e-6)
    assert m.effective_conductivity(1000.0) == pytest.approx(1e4, rel=1e-6)
    # at c=500 (half max), f=0.5^2=0.25 -> sigma = 100 + 9900*0.25 = 2575
    assert m.effective_conductivity(500.0) == pytest.approx(2575.0, rel=1e-6)


def test_effective_conductivity_no_effect():
    m = Material(name="inert", conductivity=1e3, ion_conc_max=0.0)
    assert m.effective_conductivity(100.0) == pytest.approx(1e3, rel=1e-6)
