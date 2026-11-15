"""Interactive selection of settings using comparable, disposable mesh trials."""
import numpy as np
from deap import cma
from PIL import Image

from .checkpoint import read_checkpoint
from .geometry import BASES, constrain
from .gouraud import color_matrix, render_gouraud
from .hybrid_gouraud import add, local_fit
from .local_refine import refine
from .objective import ColorObjective, WEIGHT_LIMITS, contour_options
from .project_worker import color_gain
from .targets import load
from .train import creator


GENES = {
    'preserve_contours': None,
    'contour_max_radius': (4, 64),
    'contour_internal_radius': (1, 20),
    'exterior_weight': WEIGHT_LIMITS['exterior_weight'],
    'shell_strength': WEIGHT_LIMITS['shell_strength'],
    'preserve_thin_features': None,
    'thin_strength': WEIGHT_LIMITS['thin_strength'],
    'balance_regions': None,
    'region_count': (2, 4),
    'region_share': (5, 45),
}
POPULATION_SIZE = 16


def next_population(parent, partner, rng):
    """Keep one elite and generate the remaining candidates by crossover and mutation."""
    population = [parent.copy()]
    signatures = {tuple(contour_options(parent).items())}
    while len(population) < POPULATION_SIZE:
        child = parent.copy()
        for key, bounds in GENES.items():
            value = (parent if rng.random() < .5 else partner)[key]
            if rng.random() < (.20 if bounds is None else .55):
                if bounds is None:
                    value = not value
                else:
                    lo, hi = bounds
                    sample = np.clip(value + rng.normal(0, .25 * (hi - lo)), lo, hi)
                    value = int(round(sample)) if isinstance(value, int) else round(float(sample), 3)
            child[key] = value
        signature = tuple(contour_options(child).items())
        if signature not in signatures:
            signatures.add(signature)
            population.append(child)
    return population


class Trials:
    def __init__(self, checkpoint, images, settings):
        data = read_checkpoint(checkpoint)
        self.vertices = data['vertices']
        self.colors = data['colors']
        self.width = min(settings['width'], 240)
        self.height = self.width * 3 // 4
        self.target = load(images, self.width, self.height)
        self.seed = settings['seed']
        self.order = np.random.default_rng(self.seed).permutation(len(self.vertices))[:8]
        self.matrix = None

    def fit_colors(self, objective, cancelled):
        if self.matrix is None:
            ids = np.arange(len(self.vertices) * 3).reshape(-1, 3)
            matrix = color_matrix(self.vertices, self.width, self.height, ids)
            self.occupied = np.diff(matrix.indptr) > 0
            self.matrix = matrix[self.occupied]
            self.transpose = self.matrix.T.tocsr()
        a, at = self.matrix, self.transpose
        w = objective.weights.ravel()[self.occupied, None]
        target = objective.target.reshape(-1, 3)[self.occupied]
        # The maximum row sum bounds the largest eigenvalue of A.T W A.
        lipschitz = max(float((at @ (w * np.asarray(a.sum(axis=1)))).max()), 1e-12)
        colors = self.colors.reshape(-1, 3).copy()
        initial = colors.copy()
        extrapolated = colors.copy()
        for step in range(28):
            if cancelled.is_set():
                return None
            gradient = at @ (w * (a @ extrapolated - target))
            candidate = np.clip(extrapolated - gradient / lipschitz, 0, .4)
            extrapolated = candidate + step / (step + 3) * (candidate - colors)
            colors = candidate
        if np.sum(w * (a @ colors - target)**2) > np.sum(w * (a @ initial - target)**2):
            colors = initial
        return colors.reshape(self.colors.shape)

    def preview(self, settings, cancelled):
        objective = ColorObjective(self.target, **contour_options(settings))
        mesh = self.vertices.copy()
        colors = self.fit_colors(objective, cancelled) if settings['color_fit'] else self.colors.copy()
        if colors is None or cancelled.is_set():
            return None
        current = render_gouraud(mesh, colors, self.width, self.height, BASES)
        rng = np.random.default_rng(self.seed)
        for index in self.order:
            if cancelled.is_set():
                return None
            triangle, rgb = mesh[index].copy(), colors[index].copy()
            add(current, triangle, rgb, -1.)
            residual = np.ascontiguousarray(objective.target - current)
            best = color_gain(triangle, rgb, residual, objective.weights)
            best_triangle, best_rgb = triangle, rgb
            centroid = triangle.ravel() if settings['color_fit'] else np.r_[triangle.ravel(), rgb.ravel()/6]
            strategy = cma.Strategy(centroid, settings['sigma'], lambda_=4)
            for _ in range(2):
                samples = strategy.centroid + strategy.sigma * (rng.standard_normal((4, strategy.dim)) @ strategy.BD.T)
                population = []
                for sample in samples:
                    if cancelled.is_set():
                        return None
                    candidate = constrain(sample[:9])
                    if settings['color_fit']:
                        color, gain = local_fit(candidate, residual, objective.weights)
                    else:
                        color = np.clip(sample[9:].reshape(3, 3)*6, 0, .4)
                        gain = color_gain(candidate, color, residual, objective.weights)
                    if settings['refinement']:
                        scale = self.width / settings['width']
                        candidate, color, gain, _ = refine(
                            candidate, color, gain, residual, objective.weights,
                            settings['refine_radius']*scale, settings['refine_difference']*scale,
                            settings['refine_steps'])
                    genome = candidate.ravel() if settings['color_fit'] else np.r_[candidate.ravel(),color.ravel()/6]
                    individual = creator.LisaIndividual(genome)
                    individual.fitness.values = (-gain,)
                    population.append(individual)
                    if gain > best:
                        best, best_triangle, best_rgb = gain, candidate, color
                strategy.update(population)
            mesh[index], colors[index] = best_triangle, best_rgb
            add(current, best_triangle, best_rgb)
        return [Image.fromarray(np.uint8(np.clip(view, 0, 1)*255)) for view in current]
