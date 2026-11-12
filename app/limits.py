"""Límits compartits per a l'edició del tempo i el compàs."""

BPM_MIN = 30.0
BPM_MAX = 350.0
NUM_MIN = 1
NUM_MAX = 12
DENOMINADORS_ADMESOS = (2, 4, 8, 16)

# Durada mínima d'un clip de tempo normal: un compàs 1/16 al BPM màxim
# (1 negra = 4/16; un compàs 1/16 = 0,25 negres).
TEMPS_MIN_CLIP = 60.0 * 0.25 / BPM_MAX


def bar_quarters(num, den):
    """Negres d'un compàs `num/den` (4/4→4, 6/8→3, 3/4→3)."""
    try:
        num, den = int(num), int(den)
    except (TypeError, ValueError):
        return 4.0
    if num <= 0 or den <= 0:
        return 4.0
    return float(num) * 4.0 / float(den)


def beat_quarters(den):
    """Negres d'un temps d'un compàs amb denominador `den` (4→1, 8→0.5)."""
    try:
        den = int(den)
    except (TypeError, ValueError):
        return 1.0
    if den <= 0:
        return 1.0
    return 4.0 / float(den)
