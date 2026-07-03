"""
Simulation recorder — captures voxel state over time and saves to .npz / .csv.
"""

import io
import os
import csv as _csv
import numpy as np
from voxsym.material import MATERIALS


def _decode_name(name) -> str:
    if isinstance(name, bytes):
        return name.decode("utf-8")
    return str(name)


def _material_color(name: str) -> tuple[int, int, int]:
    name = _decode_name(name)
    if name in MATERIALS:
        return tuple(int(c) for c in MATERIALS[name].color)
    return (200, 200, 200)


class Recorder:
    """Record voxel state at each timestep for later playback.

    Usage::

        rec = Recorder(vs)
        while True:
            vs.step_simulation(dt)
            vs.update()
            rec.record(sim_time)
            vs.render()
        rec.save("simulation.npz")
        rec.save_csv("simulation.csv")
    """

    def __init__(self, voxsym):
        self.voxsym = voxsym
        self._times: list[float] = []
        self._temperatures: list[np.ndarray] = []
        self._pressures: list[np.ndarray] = []
        self._ion_concentrations: list[np.ndarray] = []
        self._charges: list[np.ndarray] = []
        self._interface_concentrations: list[np.ndarray] = []
        self._electric_fields: list[np.ndarray] = []
        self._magnetic_fields: list[np.ndarray] = []
        self._current_densities: list[np.ndarray] = []
        self._polarizations: list[np.ndarray] = []
        self._magnetizations: list[np.ndarray] = []
        self._displacements: list[np.ndarray] = []
        self._velocities: list[np.ndarray] = []
        self._stresses: list[np.ndarray] = []
        self._optical_intensities: list[np.ndarray] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, t: float):
        """Capture the current state of all voxels."""
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if n == 0:
            return

        self._times.append(t)
        self._temperatures.append(
            np.array([v.temperature for v in voxels], dtype=np.float32))
        self._pressures.append(
            np.array([v.pressure for v in voxels], dtype=np.float32))
        self._ion_concentrations.append(
            np.array([v.ion_concentration for v in voxels], dtype=np.float32))
        self._charges.append(
            np.array([v.charge for v in voxels], dtype=np.float32))
        self._interface_concentrations.append(
            np.array([getattr(v, "interface_concentration", 0.0) for v in voxels],
                     dtype=np.float32))
        self._displacements.append(
            np.array([getattr(v, "displacement", [0.0, 0.0, 0.0]) for v in voxels],
                     dtype=np.float32))
        self._velocities.append(
            np.array([getattr(v, "velocity", [0.0, 0.0, 0.0]) for v in voxels],
                     dtype=np.float32))
        self._stresses.append(
            np.array([getattr(v, "stress", [0.0]*6) for v in voxels],
                     dtype=np.float32))
        self._optical_intensities.append(
            np.array([getattr(v, "optical_intensity", 0.0) for v in voxels],
                     dtype=np.float32))
        self._electric_fields.append(
            np.array([v.electric_field for v in voxels], dtype=np.float32))
        self._magnetic_fields.append(
            np.array([v.magnetic_field for v in voxels], dtype=np.float32))
        self._current_densities.append(
            np.array([v.current_density for v in voxels], dtype=np.float32))
        self._polarizations.append(
            np.array([v.polarization for v in voxels], dtype=np.float32))
        self._magnetizations.append(
            np.array([v.magnetization for v in voxels], dtype=np.float32))

    @property
    def frame_count(self) -> int:
        return len(self._times)

    # ------------------------------------------------------------------
    # CSV export (easy analysis in pandas / Excel / MATLAB)
    # ------------------------------------------------------------------

    def save_csv(self, path: str):
        """Export the recorded frames to a CSV file.

        Each row is one voxel at one timestep (long format).  Columns
        include geometry, material, and every recorded physical field.
        """
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if n == 0 or self.frame_count == 0:
            raise ValueError("Nothing to save: no voxels or no frames recorded.")

        import csv

        headers = [
            "time",
            "frame",
            "voxel_index",
            "x",
            "y",
            "z",
            "size",
            "material",
            "temperature",
            "pressure",
            "ion_concentration",
            "charge",
            "electric_field_x",
            "electric_field_y",
            "electric_field_z",
            "magnetic_field_x",
            "magnetic_field_y",
            "magnetic_field_z",
            "current_density_x",
            "current_density_y",
            "current_density_z",
            "polarization_x",
            "polarization_y",
            "polarization_z",
            "magnetization_x",
            "magnetization_y",
            "magnetization_z",
            "interface_concentration",
            "displacement_x",
            "displacement_y",
            "displacement_z",
            "velocity_x",
            "velocity_y",
            "velocity_z",
            "stress_xx",
            "stress_yy",
            "stress_zz",
            "stress_xy",
            "stress_xz",
            "stress_yz",
            "optical_intensity",
        ]

        positions = np.array([[v.x, v.y, v.z] for v in voxels], dtype=np.float64)
        sizes = np.array([v.size for v in voxels], dtype=np.float64)
        materials = [
            v.material.name if v.material else "none" for v in voxels
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for frame_idx, t in enumerate(self._times):
                for i in range(n):
                    writer.writerow([
                        t,
                        frame_idx,
                        i,
                        positions[i, 0],
                        positions[i, 1],
                        positions[i, 2],
                        sizes[i],
                        materials[i],
                        self._temperatures[frame_idx][i],
                        self._pressures[frame_idx][i],
                        self._ion_concentrations[frame_idx][i],
                        self._charges[frame_idx][i],
                        self._electric_fields[frame_idx][i, 0],
                        self._electric_fields[frame_idx][i, 1],
                        self._electric_fields[frame_idx][i, 2],
                        self._magnetic_fields[frame_idx][i, 0],
                        self._magnetic_fields[frame_idx][i, 1],
                        self._magnetic_fields[frame_idx][i, 2],
                        self._current_densities[frame_idx][i, 0],
                        self._current_densities[frame_idx][i, 1],
                        self._current_densities[frame_idx][i, 2],
                        self._polarizations[frame_idx][i, 0],
                        self._polarizations[frame_idx][i, 1],
                        self._polarizations[frame_idx][i, 2],
                        self._magnetizations[frame_idx][i, 0],
                        self._magnetizations[frame_idx][i, 1],
                        self._magnetizations[frame_idx][i, 2],
                        self._interface_concentrations[frame_idx][i],
                        self._displacements[frame_idx][i, 0],
                        self._displacements[frame_idx][i, 1],
                        self._displacements[frame_idx][i, 2],
                        self._velocities[frame_idx][i, 0],
                        self._velocities[frame_idx][i, 1],
                        self._velocities[frame_idx][i, 2],
                        self._stresses[frame_idx][i, 0],
                        self._stresses[frame_idx][i, 1],
                        self._stresses[frame_idx][i, 2],
                        self._stresses[frame_idx][i, 3],
                        self._stresses[frame_idx][i, 4],
                        self._stresses[frame_idx][i, 5],
                        self._optical_intensities[frame_idx][i],
                    ])

    def to_dataframe(self):
        """Return the recorded data as a pandas DataFrame (long format)."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError("pandas is required for to_dataframe()") from exc

        rows = []
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        materials = [v.material.name if v.material else "none" for v in voxels]
        positions = np.array([[v.x, v.y, v.z] for v in voxels], dtype=np.float64)
        sizes = np.array([v.size for v in voxels], dtype=np.float64)

        for frame_idx, t in enumerate(self._times):
            for i in range(n):
                rows.append({
                    "time": t,
                    "frame": frame_idx,
                    "voxel_index": i,
                    "x": positions[i, 0],
                    "y": positions[i, 1],
                    "z": positions[i, 2],
                    "size": sizes[i],
                    "material": materials[i],
                    "temperature": self._temperatures[frame_idx][i],
                    "pressure": self._pressures[frame_idx][i],
                    "ion_concentration": self._ion_concentrations[frame_idx][i],
                    "charge": self._charges[frame_idx][i],
                    "electric_field_x": self._electric_fields[frame_idx][i, 0],
                    "electric_field_y": self._electric_fields[frame_idx][i, 1],
                    "electric_field_z": self._electric_fields[frame_idx][i, 2],
                    "magnetic_field_x": self._magnetic_fields[frame_idx][i, 0],
                    "magnetic_field_y": self._magnetic_fields[frame_idx][i, 1],
                    "magnetic_field_z": self._magnetic_fields[frame_idx][i, 2],
                    "current_density_x": self._current_densities[frame_idx][i, 0],
                    "current_density_y": self._current_densities[frame_idx][i, 1],
                    "current_density_z": self._current_densities[frame_idx][i, 2],
                    "polarization_x": self._polarizations[frame_idx][i, 0],
                    "polarization_y": self._polarizations[frame_idx][i, 1],
                    "polarization_z": self._polarizations[frame_idx][i, 2],
                    "magnetization_x": self._magnetizations[frame_idx][i, 0],
                    "magnetization_y": self._magnetizations[frame_idx][i, 1],
                    "magnetization_z": self._magnetizations[frame_idx][i, 2],
                    "interface_concentration": self._interface_concentrations[frame_idx][i],
                    "displacement_x": self._displacements[frame_idx][i, 0],
                    "displacement_y": self._displacements[frame_idx][i, 1],
                    "displacement_z": self._displacements[frame_idx][i, 2],
                    "velocity_x": self._velocities[frame_idx][i, 0],
                    "velocity_y": self._velocities[frame_idx][i, 1],
                    "velocity_z": self._velocities[frame_idx][i, 2],
                    "stress_xx": self._stresses[frame_idx][i, 0],
                    "stress_yy": self._stresses[frame_idx][i, 1],
                    "stress_zz": self._stresses[frame_idx][i, 2],
                    "stress_xy": self._stresses[frame_idx][i, 3],
                    "stress_xz": self._stresses[frame_idx][i, 4],
                    "stress_yz": self._stresses[frame_idx][i, 5],
                    "optical_intensity": self._optical_intensities[frame_idx][i],
                })

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save(self, path: str):
        """Save recorded data to a compressed .npz file."""
        voxels = self.voxsym.get_voxels()
        n = len(voxels)
        if n == 0 or self.frame_count == 0:
            raise ValueError("Nothing to save: no voxels or no frames recorded.")

        np.savez_compressed(
            path,
            positions=np.array([[v.x, v.y, v.z] for v in voxels], dtype=np.float32),
            sizes=np.array([v.size for v in voxels], dtype=np.float32),
            colors=np.array([v.color for v in voxels], dtype=np.uint8),
            material_names=np.array(
                [v.material.name if v.material else "none" for v in voxels],
                dtype=str,
            ),
            times=np.array(self._times, dtype=np.float64),
            temperatures=np.array(self._temperatures, dtype=np.float32),
            pressures=np.array(self._pressures, dtype=np.float32),
            ion_concentrations=np.array(self._ion_concentrations, dtype=np.float32),
            charges=np.array(self._charges, dtype=np.float32),
            electric_fields=np.array(self._electric_fields, dtype=np.float32),
            magnetic_fields=np.array(self._magnetic_fields, dtype=np.float32),
            current_densities=np.array(self._current_densities, dtype=np.float32),
            polarizations=np.array(self._polarizations, dtype=np.float32),
            magnetizations=np.array(self._magnetizations, dtype=np.float32),
            interface_concentrations=np.array(self._interface_concentrations, dtype=np.float32),
            displacements=np.array(self._displacements, dtype=np.float32),
            velocities=np.array(self._velocities, dtype=np.float32),
            stresses=np.array(self._stresses, dtype=np.float32),
            optical_intensities=np.array(self._optical_intensities, dtype=np.float32),
        )

    @staticmethod
    def load(path: str) -> dict[str, np.ndarray]:
        """Load a recorded simulation from a .npz file.

        Returns a dict-like ``NpzFile`` with keys:
        positions, sizes, colors, material_names, times,
        temperatures, pressures, ion_concentrations, charges,
        electric_fields, magnetic_fields, current_densities,
        polarizations, magnetizations, interface_concentrations,
        displacements, velocities, stresses, optical_intensities.
        """
        return np.load(path, allow_pickle=False)

    @staticmethod
    def from_csv(path_or_bytes) -> dict[str, np.ndarray]:
        """Load a recorded simulation from a CSV file (long format).

        Accepts a file path (str / pathlib.Path) or raw bytes / string.
        Missing physical fields are filled with zeros.  Colors are
        reconstructed from the material name.
        """
        if isinstance(path_or_bytes, (str, os.PathLike)):
            with open(path_or_bytes, "r", encoding="utf-8", newline="") as f:
                text = f.read()
        else:
            text = (
                path_or_bytes.decode("utf-8")
                if isinstance(path_or_bytes, bytes)
                else str(path_or_bytes)
            )

        f = io.StringIO(text)
        reader = _csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or has no header.")

        rows = list(reader)
        if not rows:
            raise ValueError("CSV file has no data rows.")

        def _float(row, key):
            val = row.get(key, "")
            if val is None or val == "":
                return 0.0
            return float(val)

        # Sort by frame and voxel index for deterministic layout
        rows.sort(key=lambda r: (_float(r, "frame"), _float(r, "voxel_index")))

        frames = sorted({int(_float(r, "frame")) for r in rows})
        voxel_indices = sorted({int(_float(r, "voxel_index")) for r in rows})
        n_frames = len(frames)
        n_voxels = len(voxel_indices)

        if n_frames == 0 or n_voxels == 0:
            raise ValueError("CSV has no frames or no voxels.")

        expected_rows = n_frames * n_voxels
        if len(rows) != expected_rows:
            raise ValueError(
                f"CSV layout mismatch: {len(rows)} rows, expected "
                f"{n_frames} frames × {n_voxels} voxels = {expected_rows} rows."
            )

        # Geometry (constant across frames)
        first_frame_rows = rows[:n_voxels]
        positions = np.array(
            [[_float(r, "x"), _float(r, "y"), _float(r, "z")] for r in first_frame_rows],
            dtype=np.float32,
        )
        sizes = np.array([_float(r, "size") for r in first_frame_rows], dtype=np.float32)
        material_names = np.array(
            [r.get("material", "none") for r in first_frame_rows], dtype=str
        )
        colors = np.array([_material_color(name) for name in material_names], dtype=np.uint8)

        times = np.zeros(n_frames, dtype=np.float64)

        def _frame_array(key: str, shape3: bool = False):
            shape = (n_frames, n_voxels, 3) if shape3 else (n_frames, n_voxels)
            arr = np.zeros(shape, dtype=np.float32)
            for frame_idx in range(n_frames):
                start = frame_idx * n_voxels
                for i, r in enumerate(rows[start : start + n_voxels]):
                    if shape3:
                        for dim, suffix in enumerate(("_x", "_y", "_z")):
                            arr[frame_idx, i, dim] = _float(r, f"{key}{suffix}")
                    else:
                        arr[frame_idx, i] = _float(r, key)
            return arr

        temperatures = _frame_array("temperature")
        pressures = _frame_array("pressure")
        ion_concentrations = _frame_array("ion_concentration")
        charges = _frame_array("charge")
        electric_fields = _frame_array("electric_field", shape3=True)
        magnetic_fields = _frame_array("magnetic_field", shape3=True)
        current_densities = _frame_array("current_density", shape3=True)
        polarizations = _frame_array("polarization", shape3=True)
        magnetizations = _frame_array("magnetization", shape3=True)
        interface_concentrations = _frame_array("interface_concentration")
        displacements = _frame_array("displacement", shape3=True)
        velocities = _frame_array("velocity", shape3=True)
        stresses = _frame_array("stress", shape3=True)
        optical_intensities = _frame_array("optical_intensity")

        for frame_idx in range(n_frames):
            start = frame_idx * n_voxels
            times[frame_idx] = _float(rows[start], "time")

        return {
            "positions": positions,
            "sizes": sizes,
            "colors": colors,
            "material_names": material_names,
            "times": times,
            "temperatures": temperatures,
            "pressures": pressures,
            "ion_concentrations": ion_concentrations,
            "charges": charges,
            "electric_fields": electric_fields,
            "magnetic_fields": magnetic_fields,
            "current_densities": current_densities,
            "polarizations": polarizations,
            "magnetizations": magnetizations,
            "interface_concentrations": interface_concentrations,
            "displacements": displacements,
            "velocities": velocities,
            "stresses": stresses,
            "optical_intensities": optical_intensities,
        }

    def clear(self):
        """Discard all recorded frames."""
        self._times.clear()
        self._temperatures.clear()
        self._pressures.clear()
        self._ion_concentrations.clear()
        self._charges.clear()
        self._electric_fields.clear()
        self._magnetic_fields.clear()
        self._current_densities.clear()
        self._polarizations.clear()
        self._magnetizations.clear()
        self._interface_concentrations.clear()
        self._displacements.clear()
        self._velocities.clear()
        self._stresses.clear()
        self._optical_intensities.clear()
