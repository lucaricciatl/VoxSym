"""Test Butler–Volmer and Stern double-layer sources."""

import numpy as np

from voxsym import VoxSym
from voxsym.voxel import Voxel
from voxsym.material import Material
from voxsym.physics.interfacial_electrochemistry import (
    butler_volmer_current,
    stern_double_layer_charge,
)


def test_butler_volmer_zero_overpotential():
    """At zero overpotential the BV current is zero."""
    phi_src = np.array([0.0, 0.5])
    phi_dst = np.array([0.0, 0.5])
    conc = np.array([100.0, 100.0])
    i0 = np.array([10.0, 10.0])
    alpha = np.array([0.5, 0.5])
    j = butler_volmer_current(phi_src, phi_dst, conc, conc, i0, alpha, z=1, T=300.0)
    assert np.allclose(j, 0.0, atol=1e-9)


def test_butler_volmer_oxidation_direction():
    """Positive overpotential drives oxidation (j > 0)."""
    phi_src = np.array([0.2])
    phi_dst = np.array([0.0])
    conc_src = np.array([100.0])
    conc_dst = np.array([100.0])
    i0 = np.array([1.0])
    alpha = np.array([0.5])
    j = butler_volmer_current(phi_src, phi_dst, conc_src, conc_dst, i0, alpha, z=1, T=300.0)
    assert j[0] > 0.1


def test_stern_double_layer_charge_sign():
    """Higher src potential gives positive DL charge on src."""
    phi_src = np.array([0.3])
    phi_dst = np.array([0.0])
    C_s = np.array([0.2])
    sigma = stern_double_layer_charge(phi_src, phi_dst, C_s)
    assert sigma[0] == 0.06


def test_interfacial_sources_on_two_voxels():
    """Two-voxel interface produces non-zero dC/dt and dQ."""
    m = Material(
        name="elec",
        exchange_current_density=10.0,
        charge_transfer_coefficient=0.5,
        stern_capacitance=0.2,
        ionic_valence=1,
    )
    v1 = Voxel(x=0.0, y=0.0, z=0.0, size=1e-5)
    v2 = Voxel(x=1e-5, y=0.0, z=0.0, size=1e-5)
    v1.material = m
    v2.material = Material(name="metal")
    v1.ion_concentration = 100.0
    v2.ion_concentration = 100.0
    v1.potential = 0.1
    v2.potential = 0.0

    vs = VoxSym(backend=None)
    vs.add_voxel(v1)
    vs.add_voxel(v2)
    vs.set_enable_butler_volmer(True)
    vs.set_enable_double_layer(True)
    vs.update()

    # v1 should lose H+ (oxidation), v2 should gain H+
    assert v1.ion_concentration < 100.0
    assert v2.ion_concentration > 100.0
    # DL charge should be non-zero and opposite sign on the two voxels
    assert v1.charge != 0.0
    assert v2.charge != 0.0
    assert np.sign(v1.charge) != np.sign(v2.charge)
