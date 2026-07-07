import numpy as np


class Material:
    """Material properties for voxel-based physics simulations.

    Stores electrical, thermal, mechanical, optical, and magnetic
    properties. Units are SI unless noted otherwise.
    """

    def __init__(
        self,
        name: str = "vacuum",
        # Electrical
        conductivity: float = 0.0,          # S/m
        dielectric_constant: float = 1.0,   # relative permittivity ε_r
        resistivity: float | None = None,   # Ω·m (derived from conductivity if None)

        # Memristor: ion-intercalation dependent electronic conductivity
        conductivity_ion_min: float = 0.0,      # σ when ion conc = 0
        conductivity_ion_max: float = 0.0,      # σ when ion conc = ion_conc_max
        conductivity_ion_exponent: float = 1.0,   # power-law exponent

        # Thermal
        thermal_conductivity: float = 0.0,  # W/(m·K)
        specific_heat: float = 0.0,         # J/(kg·K)
        thermal_expansion: float = 0.0,    # 1/K (linear coefficient α)
        # Mechanical
        density: float = 0.0,              # kg/m³
        youngs_modulus: float = 0.0,       # Pa
        poisson_ratio: float = 0.0,        # dimensionless
        bulk_modulus: float | None = None, # Pa
        shear_modulus: float | None = None,# Pa
        yield_strength: float = 0.0,       # Pa
        # Optical
        refractive_index: float = 1.0,     # dimensionless
        absorption_coeff: float = 0.0,      # 1/m
        # Magnetic
        permeability: float = 1.0,         # relative μ_r
        magnetic_susceptibility: float = 0.0,  # dimensionless
        # Ionic transport (Nernst–Planck / Fick)
        ion_diffusivity: float = 0.0,      # D_ion  [m²/s]
        ionic_valence: int = 1,            # z  (charge number, dimensionless)
        anion_diffusivity: float = 0.0,    # D_anion  [m²/s]
        anion_valence: int = -1,           # z_anion
        ion_conc_max: float = 0.0,         # c_max  [mol/m³]
        partition_coeff: float = 1.0,      # K  (c_right = K·c_left at interface)
        interface_capacity: float = 0.0,   # Γ_max  [mol/m²]
        adsorption_rate: float = 0.0,      # k_a  [m³/(mol·s)]
        desorption_rate: float = 0.0,      # k_d  [1/s]
        # Display / meta
        color: tuple[int, int, int] = (200, 200, 200),
    ):
        self.name = name

        # Electrical
        self.conductivity = float(conductivity)
        self.dielectric_constant = float(dielectric_constant)
        self.conductivity_ion_min = float(conductivity_ion_min)
        self.conductivity_ion_max = float(conductivity_ion_max)
        self.conductivity_ion_exponent = float(conductivity_ion_exponent)
        if resistivity is None:
            self.resistivity = 1.0 / self.conductivity if self.conductivity > 0 else float("inf")
        else:
            self.resistivity = float(resistivity)

        # Thermal
        self.thermal_conductivity = float(thermal_conductivity)
        self.specific_heat = float(specific_heat)
        self.thermal_expansion = float(thermal_expansion)

        # Mechanical
        self.density = float(density)
        self.youngs_modulus = float(youngs_modulus)
        self.poisson_ratio = float(poisson_ratio)

        E = self.youngs_modulus
        nu = self.poisson_ratio
        if bulk_modulus is None and E > 0 and nu > -1.0:
            try:
                self.bulk_modulus = E / (3.0 * (1.0 - 2.0 * nu))
            except ZeroDivisionError:
                self.bulk_modulus = 0.0
        else:
            self.bulk_modulus = float(bulk_modulus) if bulk_modulus is not None else 0.0

        if shear_modulus is None and E > 0 and nu > -1.0:
            try:
                self.shear_modulus = E / (2.0 * (1.0 + nu))
            except ZeroDivisionError:
                self.shear_modulus = 0.0
        else:
            self.shear_modulus = float(shear_modulus) if shear_modulus is not None else 0.0

        self.yield_strength = float(yield_strength)

        # Optical
        self.refractive_index = float(refractive_index)
        self.absorption_coeff = float(absorption_coeff)

        # Magnetic
        self.permeability = float(permeability)
        self.magnetic_susceptibility = float(magnetic_susceptibility)

        # Ionic transport
        self.ion_diffusivity = float(ion_diffusivity)
        self.ionic_valence = int(ionic_valence)
        self.anion_diffusivity = float(anion_diffusivity)
        self.anion_valence = int(anion_valence)
        self.ion_conc_max = float(ion_conc_max)
        self.partition_coeff = float(partition_coeff)
        self.interface_capacity = float(interface_capacity)
        self.adsorption_rate = float(adsorption_rate)
        self.desorption_rate = float(desorption_rate)

        # Display
        self.color = color

    def __repr__(self) -> str:
        return (
            f"Material(name={self.name!r}, "
            f"conductivity={self.conductivity:.3e} S/m, "
            f"sigma_ion=[{self.conductivity_ion_min:.3e}, {self.conductivity_ion_max:.3e}], "
            f"dielectric_constant={self.dielectric_constant:.2f})"
        )

    def effective_conductivity(self, ion_concentration: float) -> float:
        """Return ion-intercalation dependent electronic conductivity [S/m]."""
        if self.conductivity_ion_max <= self.conductivity_ion_min:
            return self.conductivity
        c = float(ion_concentration)
        cmax = max(float(self.ion_conc_max), 1e-12)
        f = np.clip(c / cmax, 0.0, 1.0)
        p = self.conductivity_ion_exponent
        sigma = (
            self.conductivity_ion_min
            + (self.conductivity_ion_max - self.conductivity_ion_min) * (f ** p)
        )
        return float(sigma)


