"""Prova funcional del host Vamp i els plugins al paquet (smoke test de Windows).

Genera un WAV sintètic (un acord + pulsacions) i executa el host propi amb
**Chordino** (nnls-chroma) i amb **qm-tempotracker** (Queen Mary), verificant
que el plugin CARREGA i que escriu el CSV. És el control mínim que ha de
passar abans d'empaquetar.

També emet ordres de workflow de GitHub (`::error::` / `::notice::`) perquè, si
falla al CI, la CAUSA quedi a les anotacions del check-run (visibles per API).

Ús:
    python eines/prova_windows.py [ARREL]

`ARREL` és la carpeta on viuen `vamp_host_local.exe`, `nnls-chroma-win64-local/`
i `qm-vamp-plugins-win64-local/` (per defecte, l'arrel del projecte; per al
paquet congelat, el seu directori `_internal`).
"""
import math
import os
import struct
import subprocess
import sys
import tempfile
import traceback
import wave

ARREL_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _wf(msg, nivell="error"):
    """Emissio d'ordre de workflow de GitHub en una sola linia (ASCII segur)."""
    net = " ".join(str(msg).split())
    print(f"::{nivell}::{net[:900]}", flush=True)


def crea_wav(ruta, sr=44100, segons=8.0, bpm=120.0):
    """WAV mono: un acord de fons + pulsacions (perquè el tempo detector hi vegi onsets)."""
    n = int(sr * segons)
    periode = int(sr * 60.0 / bpm)   # mostres per pols
    crispetes = int(sr * 0.03)       # 30 ms
    dades = bytearray()
    for i in range(n):
        t = i / sr
        v = (0.10 * math.sin(2 * math.pi * 220 * t)       # A3
             + 0.07 * math.sin(2 * math.pi * 277.18 * t)  # C#4
             + 0.07 * math.sin(2 * math.pi * 329.63 * t))  # E4
        if periode and (i % periode) < crispetes:
            v += 0.6 * (1.0 - (i % periode) / crispetes)
        dades += struct.pack("<h", max(-32767, min(32767, int(v * 32767))))
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(dades))


def executa_host(arrel, plugin, wav, csv, env):
    """Executa el host per a un transform. Retorna (rc, stdout, stderr)."""
    host = os.path.join(arrel, "vamp_host_local.exe")
    if not os.path.isfile(host):
        host = os.path.join(arrel, "vamp_host_local")  # per si es prova a Linux
    if not os.path.isfile(host):
        raise FileNotFoundError(f"no trobo el host a {arrel}")
    cmd = [host, "--plugin", plugin, "--csv", csv, wav]
    print("  $", " ".join(cmd), flush=True)
    # encoding explicit + errors=replace: mai petar per decodificacio a Windows.
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, timeout=600)
    if (p.stdout or "").strip():
        print("  stdout:", p.stdout.strip()[:500], flush=True)
    if (p.stderr or "").strip():
        print("  stderr:", p.stderr.strip()[:500], flush=True)
    return p.returncode, p.stdout or "", p.stderr or ""


def linies(ruta):
    if not os.path.isfile(ruta):
        return 0
    with open(ruta, encoding="utf-8", errors="replace") as f:
        return sum(1 for l in f if l.strip())


def main():
    arrel = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else ARREL_REPO
    print(f"Prova Windows — arrel: {arrel}", flush=True)

    env = dict(os.environ)
    # Al repo les DLLs són a portable/win-dlls; al paquet, al costat de l'exe.
    for d in (os.path.join(arrel, "portable", "win-dlls"), arrel):
        if os.path.isdir(d):
            env["PATH"] = d + os.pathsep + env.get("PATH", "")
    dirs = [os.path.join(arrel, "nnls-chroma-win64-local"),
            os.path.join(arrel, "qm-vamp-plugins-win64-local")]
    env["VAMP_PATH"] = os.pathsep.join(dirs)

    # --- diagnòstic previ (ho posem a les anotacions) ---
    host = os.path.join(arrel, "vamp_host_local.exe")
    _wf(f"host={host} existeix={os.path.isfile(host)}", "notice")
    for d in dirs:
        try:
            cont = ", ".join(sorted(os.listdir(d))) if os.path.isdir(d) else "(NO existeix)"
        except OSError as e:
            cont = f"ERROR {e!r}"
        _wf(f"plugin_dir={d} -> {cont}", "notice")
    win_dlls = os.path.join(arrel, "portable", "win-dlls")
    if os.path.isdir(win_dlls):
        _wf(f"win-dlls -> {', '.join(sorted(os.listdir(win_dlls)))}", "notice")
    _wf(f"VAMP_PATH={env['VAMP_PATH']}", "notice")

    tmp = tempfile.mkdtemp(prefix="ac_wintest_")
    wav = os.path.join(tmp, "prova.wav")
    crea_wav(wav)
    print(f"WAV de prova: {wav} ({os.path.getsize(wav)} bytes)", flush=True)

    fallades = []
    try:
        csv_ch = os.path.join(tmp, "chordino.csv")
        rc, out, err = executa_host(arrel, "nnls-chroma:chordino:simplechord",
                                    wav, csv_ch, env)
        n = linies(csv_ch)
        print(f"Chordino: rc={rc}, línies={n}", flush=True)
        if rc != 0 or n < 1:
            fallades.append(f"Chordino rc={rc} linies={n} err={err.strip()[:200]}")

        csv_qm = os.path.join(tmp, "qm_tempo.csv")
        rc, out, err = executa_host(arrel, "qm-vamp-plugins:qm-tempotracker:tempo",
                                    wav, csv_qm, env)
        n = linies(csv_qm)
        print(f"qm-tempotracker: rc={rc}, línies={n}", flush=True)
        if rc != 0:
            fallades.append(f"qm-tempotracker rc={rc} err={err.strip()[:200]}")
        elif n < 1:
            print("  AVÍS: el tempo detector no ha escrit línies (potser cal més onsets)", flush=True)
    except Exception as e:  # noqa: BLE001
        _wf(f"prova_windows excepcio: {e!r}")
        print(traceback.format_exc(), flush=True)
        raise SystemExit(3)

    if fallades:
        _wf("PROVA FALLIDA: " + " | ".join(fallades))
        raise SystemExit("PROVA FALLIDA: " + "; ".join(fallades))
    _wf("PROVA OK: host i plugins carreguen i escriuen CSV.", "notice")
    print("PROVA OK: host i plugins carreguen i escriuen CSV.", flush=True)


if __name__ == "__main__":
    main()
