
import numpy as np

class Voxel:
    def __init__(
        self,
        x, y, z, size,
        color=(200, 200, 200),
        temperature: float = 300.0,
        pressure: float = 101.3,
        ion_concentration: float = 0.0,
        interface_concentration: float = 0.0,
        charge: float = 0.0,
        electric_field=None,
        magnetic_field=None,
        current_density=None,
        polarization=None,
        magnetization=None,
        # Mechanical state
        displacement=None,
        velocity=None,
        stress=None,
        # Optical state
        optical_intensity: float = 0.0,
    ):
        self.x = x
        self.y = y
        self.z = z
        self.size = size
        self.color = color
        self.opacity = 1.0                  # 0.0 = fully transparent, 1.0 = opaque
        self.material = None
        self.temperature = float(temperature)
        self.pressure = float(pressure)
        self.neighbors = {}
        # Electromagnetic properties
        self.charge = float(charge)
        self.electric_field = np.zeros(3) if electric_field is None else np.asarray(electric_field, dtype=np.float32).copy()
        self.magnetic_field = np.zeros(3) if magnetic_field is None else np.asarray(magnetic_field, dtype=np.float32).copy()
        self.current_density = np.zeros(3) if current_density is None else np.asarray(current_density, dtype=np.float32).copy()
        self.polarization = np.zeros(3) if polarization is None else np.asarray(polarization, dtype=np.float32).copy()
        self.magnetization = np.zeros(3) if magnetization is None else np.asarray(magnetization, dtype=np.float32).copy()

        # Mechanical state
        self.displacement = np.zeros(3) if displacement is None else np.asarray(displacement, dtype=np.float32).copy()
        self.velocity = np.zeros(3) if velocity is None else np.asarray(velocity, dtype=np.float32).copy()
        self.stress = np.zeros(6) if stress is None else np.asarray(stress, dtype=np.float32).copy()  # [σxx σyy σzz σxy σxz σyz]

        # Optical state
        self.optical_intensity = float(optical_intensity)
        # Ionic properties
        self.ion_concentration = float(ion_concentration)
        self.interface_concentration = float(interface_concentration)
    
    def set_coordinates(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def set_size(self, size):
        self.size = size
        
    def set_material(self, material):
        self.material = material
        
    def set_neighbor(self, direction, neighbor_voxel):
        self.neighbors[direction] = neighbor_voxel
        
    def get_coordinates(self):
        return (self.x, self.y, self.z)

    def get_size(self):
        return self.size

    def get_neighbor(self, direction):
        return self.neighbors.get(direction)

    def __repr__(self):
        return f"Voxel(x={self.x}, y={self.y}, z={self.z}, size={self.size})"