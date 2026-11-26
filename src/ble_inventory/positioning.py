"""RSSI ranging and nonlinear 2D multilateration shared by both input sources."""
from collections import deque
import math
import numpy as np


def rssi_to_distance(rssi_dbm, rssi_at_1m_dbm=-59, exponent=2):
    if exponent <= 0 or not all(math.isfinite(v) for v in (rssi_dbm, rssi_at_1m_dbm, exponent)):
        raise ValueError("Invalid path-loss model")
    return 10 ** ((rssi_at_1m_dbm - rssi_dbm)/(10*exponent))


def horizontal_distance(slant_m, height_difference_m):
    if slant_m <= abs(height_difference_m):
        raise ValueError("RSSI range smaller than known height difference")
    return math.sqrt(slant_m**2-height_difference_m**2)


class RssiFilter:
    def __init__(self, alpha=0.4, window=5):
        self.values = deque(maxlen=window)
        self.ema = None
        self.alpha = alpha

    def add(self, value):
        self.values.append(value)
        median = float(np.median(self.values))
        self.ema = median if self.ema is None else self.alpha*median+(1-self.alpha)*self.ema
        return self.ema


def multilaterate(points, distances, min_baseline_m=0.0):
    p = np.asarray(points, dtype=float)
    d = np.asarray(distances, dtype=float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or len(d) != len(p):
        raise ValueError("At least three reference points required")
    if not np.isfinite(p).all() or not np.isfinite(d).all() or np.any(d <= 0):
        raise ValueError("Invalid ranges")
    centered = p-p.mean(axis=0)
    singular = np.linalg.svd(centered, compute_uv=False)
    if singular[-1] < 1e-5 or singular[0]/singular[-1] > 100:
        raise ValueError("Reference geometry is collinear or ill-conditioned")
    if np.linalg.norm(np.ptp(p, axis=0)) < min_baseline_m:
        raise ValueError("Insufficient movement baseline")
    linear_a = 2*(p[1:]-p[0])
    linear_b = d[0]**2-d[1:]**2+(p[1:]**2).sum(axis=1)-(p[0]**2).sum()
    estimate = np.linalg.lstsq(linear_a, linear_b, rcond=None)[0]
    for _ in range(30):
        delta = estimate-p
        predicted = np.maximum(np.linalg.norm(delta, axis=1), 1e-6)
        residual = predicted-d
        jacobian = delta/predicted[:, None]
        # Huber-style weights reduce one bad RSSI observation's leverage.
        weights = np.minimum(1.0, 1.5/np.maximum(np.abs(residual), 1e-6))
        step = np.linalg.lstsq(jacobian*np.sqrt(weights[:, None]), residual*np.sqrt(weights), rcond=None)[0]
        if not np.isfinite(step).all():
            raise ValueError("Unstable position solution")
        length = np.linalg.norm(step)
        if length > 5:
            step *= 5/length
        estimate -= step
        if length < 1e-6:
            break
    rms = float(np.sqrt(np.mean((np.linalg.norm(estimate-p, axis=1)-d)**2)))
    if not np.isfinite(estimate).all() or not math.isfinite(rms):
        raise ValueError("Nonfinite position solution")
    return {"x_m": float(estimate[0]), "y_m": float(estimate[1]), "residual_m": rms,
            "samples": len(p), "geometry_condition": float(singular[0]/singular[-1])}
