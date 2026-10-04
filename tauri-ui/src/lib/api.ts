/**
 * Wrapper sobre les invocacions de Tauri (commands definits a src-tauri/src/main.rs).
 *
 * Cada command té:
 *   - Una funció TypeScript que l'invoca amb els arguments correctes
 *   - Tipus TypeScript per a la resposta
 *
 * Si el backend Python canvia la signatura, cal actualitzar aquí.
 */
import { invoke } from "@tauri-apps/api/core";

/**
 * Crida el pipeline python3 wav_a_wavs.py <wav> <bpm> <bpb>.
 *
 * @param wavPath - camí absolut a la cançó WAV
 * @param bpm - tempo per defecte (opcional, default 138)
 * @param bpb - temps per compàs (opcional, default 4)
 * @returns - stdout del procés (amb la informació de detecció)
 * @throws - stderr si Python falla
 */
export async function runDetectChords(
  wavPath: string,
  bpm: number = 138,
  bpb: number = 4
): Promise<string> {
  return await invoke<string>("detect_chords", {
    wavPath,
    bpm,
    bpb,
  });
}