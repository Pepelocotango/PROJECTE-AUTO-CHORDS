import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import WaveSurfer from "wavesurfer.js";
import { convertFileSrc } from "@tauri-apps/api/core";
import type { AnalysisResult } from "../lib/api";
import type { ClipKind, ClipZone } from "../lib/model";
import { makeSnap } from "../lib/snap";
import { Clip } from "./Clip";

interface Props {
  wavPath: string;
  analysis: AnalysisResult | null;
  selected: { kind: ClipKind; index: number } | null;
  snapEnabled: boolean;
  onSelect: (kind: ClipKind, index: number) => void;
  onEdit: (
    kind: ClipKind,
    index: number,
    zone: ClipZone,
    newStart: number,
    newEnd: number
  ) => void;
  onRename: (kind: ClipKind, index: number) => void;
}

/** Colors dels carrils (semitransparents). */
const COLOR_SEC = "rgba(91, 141, 214, 0.40)";
const COLOR_SEC_BORDER = "rgba(150, 190, 240, 0.9)";
const COLOR_ACC = "rgba(255, 209, 102, 0.35)";
const COLOR_ACC_BORDER = "rgba(255, 225, 150, 0.9)";

/**
 * Visor DAW-like: ona de so (wavesurfer.js) amb 2 carrils semitransparents
 * sobreposats — estructura (a dalt) i acords (a baix).
 *
 * Els carrils es renderitzen dins del wrapper de wavesurfer (mateixa amplada
 * que la forma d'ona) mitjançant un portal de React → scroll/zoom sincronitzats.
 */
export function WaveformView(props: Props) {
  const { wavPath, analysis, selected, snapEnabled } = props;
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const [wrapperEl, setWrapperEl] = useState<HTMLElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  // 1. Crear wavesurfer (una sola vegada)
  useEffect(() => {
    if (!containerRef.current) return;
    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#4a6fa5",
      progressColor: "#8ab4f8",
      cursorColor: "#ff6b6b",
      cursorWidth: 2,
      height: 180,
      normalize: true,
      minPxPerSec: 1,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
    });
    wsRef.current = ws;

    ws.on("ready", () => {
      setLoading(false);
      setError("");
      const wrapper = ws.getWrapper();
      if (wrapper) {
        wrapper.style.position = "relative";
        wrapper.style.height = "100%";
        wrapper.style.overflow = "visible";
        setWrapperEl(wrapper);
      }
    });
    ws.on("play", () => setPlaying(true));
    ws.on("pause", () => setPlaying(false));
    ws.on("finish", () => setPlaying(false));
    ws.on("error", (e: Error) => {
      setError(`Error carregant l'àudio: ${e?.message ?? e}`);
      setLoading(false);
    });

    return () => {
      setWrapperEl(null);
      ws.destroy();
      wsRef.current = null;
    };
  }, []);

  // 2. Carregar la WAV quan canvia
  useEffect(() => {
    const ws = wsRef.current;
    if (!ws || !wavPath) return;
    setLoading(true);
    setError("");
    const url = convertFileSrc(wavPath);
    ws.load(url).catch((e) => {
      setError(`No s'ha pogut carregar la WAV: ${e}`);
      setLoading(false);
    });
  }, [wavPath]);

  const snap = makeSnap({
    enabled: snapEnabled,
    bpm: analysis?.bpm ?? 0,
    tempoLliure: analysis?.tempo_lliure ?? true,
  });

  function seek(t: number) {
    wsRef.current?.setTime(t);
  }

  const dur = analysis?.durada_s ?? 1;

  return (
    <div className="waveform-wrap">
      <div className="transport">
        <button
          className="btn btn-primary"
          onClick={() => wsRef.current?.playPause()}
          disabled={loading || !wavPath}
        >
          {playing ? "⏸ Pausa" : "▶ Play"}
        </button>
        <button
          className="btn"
          onClick={() => {
            wsRef.current?.stop();
            wsRef.current?.setTime(0);
          }}
          disabled={loading || !wavPath}
        >
          ⏹
        </button>
        <button
          className="btn"
          onClick={() => wsRef.current?.zoom(8)}
          disabled={loading || !wavPath}
          title="Ampliar"
        >
          🔍+
        </button>
        <button
          className="btn"
          onClick={() => wsRef.current?.zoom(-8)}
          disabled={loading || !wavPath}
          title="Reduir"
        >
          🔍−
        </button>
        {loading && <span className="hint">Carregant àudio…</span>}
        {error && <span className="error-inline">{error}</span>}
      </div>

      <div ref={containerRef} className="waveform" />

      {wrapperEl &&
        analysis &&
        createPortal(
          <div className="lanes-overlay">
            {/* Carril 1: estructura */}
            <div className="lane lane-sec">
              {analysis.seccions.map(([ini, fi, lletra, fam], i) => (
                <Clip
                  key={`s${i}`}
                  kind="section"
                  index={i}
                  start={ini}
                  end={fi}
                  duration={dur}
                  label={lletra}
                  title={`${lletra} (${fam}): ${ini.toFixed(2)}–${fi.toFixed(2)}s`}
                  bg={COLOR_SEC}
                  border={COLOR_SEC_BORDER}
                  selected={
                    selected?.kind === "section" && selected.index === i
                  }
                  preserveDurationOnBody
                  snap={snap}
                  onSelect={() => props.onSelect("section", i)}
                  onSeek={() => seek(ini)}
                  onEdit={(zone, ns, ne) =>
                    props.onEdit("section", i, zone, ns, ne)
                  }
                  onDoubleClick={() => props.onRename("section", i)}
                />
              ))}
            </div>

            {/* Carril 2: acords */}
            <div className="lane lane-acc">
              {analysis.acords.map(([t, nom], i) => {
                const next =
                  i + 1 < analysis.acords.length
                    ? analysis.acords[i + 1][0]
                    : dur;
                return (
                  <Clip
                    key={`a${i}`}
                    kind="chord"
                    index={i}
                    start={t}
                    end={next}
                    duration={dur}
                    label={nom}
                    title={`${nom} @ ${t.toFixed(2)}s`}
                    bg={COLOR_ACC}
                    border={COLOR_ACC_BORDER}
                    selected={
                      selected?.kind === "chord" && selected.index === i
                    }
                    preserveDurationOnBody={false}
                    snap={snap}
                    onSelect={() => props.onSelect("chord", i)}
                    onSeek={() => seek(t)}
                    onEdit={(zone, ns, ne) =>
                      props.onEdit("chord", i, zone, ns, ne)
                    }
                    onDoubleClick={() => props.onRename("chord", i)}
                  />
                );
              })}
            </div>
          </div>,
          wrapperEl
        )}
    </div>
  );
}
