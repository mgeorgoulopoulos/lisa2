import numpy as np

ASPECT = 4 / 3
RADIUS = 3.2
# Unit-sphere angular diameter is 36.42 degrees. 42 degrees leaves a margin.
FOV_Y = 42.0
TAN_HALF = np.tan(np.deg2rad(FOV_Y / 2))
DIRECTIONS = np.array([[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]], dtype=float) / np.sqrt(3)


def basis(direction):
    n = np.asarray(direction, dtype=float)
    n = n / np.linalg.norm(n)
    up = np.array([0., 1., 0.])
    if abs(n @ up) > .97:
        up = np.array([0., 0., 1.])
    right = np.cross(up, n)
    right /= np.linalg.norm(right)
    return np.array([right, np.cross(n, right), n])


BASES = np.array([basis(n) for n in DIRECTIONS])


def constrain(vertices):
    v = np.asarray(vertices).reshape(3, 3).copy()
    # Every triangle is entirely inside the unit ball, hence inside all frusta.
    v /= np.maximum(1., np.linalg.norm(v, axis=1))[:, None]
    return v


def project(vertices, camera_basis, width, height):
    local = np.asarray(vertices) @ camera_basis.T
    z = RADIUS - local[:, 2]
    xy = local[:, :2] / z[:, None] / TAN_HALF
    xy[:, 0] /= ASPECT
    return np.column_stack(((xy[:, 0] + 1) * width / 2,
                            (1 - xy[:, 1]) * height / 2))
