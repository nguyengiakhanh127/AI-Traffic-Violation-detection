# --- START OF FILE spatial_math.py ---

import numpy as np
from geometry.primitives import Vertex, Vector2D
from geometry.shapes import Edge

class SpatialMath:
    @staticmethod
    def calculate_distance(v1: Vertex, v2: Vertex) -> float:
        return float(np.linalg.norm(v1.as_array - v2.as_array))

    @staticmethod
    def get_relative_position(point: Vertex, edge: 'Edge') -> float:
        return float(np.dot(edge.weights, point.as_array) + edge.bias)
    
    @staticmethod
    def get_midpoint(edge: Edge) -> Vertex:
        mid_x = int((edge.p1.x + edge.p2.x) / 2)
        mid_y = int((edge.p1.y + edge.p2.y) / 2)
        return Vertex(mid_x, mid_y)

    @staticmethod
    def get_normalized_vector(p1: Vertex, p2: Vertex) -> Vector2D:
        vec = p2.as_array - p1.as_array
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        return Vector2D(dx=float(vec[0]), dy=float(vec[1]))   

    @staticmethod
    def _ccw(a: Vertex, b: Vertex, c: Vertex) -> bool:
        return (c.y - a.y) * (b.x - a.x) > (b.y - a.y) * (c.x - a.x)

    @staticmethod
    def do_segments_intersect(a: Vertex, b: Vertex, c: Vertex, d: Vertex) -> bool:
        return (SpatialMath._ccw(a, c, d) != SpatialMath._ccw(b, c, d)) and \
               (SpatialMath._ccw(a, b, c) != SpatialMath._ccw(a, b, d))
