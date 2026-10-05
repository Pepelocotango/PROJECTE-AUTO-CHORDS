import { useCallback, useEffect, useState } from "react";
import { open as openDialog } from "@tauri-apps/plugin-dialog";
import { analyze, saveChanges, type AnalysisResult } from "./lib/api";
import { WaveformView } from "./components/WaveformView";
import {
  addChordAt,
  duplicateChord,
  editSection,
  setChordEnd,
  setChordStart,
  splitSection,
  validateChords,
  validateSections,
  type ClipKind,
  type ClipZone,
} from "./lib/model";
import { snapLabel } from "./lib/snap";

interface Selection {
  kind: ClipKind;
  index: number;
}

/**
 * Auto Chords — visor DAW-like (Sprint 2.4: edició interactiva).
 *
 * Flux:
 *  1. Tria WAV → Analitza (backend Python → JSON)
 *  2. El visor mostra l'ona + 2 carrils editables (estructura + acords)
 *  3. Edita (drag/resize/snap), elimina/duplica/renombra
 *  4. Desa els canvis (escriu CSVs + regenera clips)
 */
function App() {
  const [wavPath, setWavPath] = useState<string>("");
  const [bpm, setBpm] = useState<number>(138);
  const [bpb, setBpb] = useState<number>(4);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [selected, setSelected] = useState<Selection | null>(null);
  const [snapEnabled, setSnapEnabled] = useState<boolean>(true);
  const [renaming, setRenaming] = useState<{
    kind: ClipKind;
    index: number;
    value: string;
  } | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [dirty, setDirty] = useState<boolean>(false);

  // ------------------------------------------------------------------ backend

  async function triarWav() {
    try {
      const selectedPath = await openDialog({
        multiple: false,
        directory: false,
        filters: [{ name: "WAV", extensions: ["wav"] }],
        title: "Tria una cançó WAV",
      });
      if (typeof selectedPath === "string") {
        setWavPath(selectedPath);
        setError("");
        setAnalysis(null);
        setSelected(null);
        setDirty(false);
      }
    } catch (e) {
      setError(`Error obrint el file dialog: ${e}`);
    }
  }

  async function executarAnalisi() {
    if (!wavPath) return;
    setLoading(true);
    setError("");
    try {
      const result = await analyze(wavPath, bpm, bpb);
      if (result.error) {
        setError(result.error);
      } else {
        setBpm(result.bpm);
        setBpb(result.bpb);
        setAnalysis(result);
        setSelected(null);
        setDirty(false);
      }
    } catch (e: any) {
      setError(typeof e === "string" ? e : e?.message ?? JSON.stringify(e));
    } finally {
      setLoading(false);
    }
  }

  async function desarCanvis() {
    if (!analysis) return;
    setSaving(true);
    setError("");
    try {
      const res = await saveChanges({
        sortida: analysis.sortida,
        wav: analysis.wav,
        durada_s: analysis.durada_s,
        bpm: analysis.bpm,
        bpb: analysis.bpb,
        tempo_lliure: analysis.tempo_lliure,
        acords: analysis.acords,
        seccions: analysis.seccions,
      });
      if (res.error) {
        setError(res.error);
      } else {
        setDirty(false);
      }
    } catch (e: any) {
      setError(typeof e === "string" ? e : e?.message ?? JSON.stringify(e));
    } finally {
      setSaving(false);
    }
  }

  // ------------------------------------------------------------------- edició

  const handleEdit = useCallback(
    (kind: ClipKind, index: number, zone: ClipZone, ns: number, ne: number) => {
      setAnalysis((prev) => {
        if (!prev) return prev;
        const total = prev.durada_s;
        if (kind === "chord") {
          const acords =
            zone === "right"
              ? setChordEnd(prev.acords, index, ne, total)
              : setChordStart(prev.acords, index, ns, total);
          if (validateChords(acords)) return prev;
          setDirty(true);
          return { ...prev, acords };
        } else {
          const seccions = editSection(
            prev.seccions,
            index,
            zone,
            ns,
            ne,
            total
          );
          if (validateSections(seccions)) return prev;
          setDirty(true);
          return { ...prev, seccions };
        }
      });
    },
    []
  );

  const handleSelect = useCallback((kind: ClipKind, index: number) => {
    setSelected({ kind, index });
  }, []);

  const handleDelete = useCallback(() => {
    setAnalysis((prev) => {
      if (!prev || !selected) return prev;
      const { kind, index } = selected;
      if (kind === "chord") {
        const acords = prev.acords.slice();
        acords.splice(index, 1);
        setDirty(true);
        return { ...prev, acords };
      } else {
        const seccions = prev.seccions.slice();
        seccions.splice(index, 1);
        setDirty(true);
        return { ...prev, seccions };
      }
    });
    setSelected(null);
  }, [selected]);

  const handleDuplicate = useCallback(() => {
    setAnalysis((prev) => {
      if (!prev || !selected) return prev;
      const { kind, index } = selected;
      if (kind === "chord") {
        const { acords, newIndex } = duplicateChord(
          prev.acords,
          index,
          prev.durada_s
        );
        setSelected({ kind, index: newIndex });
        setDirty(true);
        return { ...prev, acords };
      } else {
        const { seccions, newIndex } = splitSection(prev.seccions, index);
        setSelected({ kind, index: newIndex });
        setDirty(true);
        return { ...prev, seccions };
      }
    });
  }, [selected]);

  const handleAddChord = useCallback(() => {
    setAnalysis((prev) => {
      if (!prev) return prev;
      const t = prev.durada_s / 2;
      const acords = addChordAt(prev.acords, t, prev.durada_s);
      if (acords === prev.acords) return prev;
      setDirty(true);
      return { ...prev, acords };
    });
  }, []);

  const commitRename = useCallback(() => {
    if (!renaming) return;
    const { kind, index, value } = renaming;
    const v = value.trim();
    if (!v) {
      setRenaming(null);
      return;
    }
    setAnalysis((prev) => {
      if (!prev) return prev;
      if (kind === "chord") {
        const acords = prev.acords.slice();
        const [t] = acords[index];
        acords[index] = [t, v];
        setDirty(true);
        return { ...prev, acords };
      } else {
        const seccions = prev.seccions.slice();
        const s = [...seccions[index]] as any;
        s[2] = v;
        s[3] = v;
        seccions[index] = s;
        setDirty(true);
        return { ...prev, seccions };
      }
    });
    setRenaming(null);
  }, [renaming]);

  // -------------------------------------------------------------- dreceres

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      const inInput =
        target?.tagName === "INPUT" || target?.tagName === "TEXTAREA";
      if (inInput) return;
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        handleDelete();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "d") {
        e.preventDefault();
        handleDuplicate();
      } else if (e.key === "Escape") {
        setSelected(null);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleDelete, handleDuplicate]);

  // -------------------------------------------------------------------- UI

  const snapCfg = {
    enabled: snapEnabled,
    bpm: analysis?.bpm ?? bpm,
    tempoLliure: analysis?.tempo_lliure ?? false,
  };

  return (
    <div className="app">
      <header className="header">
        <h1>Auto Chords</h1>
        <p className="subtitle">
          Detector d'acords i estructura · visor DAW-like editable
        </p>
      </header>

      <main className="main">
        <section className="panel">
          <div className="row">
            <button
              onClick={triarWav}
              disabled={loading}
              className="btn btn-primary"
            >
              {wavPath ? "Canviar WAV" : "Tria WAV…"}
            </button>
            <label className="field">
              BPM:
              <input
                type="number"
                min="40"
                max="240"
                value={bpm}
                onChange={(e) => setBpm(Number(e.target.value))}
                disabled={loading}
              />
            </label>
            <label className="field">
              Temps/compàs:
              <input
                type="number"
                min="2"
                max="12"
                value={bpb}
                onChange={(e) => setBpb(Number(e.target.value))}
                disabled={loading}
              />
            </label>
            <button
              onClick={executarAnalisi}
              disabled={!wavPath || loading}
              className="btn btn-accent"
            >
              {loading ? "Processant…" : "Analitza"}
            </button>
          </div>
          {wavPath && (
            <div className="row" style={{ marginTop: 8 }}>
              <code className="path" title={wavPath}>
                {wavPath}
              </code>
            </div>
          )}
        </section>

        {loading && (
          <section className="panel">
            <p className="hint">
              Processant… (Chordino + Segmentino, pot trigar 30-60 s)
            </p>
          </section>
        )}

        {error && (
          <section className="panel">
            <pre className="error">{error}</pre>
          </section>
        )}

        {wavPath && !error && (
          <section className="panel panel-viewer">
            <div className="viewer-header">
              <span className="viewer-badge viewer-badge-sec">Estructura</span>
              <span className="viewer-badge viewer-badge-acc">Acords</span>
              {analysis && (
                <>
                  <span className="stats-inline">
                    {analysis.durada_s.toFixed(1)}s ·{" "}
                    {analysis.acords.length} acords ·{" "}
                    {analysis.seccions.length} seccions
                  </span>
                  <label className="field">
                    <input
                      type="checkbox"
                      checked={snapEnabled}
                      onChange={(e) => setSnapEnabled(e.target.checked)}
                    />
                    {snapLabel(snapCfg)}
                  </label>
                  <button
                    className="btn"
                    onClick={handleAddChord}
                    title="Afegeix un acord al mig (provisional)"
                  >
                    + Acord
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={desarCanvis}
                    disabled={!dirty || saving}
                    title="Desa els canvis (CSV + clips WAV)"
                  >
                    {saving ? "Desant…" : dirty ? "💾 Desa" : "Desat"}
                  </button>
                </>
              )}
              {!analysis && (
                <span className="hint">
                  Prem «Analitza» per veure els acords i l'estructura.
                </span>
              )}
            </div>
            <WaveformView
              wavPath={wavPath}
              analysis={analysis}
              selected={selected}
              snapEnabled={snapEnabled}
              onSelect={handleSelect}
              onEdit={handleEdit}
              onRename={(kind, index) => {
                const value =
                  kind === "chord"
                    ? analysis?.acords[index]?.[1] ?? ""
                    : analysis?.seccions[index]?.[2] ?? "";
                setRenaming({ kind, index, value });
              }}
            />
            {analysis && (
              <p className="hint" style={{ marginTop: 8 }}>
                Arrossega els clips per moure'ls · vores per redimensionar ·
                click per situar el play · doble-click per renombrar ·
                <strong> Supr</strong> elimina · <strong>Ctrl+D</strong> duplica
                · <strong>Alt</strong> desactiva el snap mentre arrossegues.
              </p>
            )}
          </section>
        )}
      </main>

      {/* Editor de nom (flotant) */}
      {renaming && (
        <div className="rename-modal">
          <div className="rename-box">
            <label>
              {renaming.kind === "chord" ? "Nom de l'acord" : "Lletra de la secció"}:
            </label>
            <input
              autoFocus
              value={renaming.value}
              onChange={(e) =>
                setRenaming({ ...renaming, value: e.target.value })
              }
              onKeyDown={(e) => {
                if (e.key === "Enter") commitRename();
                if (e.key === "Escape") setRenaming(null);
              }}
            />
            <div className="row" style={{ marginTop: 10, justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => setRenaming(null)}>
                Cancel·la
              </button>
              <button className="btn btn-primary" onClick={commitRename}>
                Desa
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
