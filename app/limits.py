"""Límits compartits per a l'edició del tempo i el compàs."""

BPM_MIN = 30.0
BPM_MAX = 350.0
NUM_MIN = 1
NUM_MAX = 12
DENOMINADORS_ADMESOS = (2, 4, 8, 16)

# Durada mínima d'un clip de tempo normal: un compàs 1/16 al BPM màxim
# (1 negra = 4/16; un compàs 1/16 = 0,25 negres).
TEMPS_MIN_CLIP = 60.0 * 0.25 / BPM_MAX
