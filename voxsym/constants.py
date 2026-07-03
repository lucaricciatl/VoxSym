"""
Physical constants in SI units.
"""

# Elementary charge [C]
ELEMENTARY_CHARGE = 1.602176634e-19
e = ELEMENTARY_CHARGE

# Boltzmann constant [J/K]
BOLTZMANN_CONSTANT = 1.380649e-23
kB = BOLTZMANN_CONSTANT

# Avogadro number [mol⁻¹]
AVOGADRO_NUMBER = 6.02214076e23
NA = AVOGADRO_NUMBER

# Faraday constant  F = e · NA  [C/mol]
FARADAY_CONSTANT = ELEMENTARY_CHARGE * AVOGADRO_NUMBER
F = FARADAY_CONSTANT

# Vacuum permittivity [F/m]
VACUUM_PERMITTIVITY = 8.854187817e-12
epsilon0 = VACUUM_PERMITTIVITY

# Universal gas constant  R = kB · NA  [J/(mol·K)]
GAS_CONSTANT = BOLTZMANN_CONSTANT * AVOGADRO_NUMBER
R = GAS_CONSTANT

# Thermal voltage at 300 K  kT/e  [V]
def thermal_voltage(T: float = 300.0) -> float:
    """Thermal voltage k_B·T / e  [V]."""
    return BOLTZMANN_CONSTANT * T / ELEMENTARY_CHARGE
