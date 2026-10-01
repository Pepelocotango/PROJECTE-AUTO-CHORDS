# Full de ruta — PROJECTE AUTO CHORDS

Visió: a partir de un arxiu de audio carregat a la app, n'extraiem acords + estructura , pensat principalment en obtenir carpetes separades amb clips de wavs llestos per al Live/Reaper, pero obert a altres exportacions futures.
amb un visor on **escoltar, navegar, corregir i re-exportar**.
Tot en català. Llicència: GPLv3.

## Fase A — Visor navegable ✅ (prototip `app/visor.py`)

- Ona amb pics precalculats + cursor + doble-clic per saltar.
- Escolta amb `paplay` extern (QtMultimedia aparcat), volum/mute programari.
- Transports: play/pausa/stop, ±10 s, loop A-B amb regió pintada,
  zoom, temps `mm:ss / mm:ss`.
- Botó «Analitza»: Chordino+Segmentino+ABC en fil, omple les llistes.
- Ressalt de l'acord/secció que sona. Registre visible + tancament que
  sempre mata l'àudio.
- Sabem que està bé quan: obrir la wav de 165 s, analitzar, navegar per
  acords/seccions amb loop i volum, tancar amb la X en silenci.

## Fase B — Edició (següent)

1. **Corregir acord** ✅: doble-clic → canvia l'etiqueta → es desa al csv
   de `<tema>_ACORDS/` i es regeneren els `wavs_acords/` (locators+guia
   inclosos), sense re-analitzar. ✅ quan: un acord corregit surt amb el
   nom nou al wav.
2. **Partir/fusionar secció**: clic dret a l'ABC → parteix/fusiona →
   es regenera `estructura_ABC.csv` + `wavs_estructura/`. ✅ quan: la
   seqüència de lletres reflecteix el canvi i els wavs casen.
3. **Noms `music21`** (BSD): substitueix el `style()` casolà
   (arrel/baix/inversió de debò). ✅ quan: `G/D`, `Cmaj7`, `Am` normalitzats.

## Fase C — Tancament del cercle

- Script únic `wav → wavs` ja existeix (`wav_a_wavs.py`); connectar-lo com
  a export del visor (un clic: locators + guia + les dues carpetes).
- `pyproject.toml` instal·lable de debò (`pip install .`) quan el visor
  deixi de ser prototip.
- ✅ final quan: de la wav als clips del Live sense terminal entremig.
