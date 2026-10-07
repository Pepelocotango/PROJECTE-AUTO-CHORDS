"""Prova funcional del host Vamp i els plugins al paquet (smoke test de Windows).

Genera un WAV sintètic (un acord + pulsacions) i executa el host propi amb
**Chordino** (nnls-chroma) i amb **qm-tempotracker** (Queen Mary), verificant
que el plugin CARREGA i que escriu el CSV. És el control mínim que ha de
passar abans d'empaquetar.

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
import wave

ARREL_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def crea_wav(ruta, sr=44100, segons=8.0, bpm=120.0):
    """WAV mono: un acord de fons + pulsacions (perquè el tempo detector hi vegi onsets)."""
    n = int(sr * segons)
    periode = int(sr * 60.0 / bpm)
    crispetes = int(sr * 0.03)  # 30 ms
    dades = bytearray()
    for i in range(n):
        t = i / sr
        v = (0.10 * math.sin(2 * math.pi * 220 * t)      # A3
             + 0.07 * math.sin(2 * math.pi * 277.18 * t)  # C#4
             + 0.07 * math.sin(2 * math.pi * 329.63 * t))  # E4
        if i % periode < crispetes:
            v += 0.6 * (1.0 - (i % periode) / crispetes)
        dades += struct.pack("<h", max(-32767, min(32767, int(v * 32767))))
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(dades))


def executa_host(arrel, plugin, wav, csv, env):
    host = os.path.join(arrel, "vamp_host_local.exe")
    if not os.path.isfile(host):
        host = os.path.join(arrel, "vamp_host_local")  # per si es prova a Linux
    if not os.path.isfile(host):
        raise SystemExit(f"ERROR: no trobo el host a {arrel}")
    cmd = [host, "--plugin", plugin, "--csv", csv, wav]
    print("  $", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)
    if p.stdout.strip():
        print("  stdout:", p.stdout.strip()[:400])
    if p.stderr.strip():
        print("  stderr:", p.stderr.strip()[:400])
    return p.returncode


def linies(ruta):
    if not os.path.isfile(ruta):
        return 0
    with open(ruta, encoding="utf-8", errors="replace") as f:
        return sum(1 for l in f if l.strip())


def main():
    arrel = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else ARREL_REPO
    print(f"Prova Windows — arrel: {arrel}")

    env = dict(os.environ)
    # Al repo les DLLs són a portable/win-dlls; al paquet, al costat de l'exe.
    for d in (os.path.join(arrel, "portable", "win-dlls"), arrel):
        if os.path.isdir(d):
            env["PATH"] = d + os.pathsep + env.get("PATH", "")
    dirs = [os.path.join(arrel, "nnls-chroma-win64-local"),
            os.path.join(arrel, "qm-vamp-plugins-win64-local")]
    env["VAMP_PATH"] = os.pathsep.join(dirs)

    tmp = tempfile.mkdtemp(prefix="ac_wintest_")
    wav = os.path.join(tmp, "prova.wav")
    crea_wav(wav)
    print(f"WAV de prova: {wav} ({os.path.getsize(wav)} bytes)")

    fallades = []

    csv_ch = os.path.join(tmp, "chordino.csv")
    rc = executa_host(arrel, "nnls-chroma:chordino:simplechord", wav, csv_ch, env)
    n = linies(csv_ch)
    print(f"Chordino: rc={rc}, línies={n}")
    if rc != 0 or n < 1:
        fallades.append(f"Chordino (rc={rc}, línies={n})")

    csv_qm = os.path.join(tmp, "qm_tempo.csv")
    rc = executa_host(arrel, "qm-vamp-plugins:qm-tempotracker:tempo", wav, csv_qm, env)
    n = linies(csv_qm)
    print(f"qm-tempotracker: rc={rc}, línies={n}")
    if rc != 0:
        fallades.append(f"qm-tempotracker (rc={rc})")
    elif n < 1:
        print("  AVÍS: el tempo detector no ha escrit línies (potser cal més onsets)")

    if fallades:
        raise SystemExit("PROVA FALLIDA: " + "; ".join(fallades))
    print("PROVA OK: host i plugins carreguen i escriuen CSV.")


if __name__ == "__main__":
    main()
