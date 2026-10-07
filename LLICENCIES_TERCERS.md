# Llicències i reconeixement de tercers

> AUTO CHORDS és **GPL-3.0-or-later** (vegeu `LICENSE`). Els components de
> tercers que **distribuïm** (dins el repositori o dins l'AppImage) i les
> seves llicències són els següents. Totes són **compatibles** amb la GPLv3.
> Última revisió: **2026-10-07**.

## Resum

| Component | Llicència | On va | Enllaç |
|-----------|-----------|-------|--------|
| **Lucide** (icones de la UI) | **ISC** + **MIT** (les derivades de Feather) | `icones/` (repo + AppImage) | https://lucide.dev |
| **Chordino / NNLS-Chroma** (Matthias Mauch, C4DM) | **GPL-2.0+** | `nnls-chroma-linux64-local/` | https://code.soundsoftware.ac.uk/projects/nnls-chroma |
| **QM Vamp Plugins** (Queen Mary) | **GPL-2.0+** | `qm-vamp-plugins-linux64-local/` | https://github.com/c4dm/qm-vamp-plugins |
| **Vamp Plugin SDK** (enllaçat a l'host) | **MIT / BSD-3** | `vamp_host_local` | https://github.com/c4dm/vamp-plugin-sdk |
| **Sonic Annotator** (reserva) | **GPL-2.0+** | `sonic-annotator` | https://github.com/sonic-visualiser/sonic-annotator |
| **CPython** (Python portable) | **PSF-2.0** | AppImage (`portable/`) | https://www.python.org |
| **PyQt5 / PyQt5-Qt5** | **GPL-3.0** | AppImage | https://riverbankcomputing.com/software/pyqt |
| **Qt 5** (dins la roda PyQt5) | **LGPL-3.0** (+ parts GPL) | AppImage | https://www.qt.io |
| **NumPy** | **BSD-3-Clause** | AppImage | https://numpy.org |
| **libsndfile** (enllaçada) | **LGPL-2.1+** | `vamp_host_local` | https://libsndfile.github.io/libsndfile |
| **FFmpeg** (build estàtic) | **GPL-3.0** | AppImage (`portable/bin/ffmpeg`) | https://ffmpeg.org |
| **AppImageKit runtime** | **MIT** | AppImage | https://github.com/AppImage/AppImageKit |

## Notes d'obligacions

- **GPL-2.0+ / GPL-3.0** (Chordino, Queen Mary, Sonic Annotator, PyQt5,
  FFmpeg): el **codi font complet** d'aquests components es pot obtenir
  gratuïtament als enllaços de sobre. En distribuir AUTO CHORDS s'ofereix
  aquest codi sense cap cost addicional. AUTO CHORDS és ell mateix GPLv3, de
  manera que no hi ha incompatibilitat.
- **LGPL** (Qt5, libsndfile): es distribueixen com a **biblioteques
  compartides** (`.so`), cosa que permet **substituir-les** per versions
  modificades → compleix el requisit de relinkatge de la LGPL. El codi font
  és als enllaços de sobre.
- **ISC (Lucide) i MIT (Feather)**: el text **complet** de les llicències i
  els avisos de copyright que exigeixen es troben a **`icones/LICENSE`**.
- **BSD / PSF**: requereixen reproduir l'avís de copyright (als respectius
  paquets/roues).

## Detall de les icones

Les icones de la interfície viuen a `icones/` i provenen del projecte
**Lucide** (https://lucide.dev), que es distribueix sota **ISC**. Algunes
d'elles (p. ex. `compass`, `maximize`, `music`, `square`, `target`,
`zoom-in`, `zoom-out`) són **derivades del projecte Feather** i es
distribueixen sota **MIT** (© 2013-present Cole Bemis). El text complet de
totes dues llicències és a `icones/LICENSE`.

## Eines de compilació (NO es distribueixen)

`g++`, `appimagetool`, etc. són eines de build; no formen part del producte
distribuït.