# Pre-defined materials (room-temperature values, approximate)
# ---------------------------------------------------------------------------

VACUUM = Material(
    name="vacuum",
    conductivity=0.0,
    dielectric_constant=1.0,
    resistivity=float("inf"),
    thermal_conductivity=0.0,
    specific_heat=0.0,
    density=0.0,
    refractive_index=1.0,
    permeability=1.0,
    color=(50, 50, 50),
)

COPPER = Material(
    name="copper",
    conductivity=5.96e7,
    dielectric_constant=float("inf"),
    thermal_conductivity=401.0,
    specific_heat=385.0,
    density=8960.0,
    youngs_modulus=110e9,
    poisson_ratio=0.34,
    yield_strength=70e6,
    refractive_index=0.0,
    absorption_coeff=1e8,
    permeability=0.999991,
    ion_diffusivity=0.0,
    ionic_valence=1,
    ion_conc_max=0.0,
    color=(184, 115, 51),
)

IRON = Material(
    name="iron",
    conductivity=1.0e7,
    dielectric_constant=float("inf"),
    thermal_conductivity=80.2,
    specific_heat=449.0,
    density=7874.0,
    youngs_modulus=211e9,
    poisson_ratio=0.29,
    yield_strength=250e6,
    refractive_index=0.0,
    absorption_coeff=1e8,
    permeability=5000.0,  # ferromagnetic
    magnetic_susceptibility=4999.0,
    color=(161, 157, 148),
)

ALUMINUM = Material(
    name="aluminum",
    conductivity=3.5e7,
    dielectric_constant=float("inf"),
    thermal_conductivity=237.0,
    specific_heat=900.0,
    density=2700.0,
    youngs_modulus=70e9,
    poisson_ratio=0.33,
    yield_strength=30e6,
    refractive_index=0.0,
    absorption_coeff=1e8,
    permeability=1.000022,
    color=(210, 210, 210),
)

SILICON = Material(
    name="silicon",
    conductivity=1.0e-3,  # intrinsic, very low
    dielectric_constant=11.68,
    thermal_conductivity=149.0,
    specific_heat=710.0,
    density=2330.0,
    youngs_modulus=169e9,
    poisson_ratio=0.22,
    yield_strength=7e9,
    refractive_index=3.42,
    absorption_coeff=1e3,
    permeability=1.0,
    color=(80, 80, 90),
)

GLASS = Material(
    name="glass",
    conductivity=1.0e-15,
    dielectric_constant=4.7,
    thermal_conductivity=1.05,
    specific_heat=840.0,
    density=2500.0,
    youngs_modulus=70e9,
    poisson_ratio=0.22,
    yield_strength=50e6,
    refractive_index=1.52,
    absorption_coeff=0.1,
    permeability=1.0,
    ion_diffusivity=1e-20,
    ionic_valence=1,
    ion_conc_max=0.0,
    color=(180, 220, 240),
)

