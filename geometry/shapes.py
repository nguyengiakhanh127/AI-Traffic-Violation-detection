import cv2
import numpy as np
from typing import List
from geometry.primitives import Vertex
from utils.enums import TrafficLineType

class Edge:
    def __init__(self, p1: Vertex, p2: Vertex, line_type: TrafficLineType):
        self.p1 = p1
        self.p2 = p2
        self.line_type = line_type

        self.weights: np.ndarray = np.empty(2, dtype=np.float32)
        self.bias: float = 0.0
        self.norm: float = 0.0
        
        self._calculate_line_equation()

    def _calculate_line_equation(self) -> None:
        a = float(self.p2.y - self.p1.y)
        b = float(self.p1.x - self.p2.x)
        c = float(self.p2.x * self.p1.y - self.p1.x * self.p2.y)
        
        self.weights = np.array([a, b], dtype=np.float32)
        self.bias = c
        self.norm = float(np.linalg.norm(self.weights))

class Polygon:
    def __init__(self, vertices: List[Vertex]):
        self.vertices = vertices
        self._cv_contour = np.array([v.as_array for v in self.vertices], dtype=np.int32)

    def is_contain_point(self, point: Vertex) -> bool:
        pt = (int(point.x), int(point.y))
        result = cv2.pointPolygonTest(self._cv_contour, pt, False)
        return result >= 0