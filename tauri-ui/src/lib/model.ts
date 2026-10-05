/**
 * model.ts — operacions sobre el model de dades (acords i seccions).
 *
 * Model (consistent amb el backend Python):
 *   - acords:   [[t_inici, nom], ...]  → la durada és implícita: fi = inici del següent
 *   - seccions: [[ini, fi, lletra, família], ...]  → durada explícita
 *
 * Regla d'or: **el final d'un clip és l'inici del següent**.
 *   - Acords: es compleix per construcció (el fi és el següent inici).
 *   - Seccions: en editar una vora, propaguem la vora del veí.
 *
 * Tot en català.
 */
import type { Acord, Seccio } from "./api";

export type ClipKind = "chord" | "section";
export type ClipZone = "left" | "body" | "right";

/** Separació mínima entre inicis d'acords (segons). */
export const MIN_GAP_S = 0.02;
/** Durada mínima d'una secció (segons). */
export const MIN_SEC_LEN_S = 0.05;

export function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** Final d'un acord = inici del següent (o durada total si és l'últim). */
export function chordEnd(acords: Acord[], i: number, total: number): number {
  return i + 1 < acords.length ? acords[i + 1][0] : total;
}

/**
 * Mou l'inici de l'acord `i` a `t` (amb clamp pels veïns).
 * El fi (inici del següent) no canvia: l'amplada del clip s'ajusta.
 */
export function setChordStart(
  acords: Acord[],
  i: number,
  t: number,
  total: number
): Acord[] {
  if (i < 0 || i >= acords.length) return acords;
  const lo = i > 0 ? acords[i - 1][0] + MIN_GAP_S : 0;
  const hi = i + 1 < acords.length ? acords[i + 1][0] - MIN_GAP_S : total;
  const nt = clamp(t, lo, Math.max(lo, hi));
  const out = acords.slice();
  out[i] = [nt, acords[i][1]];
  return out;
}

/**
 * Mou l'inici de l'acord `i+1` (= final de l'acord `i`).
 * Si `i` és l'últim acord, no fa res (el seu fi és la durada total).
 */
export function setChordEnd(
  acords: Acord[],
  i: number,
  t: number,
  total: number
): Acord[] {
  if (i + 1 >= acords.length) return acords;
  return setChordStart(acords, i + 1, t, total);
}

/**
 * Mou/redimensiona una secció mantenint la contigüitat amb els veïns.
 *
 * - `left`:  mou `ini` (i ajusta el `fi` de l'anterior, si n'hi ha)
 * - `right`: mou `fi` (i ajusta l'`ini` del següent, si n'hi ha)
 * - `body`:  desplaça la secció sencera (preservant durada)
 */
export function editSection(
  seccions: Seccio[],
  i: number,
  zone: ClipZone,
  newStart: number,
  newEnd: number,
  total: number
): Seccio[] {
  if (i < 0 || i >= seccions.length) return seccions;
  const out = seccions.map((s) => [...s] as Seccio);
  const [ini, fi] = [out[i][0], out[i][1]];

  if (zone === "left") {
    const lo = i > 0 ? out[i - 1][0] + MIN_SEC_LEN_S : 0;
    const hi = fi - MIN_SEC_LEN_S;
    const nt = clamp(newStart, lo, Math.max(lo, hi));
    out[i][0] = nt;
    if (i > 0) out[i - 1][1] = nt; // contigüitat amb l'anterior
  } else if (zone === "right") {
    const lo = ini + MIN_SEC_LEN_S;
    const hi = i + 1 < out.length ? out[i + 1][1] - MIN_SEC_LEN_S : total;
    const nt = clamp(newEnd, lo, Math.max(lo, hi));
    out[i][1] = nt;
    if (i + 1 < out.length) out[i + 1][0] = nt; // contigüitat amb el següent
  } else {
    // body: desplaça la secció sencera
    const dur = fi - ini;
    const lo = i > 0 ? out[i - 1][0] : 0;
    const hi = i + 1 < out.length ? out[i + 1][1] : total;
    const ns = clamp(newStart, lo, Math.max(lo, hi - dur));
    out[i][0] = ns;
    out[i][1] = ns + dur;
    if (i > 0) out[i - 1][1] = ns;
    if (i + 1 < out.length) out[i + 1][0] = ns + dur;
  }
  return out;
}

/** Comprova que els acords estan estrictament ordenats i sense duplicats. */
export function validateChords(acords: Acord[]): string | null {
  for (let i = 1; i < acords.length; i++) {
    if (acords[i][0] <= acords[i - 1][0] + 1e-9) {
      return "Els acords no poden compartir ni invertir l'inici.";
    }
  }
  return null;
}

/** Comprova que les seccions no se solapen i tenen durada vàlida. */
export function validateSections(seccions: Seccio[]): string | null {
  for (let i = 0; i < seccions.length; i++) {
    const [ini, fi] = seccions[i];
    if (fi <= ini) return `La secció ${seccions[i][2]} té durada no vàlida.`;
    if (i > 0 && ini < seccions[i - 1][1] - 1e-9) {
      return "Les seccions no poden solapar-se.";
    }
  }
  return null;
}

/** Duplica un acord just després (a mig camí cap al següent). */
export function duplicateChord(
  acords: Acord[],
  i: number,
  total: number
): { acords: Acord[]; newIndex: number } {
  const end = chordEnd(acords, i, total);
  const start = acords[i][0];
  const mid = start + (end - start) / 2;
  if (mid - start < MIN_GAP_S * 2) {
    return { acords, newIndex: i };
  }
  const out = acords.slice();
  out.splice(i + 1, 0, [mid, acords[i][1]]);
  return { acords: out, newIndex: i + 1 };
}

/** Duplica una secció just després (partint per la meitat). */
export function splitSection(
  seccions: Seccio[],
  i: number
): { seccions: Seccio[]; newIndex: number } {
  const [ini, fi, lletra, fam] = seccions[i];
  const mid = ini + (fi - ini) / 2;
  if (mid - ini < MIN_SEC_LEN_S || fi - mid < MIN_SEC_LEN_S) {
    return { seccions, newIndex: i };
  }
  const out = seccions.slice();
  const nova: Seccio = [mid, fi, lletra, fam];
  out[i] = [ini, mid, lletra, fam];
  out.splice(i + 1, 0, nova);
  return { seccions: out, newIndex: i + 1 };
}

/** Afegeix un acord nou al final o en un forat. */
export function addChordAt(acords: Acord[], t: number, total: number): Acord[] {
  const nt = clamp(t, 0, total);
  const out = acords.slice();
  let idx = out.length;
  for (let i = 0; i < out.length; i++) {
    if (out[i][0] > nt) {
      idx = i;
      break;
    }
  }
  // Evitem col·lisions directes
  const before = idx > 0 ? out[idx - 1][0] : -Infinity;
  const after = idx < out.length ? out[idx][0] : Infinity;
  if (nt - before < MIN_GAP_S || after - nt < MIN_GAP_S) return acords;
  out.splice(idx, 0, [nt, "N"]);
  return out;
}
