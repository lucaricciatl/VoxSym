"""Tests for the Voxel data model."""

import numpy as np
import pytest

from voxsym import Voxel
from voxsym.material import COPPER, WATER


def test_voxel_creation():
    v = Voxel(1.0, 2.0, 3.0, 0.5, temperature=400.0)
    assert v.x == 1.0
    assert v.y == 2.0
    assert v.z == 3.0
    assert v.size == 0.5
    assert v.temperature == 400.0


def test_voxel_default_fields():
    v = Voxel(0.0, 0.0, 0.0, 1.0)
    assert v.material is None
    assert v.charge == 0.0
    assert v.opacity == 1.0
    assert v.pressure == 101.3
    assert v.ion_concentration == 0.0
    np.testing.assert_array_equal(v.electric_field, np.zeros(3))
    np.testing.assert_array_equal(v.magnetic_field, np.zeros(3))


def test_voxel_material_assignment():
    v = Voxel(0.0, 0.0, 0.0, 1.0)
    v.set_material(COPPER)
    assert v.material is COPPER
    assert v.material.name == "copper"

    v.set_material(WATER)
    assert v.material.name == "water"


def test_voxel_coordinate_math():
    v = Voxel(1.0, 2.0, 3.0, 0.5)
    assert v.get_coordinates() == (1.0, 2.0, 3.0)

    v.set_coordinates(4.0, 5.0, 6.0)
    assert v.get_coordinates() == (4.0, 5.0, 6.0)

    v.set_size(2.0)
    assert v.get_size() == 2.0


def test_voxel_neighbors():
    a = Voxel(0.0, 0.0, 0.0, 1.0)
    b = Voxel(1.0, 0.0, 0.0, 1.0)
    a.set_neighbor("+x", b)
    assert a.get_neighbor("+x") is b
    assert a.get_neighbor("-x") is None


def test_voxel_repr():
    v = Voxel(1.0, 2.0, 3.0, 0.5)
    assert repr(v) == "Voxel(x=1.0, y=2.0, z=3.0, size=0.5)"
