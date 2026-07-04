"""Headless sanity tests for Tasks 13 & 14."""

import numpy as np


def test_poisson_point_charge():
    from voxsym import VoxSym, Voxel

    vs = VoxSym(backend=None)
    # 5×5×5 grid, place a positive charge in the centre
    for x in range(-2, 3):
        for y in range(-2, 3):
            for z in range(-2, 3):
                v = Voxel(float(x), float(y), float(z), 1.0)
                if x == 0 and y == 0 and z == 0:
                    v.charge = 1.0
                vs.add_voxel(v)

    vs.solve_poisson(max_iter=2000, tol=1e-5)

    centre = vs.voxels[(len(vs.voxels)) // 2]
    assert centre.phi > 0, "potential at positive charge should be positive"

    # E-field should point outward (roughly radial) on +x face
    e_norms = []
    for v in vs.voxels:
        if v.x == 2 and v.y == 0 and v.z == 0:
            e_norms.append(np.linalg.norm(v.electric_field))
    assert e_norms, "expected a voxel on +x face"
    assert max(e_norms) > 0, "E-field magnitude should be positive away from charge"
    print("poisson point-charge: OK")


def test_charge_conservation():
    from voxsym import VoxSym, Voxel
    from voxsym.material import Material

    electrolyte = Material(
        name="electrolyte",
        conductivity=1.0,
        thermal_conductivity=1.0,
        specific_heat=1000.0,
        density=1000.0,
        ion_diffusivity=1e-9,
        ionic_valence=1,
        ion_conc_max=1000.0,
        color=(200, 200, 200),
    )

    vs = VoxSym(backend=None)
    for x in range(-2, 3):
        for y in range(-2, 3):
            for z in range(-2, 3):
                v = Voxel(float(x), float(y), float(z), 1.0)
                v.material = electrolyte
                v.ion_concentration = 100.0
                vs.add_voxel(v)

    vs._ensure_ion_solver().set_conserve_charge(enabled=True, conserved_total=True)
    vs.set_time_step(1e-6)

    total_before = sum(v.charge for v in vs.voxels)
    for _ in range(50):
        vs.step_and_update(1e-6)
    total_after = sum(v.charge for v in vs.voxels)

    assert abs(total_after - total_before) < 1e-12, (
        f"total charge changed: {total_before} → {total_after}"
    )
    print("charge conservation neutral grid: OK")


def test_poisson_disabled_by_default():
    from voxsym import VoxSym

    vs = VoxSym(backend=None)
    assert not vs.enable_poisson
    print("poisson disabled by default: OK")


if __name__ == "__main__":
    test_poisson_disabled_by_default()
    test_poisson_point_charge()
    test_charge_conservation()
    print("all sanity tests passed")
