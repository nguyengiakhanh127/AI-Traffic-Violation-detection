from dataclasses import dataclass
import numpy as np

@dataclass
class Vertex:
    x: float
    y: float

    @property
    def as_array(self) -> np.ndarray:
        return np.array([self.x, self.y], dtype=np.float32)

@dataclass
class Vector2D:
    dx: float
    dy: float

    @property
    def as_array(self) -> np.ndarray:
        return np.array([self.dx, self.dy], dtype=np.float32)

    def dot_product(self, other: 'Vector2D') -> float:
        return float(np.dot(self.as_array, other.as_array))