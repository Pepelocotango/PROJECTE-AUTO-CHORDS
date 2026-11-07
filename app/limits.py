"""Límits compartits per a l'edició del tempo i el compàs."""

BPM_MIN = 30.0
BPM_MAX = 350.0
NUM_MIN = 1
NUM_MAX = 12
DENOMINADORS_ADMESOS = (2, 4, 8)

# Durada mínima d'un clip de tempo normal: un compàs 1/8 al BPM màxim.
TEMPS_MIN_CLIP = 60.0 * 0.5 / BPM_MAX
