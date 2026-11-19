"""Camera-pixel budgets, independent of Blender. Values are quality heuristics, not guarantees."""
import math

PRESETS = {
    'CAREFUL': (2.0, 0.35, 0.7),
    'BALANCED': (1.5, 0.16, 1.0),
    'STRONG': (1.1, 0.08, 1.5),
}


def importance(span, reference):
    if reference <= 0 or not math.isfinite(span + reference):
        return 1.0
    return min(1.0, max(0.02, span / reference) ** 1.35)


def texture_demand(screen_span, uv_span, reference, detail=False, preset='BALANCED'):
    oversample, _, _ = PRESETS[preset]
    weight = importance(screen_span, reference)
    quality = max(1.0, oversample * (0.75 + 0.25 * weight))
    return max(256, screen_span / max(uv_span, 1e-6) * quality * (1.25 if detail else 1.0))


def coverage_demand(samples, preset='BALANCED'):
    """Screen-area-weighted UV demand; avoid a single subpixel UV sliver vetoing all savings.

    This is a perceptual tradeoff, not a bound: the least-covered tail may lose detail.
    """
    quantile = {'CAREFUL': .999, 'BALANCED': .99, 'STRONG': .975}[preset]
    values = sorted((value, area) for value, area in samples if area > 1e-9 and math.isfinite(value))
    total = sum(area for _, area in values)
    accumulated = 0
    for value, area in values:
        accumulated += area
        if accumulated >= total * quantile:
            return value
    return values[-1][0] if values else 0


def texture_size(width, height, demand, minimum=256):
    if width <= 0 or height <= 0 or not math.isfinite(demand):
        raise ValueError('Invalid image dimensions or texture demand')
    longest = max(width, height)
    target = math.ceil(max(minimum, demand, 1) / 256) * 256
    if target >= longest:
        return width, height
    scale = target / longest
    return max(1, round(width * scale)), max(1, round(height * scale))


def mesh_ratio(triangles, width, height, reference, preset='BALANCED'):
    span = max(width, height)
    if triangles <= 0 or span <= 0 or reference <= 0:
        return 1.0
    weight = importance(span, reference)
    if span >= reference * 0.85:
        return 1.0
    _, floor, error = PRESETS[preset]
    # Surface budget plus a silhouette floor. Pixels cannot bound geometric error;
    # the retention floor is deliberately independent of mesh density.
    pixel_error = error * (1.6 - weight)
    budget = max(512, width * height / (pixel_error * pixel_error), 8 * (width + height))
    retention = floor + (1 - floor) * weight ** 1.5
    return min(1.0, max(retention, budget / triangles))


def image_bytes(width, height, channels=4, floating=False):
    # Cycles residency is backend-dependent; count mip levels, not compressed file bytes.
    return int(width * height * max(channels, 4) * (4 if floating else 1) * 4 / 3)
