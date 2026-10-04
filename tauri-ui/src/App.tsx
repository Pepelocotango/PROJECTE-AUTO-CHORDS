import { useState } from "react";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { runDetectChords } from "./lib/api";

/**
 * Hello World de l'app Tauri.
 *
 * Flux:
 *  1. L'usuari tria una WAV amb un file dialog natiu (Tauri).
 *  2. L'app crida el backend Python (wav_a_wavs.py) via subprocess.
 *  3. Es mostra la sortida (informativa, en properes iteracions serà
 *     el visor DAW-like amb ones, acords i estructura).
 */
function App() {
  const [wavPath, setWavPath] = useState<string>("");
  const [output, setOutput] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  async function triarWav() {
    try {
      const selected = await openDialog({
        multiple: false,
        directory: false,
        filters: [{ name: "WAV", extensions: ["wav"] }],
        title: "Tria una cançó WAV",
      });
      if (typeof selected === "string") {
        setWavPath(selected);
        setError("");
      }
    } catch (e) {
      setError(`Error obrint el file dialog: ${e}`);
    }
  }

  async function detectarAcords() {
    if (!wavPath) return;
    setLoading(true);
    setError("");
    setOutput("Processant… (pot trigar 30-60 s per a una cançó sencera)\n");
    try {
      const text = await runDetectChords(wavPath);
      setOutput(text);
    } catch (e: any) {
      const msg = typeof e === "string" ? e : e?.message ?? JSON.stringify(e);
      setError(msg);
      setOutput("");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Auto Chords</h1>
        <p className="subtitle">
          Detector d'acords i estructura · backend Chordino + Segmentino
        </p>
      </header>

      <main className="main">
        <section className="panel">
          <h2>1. Tria la cançó</h2>
          <div className="row">
            <button
              onClick={triarWav}
              disabled={loading}
              className="btn btn-primary"
            >
              {wavPath ? "Canviar WAV" : "Tria WAV…"}
            </button>
            {wavPath && (
              <code className="path" title={wavPath}>
                {wavPath}
              </code>
            )}
          </div>
        </section>

        <section className="panel">
          <h2>2. Detecta acords + estructura</h2>
          <button
            onClick={detectarAcords}
            disabled={!wavPath || loading}
            className="btn btn-accent"
          >
            {loading ? "Processant…" : "Detecta"}
          </button>
        </section>

        {(output || error) && (
          <section className="panel">
            <h2>3. Sortida</h2>
            {error && <pre className="error">{error}</pre>}
            {output && <pre className="output">{output}</pre>}
            <p className="hint">
              Aquesta és la versió <strong>Hello World</strong>. La versió
              completa mostrarà el <strong>visor DAW-like</strong> amb ones,
              2 carrils (acords + estructura) i tota la interacció de la
              Fase D del ROADMAP.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;