WATER = Material(
    name="water",
    conductivity=0.01,
    dielectric_constant=80.1,
    thermal_conductivity=0.6,
    specific_heat=4186.0,
    thermal_expansion=2.1e-4,
    density=1000.0,
    youngs_modulus=2.2e9,
    poisson_ratio=0.5,
    yield_strength=0.0,
    refractive_index=1.33,
    absorption_coeff=0.1,
    permeability=1.0,
    ion_diffusivity=1e-9,
    ionic_valence=1,
    ion_conc_max=1000.0,
    color=(60, 120, 220),
)

AIR = Material(
    name="air",
    conductivity=0.0,
    dielectric_constant=1.0006,
    thermal_conductivity=0.026,
    specific_heat=1005.0,
    thermal_expansion=3.4e-3,
    density=1.225,
    youngs_modulus=0.0,
    poisson_ratio=0.0,
    yield_strength=0.0,
    refractive_index=1.0003,
    absorption_coeff=0.0,
    permeability=1.0,
    ion_diffusivity=1e-5,
    ionic_valence=1,
    ion_conc_max=40.0,
    color=(200, 230, 255),
)

WOOD_OAK = Material(
    name="oak_wood",
    conductivity=0.01,
    dielectric_constant=3.0,
    thermal_conductivity=0.17,
    specific_heat=2400.0,
    thermal_expansion=4.9e-6,
    density=750.0,
    youngs_modulus=11e9,
    poisson_ratio=0.3,
    yield_strength=40e6,
    refractive_index=1.5,
    absorption_coeff=10.0,
    permeability=1.0,
    color=(139, 90, 43),
)

RUBBER = Material(
    name="rubber",
    conductivity=1.0e-14,
    dielectric_constant=7.0,
    thermal_conductivity=0.13,
    specific_heat=2010.0,
    thermal_expansion=2.2e-4,
    density=1100.0,
    youngs_modulus=0.01e9,
    poisson_ratio=0.499,
    yield_strength=15e6,
    refractive_index=1.5,
    absorption_coeff=100.0,
    permeability=1.0,
    ion_diffusivity=1e-13,
    ionic_valence=1,
    ion_conc_max=0.0,
    color=(40, 40, 40),
)

# ---------------------------------------------------------------------------
# Ion-transport materials (MXene / ECRAM context)
# ---------------------------------------------------------------------------

MXENE = Material(
    name="mxene",
    conductivity=2.4e5,          # Ti₃C₂ MXene [S/m]
    dielectric_constant=10.0,
    thermal_conductivity=10.0,
    specific_heat=900.0,
    density=4500.0,              # kg/m³
    youngs_modulus=330e9,
    poisson_ratio=0.2,
    yield_strength=1e9,
    refractive_index=2.0,
    absorption_coeff=1e6,
    permeability=1.0,
    ion_diffusivity=1e-11,       # Li⁺ in MXene [m²/s]
    ionic_valence=1,
    ion_conc_max=15000.0,        # mol/m³
    partition_coeff=1.0,
    interface_capacity=1e-5,     # mol/m²
    adsorption_rate=1e-6,
    desorption_rate=0.1,
    color=(80, 160, 180),
)

ELECTROLYTE = Material(
    name="electrolyte",
    conductivity=1.0,             # liquid electrolyte [S/m]
    dielectric_constant=80.0,
    thermal_conductivity=0.6,
    specific_heat=4180.0,
    density=1100.0,
    youngs_modulus=0.0,
    poisson_ratio=0.5,
    yield_strength=0.0,
    refractive_index=1.4,
    absorption_coeff=0.1,
    permeability=1.0,
    ion_diffusivity=1e-9,        # Li⁺ in liquid electrolyte [m²/s]
    ionic_valence=1,
    ion_conc_max=1000.0,
    partition_coeff=0.5,
    interface_capacity=0.0,
    adsorption_rate=0.0,
    desorption_rate=0.0,
    color=(100, 200, 100),
)

# Convenience registry
MATERIALS = {
    "vacuum": VACUUM,
    "copper": COPPER,
    "iron": IRON,
    "aluminum": ALUMINUM,
    "silicon": SILICON,
    "glass": GLASS,
    "water": WATER,
    "air": AIR,
    "oak_wood": WOOD_OAK,
    "rubber": RUBBER,
    "mxene": MXENE,
    "electrolyte": ELECTROLYTE,
}


def get_material(name: str) -> Material:
    """Lookup a pre-defined material by name (case-insensitive)."""
    key = name.lower().strip()
    if key not in MATERIALS:
        raise KeyError(f"Unknown material '{name}'. Available: {list(MATERIALS.keys())}")
    return MATERIALS[key]