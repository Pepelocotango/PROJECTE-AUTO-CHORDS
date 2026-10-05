/**
 * snap.ts — quantització temporal (snap) per a l'edició de clips.
 *
 * Si hi ha BPM definit, l'snap és a la subdivisió del beat (corxera).
 * Si no (tempo lliure), l'snap és a 0,1 s.
 *
 * L'snap es pot desactivar temporalment prement Alt mentre s'arrossega.
 */
export interface SnapConfig {
  enabled: boolean;
  bpm: number;
  tempoLliure: boolean;
}

export function makeSnap(cfg: SnapConfig): (t: number) => number {
  if (!cfg.enabled) return (t) => t;
  if (cfg.tempoLliure || !cfg.bpm || cfg.bpm <= 0) {
    // Mode lliure: snap a 0,1 s
    return (t) => Math.round(t * 10) / 10;
  }
  const beat = 60 / cfg.bpm;
  const step = beat / 2; // corxera
  return (t) => Math.round(t / step) * step;
}

/** Etiqueta llegible del pas de snap actiu (per mostrar a la UI). */
export function snapLabel(cfg: SnapConfig): string {
  if (!cfg.enabled) return "snap OFF";
  if (cfg.tempoLliure || !cfg.bpm || cfg.bpm <= 0) return "snap 0,1 s";
  return "snap corxera";
}
