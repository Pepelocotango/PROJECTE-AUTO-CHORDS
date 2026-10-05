/**
 * Wrapper sobre les invocacions de Tauri (commands definits a
 * `src-tauri/src/lib.rs`).
 *
 * Cada command té:
 *   - Una funció TypeScript que l'invoca amb els arguments correctes
 *   - Tipus TypeScript per a la resposta
 *
 * Si el backend Rust/Python canvia la signatura, cal actualitzar aquí.
 */
import { invoke } from "@tauri-apps/api/core";

/** Un acord: [temps_inici_s, nom] (ex. [16.44, "E7"]). */
export type Acord = [number, string];

/** Una secció: [inici_s, fi_s, lletra, família] (ex. [0.0, 21.36, "A", "N"]). */
export type Seccio = [number, number, string, string];

/** Resultat complet de l'anàlisi d'una WAV. */
export interface AnalysisResult {
  wav: string;
  sortida: string;
  durada_s: number;
  bpm: number;
  bpb: number;
  tempo_lliure: boolean;
  acords: Acord[];
  seccions: Seccio[];
  /** Si el backend ha fallat, ve aquí en lloc de les dades. */
  error?: string;
}

/**
 * Executa el pipeline complet (Chordino + Segmentino + clips) sobre una WAV
 * i retorna el resultat estructurat en JSON.
 *
 * @param wavPath - camí absolut a la cançó WAV
 * @param bpm - tempo (per defecte 138)
 * @param bpb - temps per compàs (per defecte 4)
 * @returns - el resultat complet (acords, seccions, durada, etc.)
 * @throws - error si la comunicació amb Tauri falla
 */
export async function analyze(
  wavPath: string,
  bpm: number = 138,
  bpb: number = 4
): Promise<AnalysisResult> {
  const jsonText = await invoke<string>("analyze", { wavPath, bpm, bpb });
  try {
    return JSON.parse(jsonText) as AnalysisResult;
  } catch (e) {
    throw new Error(`Resposta del backend no és JSON vàlid: ${e}`);
  }
}

/** Resposta del backend en desar canvis. */
export interface SaveResult {
  ok?: boolean;
  n_wavs_acords?: number;
  n_wavs_estructura?: number;
  error?: string;
}

/** Dades que s'envien al backend per desar. */
export interface SavePayload {
  sortida: string;
  wav: string;
  durada_s: number;
  bpm: number;
  bpb: number;
  tempo_lliure: boolean;
  acords: Acord[];
  seccions: Seccio[];
}

/**
 * Desa els canvis al disc: escriu `acords.csv` + `estructura_ABC.csv`
 * i regenera els clips WAV (`wavs_acords/` + `wavs_estructura/`).
 *
 * @param payload - l'estat complet editat
 * @returns - resum de la regeneració
 * @throws - error si la comunicació amb Tauri falla
 */
export async function saveChanges(payload: SavePayload): Promise<SaveResult> {
  const jsonText = await invoke<string>("save_changes", {
    payload: JSON.stringify(payload),
  });
  try {
    return JSON.parse(jsonText) as SaveResult;
  } catch (e) {
    throw new Error(`Resposta del backend no és JSON vàlid: ${e}`);
  }
}
