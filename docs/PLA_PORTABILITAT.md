# PLA DE PORTABILITAT — fer AUTO CHORDS autocontingut

> **2026-10-07.** Pla de treball per fases (decisió de l'operador: **es volen
> totes**). Basat en `docs/PORTABILITAT.md` (anàlisi amb mides i `ldd` reals).
> **Regla**: una fase = un o més commits, amb tests; res trencat en acabar cada
> fase (els 165 tests han de seguir verds).

## Objectiu final
Una carpeta d'**~160 MB** que es copia a qualsevol **Linux x86_64 modern**
(amb PipeWire/Pulse) i funciona amb **doble clic**, **sense instal·lar res**
ni Python ni llibreries. Els plugins i l'host d'anàlisi hi viatgen a dins.

---

## FASE 1 — Host Vamp propi (treure `sonic-annotator`) ⭐

**Per què**: `sonic-annotator` arrossega **~70 llibreries** (Qt6, ICU, glib,
gnutls, curl…). Els nostres plugins, en canvi, només depenen de libc/libstdc++.

| # | Tasca | Criteri |
|---|-------|---------|
| 1.1 | Escriure un host mínim (`eines/vamp_host.cpp`) amb `libvamp-hostsdk`: carregar un plugin, fer el transform, escriure el CSV **amb el mateix format** que `sonic-annotator` | compila amb `-msse -msse2` |
| 1.2 | Provar-lo amb Chordino / Segmentino / qm i **comparar el CSV** amb el del sonic-annotator | CSV idèntic (o equivalent) |
| 1.3 | Integrar-lo al `pipeline` (substituir la crida a `SONIC` de forma transparent) | els 165 tests verds |
| 1.4 | Verificar el `ldd` del nou host | només libc/libstdc++/sndfile (sense Qt6) |

**Decisió tècnica a prendre a l'inici**: host **C++** (control total, ja
compilam C++) o el **mòdul `vamp` de Python** (menys codi, però cal instal·lar-lo).
→ Provaré primer el C++ (encara que sigui més feina, no afegeix dependències pip).

---

## FASE 2 — CPython portable (treure el Python del sistema)

| # | Tasca | Criteri |
|---|-------|---------|
| 2.1 | Descarregar **`python-build-standalone`** (build **SSE**, sense AVX) a `portable/python/` | arrenca al Q9400 |
| 2.2 | Instal·lar-hi PyQt5, `numpy<2`, pyqtgraph (rodes compatibles) | `import PyQt5, numpy` OK |
| 2.3 | `AUTO_CHORDS.sh` que **prefereixi el Python portable** i, si no, el `.venv` | la app arrenca des del portable |
| 2.4 | Provar la GUI completa (offscreen + real) | arrenca i carrega una WAV |

---

## FASE 3 — `ffmpeg` estàtic embeGut (import de formats sense sistema)

| # | Tasca | Criteri |
|---|-------|---------|
| 3.1 | Descarregar un **`ffmpeg` estàtic** a `portable/bin/` | `-version` funciona |
| 3.2 | `app/ffmpeg.py` que **prefereixi el local** (`portable/bin`) i caigui al del sistema | import d'un mp3 sense el ffmpeg del sistema |

---

## FASE 4 — Àudio i requisits d'entorn

| # | Tasca | Criteri |
|---|-------|---------|
| 4.1 | Detecció del reproductor (`paplay` → `aplay`) i **missatge clar** si no n'hi ha | l'app avisa en lloc de fallar |
| 4.2 | Documentar el requisit de **PipeWire/Pulse** al README/DEVELOPING | documentat |

---

## FASE 5 — Empaquetat i distribució

| # | Tasca | Criteri |
|---|-------|---------|
| 5.1 | `empaqueta_portable.sh` → munta `AUTO_CHORDS_PORTABLE/` excloent `.deps/`, `.git/`, `.venv/`, `temp/`, `__pycache__` | carpeta llesta |
| 5.2 | Verificació **en brut**: executar la carpeta portable amb el `PATH` net / un directori diferent | funciona |
| 5.3 | *(opcional)* **AppImage** | un sol fitxer |
| 5.4 | Docs: `docs/PORTABILITAT.md` (resultat) + README (com executar el portable) | documentat |

---

## Ordre d'execució i fites

```
F1 (host) ──► F2 (Python portable) ──► F3 (ffmpeg) ──► F4 (àudio) ──► F5 (paquet)
   ⭐ el canvi            ─────────── el paquet ja és funcional aquí ───────────►
   arquitectònic
```

**Mida objectiu**: ~160 MB (avui 515 MB; 198 MB dels quals són `.deps`, que
no calen per executar).

## Riscos (verificar a cada fase)
- ⚠️ **Q9400 sense AVX**: `python-build-standalone` i les rodes han de ser SSE.
- ⚠️ **Vamp SDK**: els headers són a `.deps/usr/include` (caldrà copiar-los al repo de build).
- ⚠️ **Cap regressió**: a cada fase, **165/165 tests**.
- ⚠️ **Windows/macOS**: fora d'abast d'aquest pla (GUI portable, però els `.so` i l'àudio són per SO).

## No-objectius (per ara)
- Instal·ladors natius (.deb/.exe/.dmg).
- Execució a Windows/macOS.
- Empaquetar el daemon d'àudio.
