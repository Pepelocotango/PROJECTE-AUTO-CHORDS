# PROJECTE AUTO CHORDS — de wav a acords, automàtic

> Objectiu final: sistema totalment autònom que, donada una wav, n'extregui
> acords + estructura i generi carpetes de wavs anomenats per compàs,
> llestos per al Live. De moment: recopilació d'eines + pipeline manual
> verificat. Tot en català.

## Estat (29-09-2026, tarda)

El `wav → csv` **ja és autònom al Linux** (sonic-annotator + Chordino,
~23× temps real, idèntic al Sonic al decimal 9). I el repartiment
Live/Reaper ha quedat **definitiu** (vegeu Repartiment). Falta tancar el
circuit amb un sol script (`annotator → acords_a_live.py → wavs`).

## Eines (aquesta carpeta)

| Fitxer/carpeta | Què és |
|---|---|
| `sonic-annotator` | Binari 1.7 compilat a l'host Ubuntu (Q9400, sense AVX). Batch Vamp headless. |
| `nnls-chroma-linux64-local/` | Plugin Chordino compilat aquí (`.so` + `.cat` + `.n3` + `chord.dict`). Servidor oficial mort → build propi, verificat (exposa `chordino`, `nnls-chroma`, `tuning`). |
| `nnls-chroma-osx-v1.1/` | Binari oficial per al Mac (posat per l'operador). |
| `codi_font_chordino/` | Font `c4dm/nnls-chroma` (commit `4c5f214`). Inclou `chordextract.cpp` (CLI, possible via sense Sonic). Falta per recopilar: `vamp-plugin-sdk`. |
| `acords_a_live.py` | `csv → acords_locators.txt + guia_acords.html`. Ús: `python3 acords_a_live.py csv BPM temps_per_compàs [offset_segons]`. |
| `exemple_chordino.csv` | Sortida tipus Chordino (format `temps,acord`, `N` = sense acord). |
| `exemple_locators.txt` / `exemple_guia.html` | Sortides del py a 138 BPM 4/4. |
| `exemple_1-1-1_E.wav` / `.mid` | Referència de formats (el **wav** és el bo; el MIDI el Live l'arrodoneix). |
| `als2rpp.py` | (Aliè a aquest projecte: conversor ALS→RPP, no tocar.) |

## Pipeline verificat (02 138BPM PEP LIVE)

```
wav (Sonic+Chordino o annotator) → csv → acords_a_live.py → locators/guia
    → 119 wavs silenciosos (mateix nom `compàs-temps-setzena_ACORD`)
    → lot a pista d'àudio del Live (guia visual, sense so)
```

Dades reals: wav 246.96 s · 119 segments · 568.5 temps = 247.17 s a 138 BPM.

## Comandes

```bash
VAMP_PATH=nnls-chroma-linux64-local ./sonic-annotator \
  -d vamp:nnls-chroma:chordino:simplechord -w csv tema.wav
python3 acords_a_live.py acords.csv 138 4 [offset]
```

## App + VM Debian (Mac)

- **App** (`app/`): PyQt5 (Qt5 = l'únic Qt que corre al Q9400; Qt6 demana
  SSE4.2) amb els 2 camins (tempo fix / tempo lliure, tria l'usuari).
  Obertura: `bash AUTO_CHORDS.sh`.
- **VM Debian**: no s'hi compila res — `instal·la_vm_debian.sh` hi posa
  només llibreries d'execució (1 pkexec) i verifica. Tot corre des del
  disc compartit (`/mnt/F5EB-8EFE/...`, mateixos camins).

## Lliçons fixades (no repetir)

1. **MIDI no serveix de guia exacta**: el Live 9 arrodoneix el loop MIDI
   al compàs sencer (14.5 temps → clip 4.0.0) i l'End hi queda clavat.
   Els wavs conserven la durada al sample.
2. **MIDI buit = rebutjat**: cal ≥1 nota (fantasma C-2, canal 16, vel. 1).
3. **Snap OFF en importar en lot** (Cmd+4 o Cmd premut): si no, cada clip
   cau a inici de compàs i tot es desplaça.
4. **Prefs universals** (`Record/Warp/Launch`): `Loop/Warp Short Samples →
   Unwarped One Shot` + `Auto-Warp Long Samples → OFF`.
5. **El nom = només l'inici** (`1-1-1_E`); la fi la dona el següent fitxer.
   La setzena sempre 1 o 3 (graella de corxeres). `G/D` → `G-D` al nom.
6. **Offset**: els stems d'aquest tema arrenquen al compàs 3 → la guia
   entra al 3.1.1 (o regenerar amb offset = 8 temps).
7. Instal·lar plugin a l'host: copiar els 4 fitxers a `~/.vamp/`
   (al Mac: `~/Library/Audio/Plug-Ins/Vamp/`).

## Pendent

- [x] Script únic `wav → wavs` → `wav_a_wavs.py` (mateix motor que l'app).
- [x] `vamp-plugin-sdk` sense sistema → `.deps/` via `bash instal·la_local.sh` + `chordextract` de prova a `/tmp` (annotator intacte).
- [x] Detecció d'estructura: `fer_abc` agrupa per família (`N1/N4/N6→N`), fusiona adjacents (`C-C→C`) i resumeix repeticions (ex. `ABCBACDACA, A×4 B×2 C×3 D×1`).
- Neteja a la carpeta del tema: `midis_acords/` + `*_obsolets/` (fora del repo; cal el camí del tema).

## Repartiment (definitiu 29-09, simplificat)

**Només clips wav, als dos DAWs.** `wavs_acords/` (per acord) i
`wavs_estructura/` (per secció A–G): s'arrosseguen en lot (snap OFF) i es
posen sols. El nom del fitxer = la informació (acord/lletra + posició).
**Corregir un acord = reanomenar el wav** (la durada no canvia).
Vies descartades: PNG/vídeo (finestra negra al Reaper), MIDI (el Live
l'arrodoneix), cues WAV (el Live les ignora), txt com a clips (cap DAW
els importa). El Reaper conserva les notes d'ítem només com a extra
opcional, no com a via.

## Llicència

GPLv3 — vegeu `LICENSE`.
Copyright (c) 2026 Pëp <pepelocotango@gmail.com>.
