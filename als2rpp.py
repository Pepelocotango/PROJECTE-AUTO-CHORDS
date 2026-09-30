#!/usr/bin/env python3
"""
als2rpp.py - Converteix les pistes d'un projecte d'Ableton Live 9 (.als)
en un projecte de Reaper (.rpp): noms, volum, pan, mute i clips d'audio
de l'arranjament (ITEM + SOURCE WAVE amb rutes absolutes).

Ús:
    python3 als2rpp.py projecte.als [sortida.rpp]

Només fa servir la biblioteca estàndard (Python 3.8 de l'Ubuntu 20.04 va bé).
"""
import gzip
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


def valor(node, ruta, per_defecte):
    """Retorna l'atribut Value del node trobat a 'ruta', o el valor per defecte."""
    if node is None:
        return per_defecte
    trobat = node.find(ruta)
    if trobat is None:
        return per_defecte
    return trobat.get("Value", per_defecte)


def nom_pista(pista):
    nom = valor(pista, "Name/EffectiveName", "")
    if not nom:
        nom = valor(pista, "Name/UserName", "")
    return nom or "Pista"


def guid():
    return "{" + str(uuid.uuid4()).upper() + "}"


def escapa(text):
    # Reaper no tolera cometes dobles dins del nom
    return text.replace('"', "'")


def llegeix_als(ruta):
    with gzip.open(ruta, "rb") as f:
        return ET.parse(f).getroot()


def ruta_mostra(file_ref, base_dir):
    """Resol la ruta absoluta del wav a partir de <FileRef> (relativa a la carpeta del .als)."""
    if file_ref is None:
        return None
    nom_node = file_ref.find("Name")
    if nom_node is None:
        return None
    nom = nom_node.get("Value", "")
    if not nom:
        return None
    rp = file_ref.find("RelativePath")
    parts = []
    if rp is not None:
        for e in list(rp):
            if e.tag == "RelativePathElement" and e.get("Dir"):
                parts.append(e.get("Dir"))
    candidata = Path(base_dir).joinpath(*parts, nom) if parts else Path(base_dir) / nom
    if candidata.exists():
        return str(candidata)
    # fallback: cerca pel nom dins la carpeta del projecte (per si la relativa canvia)
    trobats = list(Path(base_dir).rglob(nom))
    if trobats:
        return str(trobats[0])
    return str(candidata)


def clips_audio(pista):
    """Torna la llista d'<AudioClip>' d'arranjament ordenats per Time (beats)."""
    ev = pista.find("DeviceChain/MainSequencer/Sample/ArrangerAutomation/Events")
    if ev is None:
        return []
    clips = [c for c in ev.findall("AudioClip") if c.find("SampleRef/FileRef") is not None]
    def temps(c):
        try:
            return float(c.get("Time", "0"))
        except ValueError:
            return 0.0
    return sorted(clips, key=temps)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    entrada = Path(sys.argv[1])
    sortida = Path(sys.argv[2]) if len(sys.argv) > 2 else entrada.with_suffix(".rpp")

    arrel = llegeix_als(entrada)
    liveset = arrel.find("LiveSet")
    if liveset is None:
        sys.exit("No s'ha trobat <LiveSet>: no sembla un .als vàlid.")

    tempo = valor(liveset, "MasterTrack/DeviceChain/Mixer/Tempo/Manual", "120")

    tipus = ("AudioTrack", "MidiTrack", "GroupTrack", "ReturnTrack")
    pistes = [p for p in liveset.find("Tracks") if p.tag in tipus]

    linies = ['<REAPER_PROJECT 0.1 "6.0" 0']
    try:
        tempo_f = float(tempo)
    except ValueError:
        tempo_f = 120.0
    linies.append("  TEMPO %.6f 4 4" % tempo_f)
    segons_per_batec = 60.0 / tempo_f if tempo_f else 0.5
    base_dir = entrada.parent

    total_items = 0
    for p in pistes:
        mixer = p.find("DeviceChain/Mixer")
        vol = float(valor(mixer, "Volume/Manual", "1"))   # lineal, 1.0 = 0 dB
        pan = float(valor(mixer, "Pan/Manual", "0"))      # -1 (esq) .. 1 (dreta)
        # A Live, Speaker=true vol dir que la pista està activa (no silenciada)
        muted = 0 if valor(mixer, "Speaker/Manual", "true").lower() == "true" else 1

        linies += [
            "  <TRACK " + guid(),
            '    NAME "%s"' % escapa(nom_pista(p)),
            "    VOLPAN %.8f %.6f -1 -1 1" % (vol, pan),
            "    MUTESOLO %d 0 0" % muted,
        ]
        for clip in clips_audio(p):
            try:
                pos_b = float(clip.get("Time", "0"))
                ini_b = float(valor(clip, "CurrentStart", clip.get("Time", "0")))
                fi_b = float(valor(clip, "CurrentEnd", clip.get("Time", "0")))
            except ValueError:
                continue
            dur_b = fi_b - ini_b
            if dur_b <= 0:
                continue
            pos_s = pos_b * segons_per_batec
            dur_s = dur_b * segons_per_batec
            wav = ruta_mostra(clip.find("SampleRef/FileRef"), base_dir)
            nom_wav = Path(wav).name if wav else escapa(valor(clip, "Name", "audio"))
            linies += [
                "    <ITEM",
                "      POSITION %.8f" % pos_s,
                "      LENGTH %.8f" % dur_s,
                "      SOFFS 0.00000000",
                '      NAME "%s"' % escapa(nom_wav),
                "      IGUID " + guid(),
                "      IID 1",
                "      <SOURCE WAVE",
                '        FILE "%s"' % (wav or ""),
                "      >",
                "    >",
            ]
            total_items += 1
        linies.append("  >")

    linies.append(">")
    sortida.write_text("\n".join(linies) + "\n", encoding="utf-8")
    print("Fet: %d pistes, %d clips audio -> %s" % (len(pistes), total_items, sortida))


if __name__ == "__main__":
    main()
