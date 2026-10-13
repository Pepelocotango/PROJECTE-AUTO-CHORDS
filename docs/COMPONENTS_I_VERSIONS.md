# Components i versions

> Generat per **`eines/genera_inventari.py`** a partir de fonts del
> **repositori** (`requirements.txt` i `eines/deps_fixades.env`) —
> **sense mirar l'entorn local** — perquè el CI pugui comprovar que
> està al dia (`git diff --exit-code`).
> Serveix per **vigilar avisos de seguretat**: si se'n publica un d'un
> d'aquests components, aquí es veu quina versió en fem servir i on es fixa.
>
> Per regenerar-lo després de canviar una versió:
> ```
> python3 eines/genera_inventari.py
> ```

## Resum

| Component | Versió | Origen |
|---|---|---|
| Python (portable, el que s'empaqueta) | **3.12.15** | python-build-standalone **20261003** |
| PyQt5 | 5.15.11 | PyPI (a macOS 10.13: 5.15.10) |
| PyQt5-Qt5 | 5.15.19 | PyPI |
| PyQt5_sip | 12.19.0 | PyPI |
| numpy | 1.26.4 | PyPI (**1.x**: el Q9400 no té AVX) |
| sounddevice | 0.5.6 | PyPI (àudio natiu mac/win) |
| cffi | 2.0.0 | PyPI |
| ffmpeg (Linux) | **7.0.2** | johnvansickle (estàtic) |
| ffmpeg (macOS) | **9.0.2** | evermeet.cx (estàtic) |
| ffmpeg (Windows) | **9.0.2** | gyan.dev (estàtic) |
| appimagetool | **1.9.1** | GitHub (AppImage) |
| Icones Lucide | **1.56.0** | raw.githubusercontent |
| Vamp: nnls-chroma (Chordino) | compilat | codi font del projecte |
| Vamp: qm-vamp-plugins | compilat | commit `c918afc070f7…` |
| Vamp: qm-dsp | compilat | commit `e34a3cc18833…` |
| Vamp: vamp-plugin-sdk | compilat | commit `63e0c3b37b6f…` |
| Vamp: libsndfile | compilat | commit `b9103bd48b6c…` |
| Vamp host (`vamp_host_local`) | present | codi font del projecte |

> El venv de desenvolupament i l'entorn portable instal·len **exactament
> aquests pins** (`requirements.txt`); aquest document NO llegeix cap
> entorn local, perquè sigui reproduïble al CI.

## Versions fixades (`eines/deps_fixades.env`)

| Clau | Valor |
|---|---|
| `APPIMAGETOOL_VER` | `1.9.1` |
| `FFMPEG_LINUX_FILE` | `ffmpeg-${FFMPEG_LINUX_VER}-amd64-static.tar.xz` |
| `FFMPEG_LINUX_VER` | `7.0.2` |
| `FFMPEG_MAC_VER` | `9.0.2` |
| `FFMPEG_WIN_VER` | `9.0.2` |
| `LIBSNDFILE_COMMIT` | `b9103bd48b6c8fb517ae737fe3baee0c718b804c` |
| `LUCIDE_TAG` | `1.56.0` |
| `PYBS_FILE` | `cpython-${PYBS_PYV}+${PYBS_TAG}-x86_64-unknown-linux-gnu-install_only.tar.gz` |
| `PYBS_PYV` | `3.12.15` |
| `PYBS_TAG` | `20261003` |
| `QM_DSP_COMMIT` | `e34a3cc188332ed7c33cd9257ef164de5b587191` |
| `QM_VAMP_PLUGINS_COMMIT` | `c918afc070f79489758bb2dab6895972bd82066b` |
| `VAMP_PLUGIN_SDK_COMMIT` | `63e0c3b37b6fb9ce6f074ea8222b4903e4f5568a` |

> Els SHA256 de cada baixada són al mateix fitxer (`..._SHA256`) i es
> verifiquen a cada descàrrega; les URLs (`..._URL`) també hi són.

## Fitxers de plugins compilats al projecte

- `nnls-chroma-linux64-local/nnls-chroma.so`
- `qm-vamp-plugins-linux64-local/qm-vamp-plugins.so`

## Com s'actualitza

1. Canvia la versió a `eines/deps_fixades.env` (i, si cal, al script
   que la fa servir) o el pin a `requirements.txt`.
2. Calcula el SHA256 nou: `python3 eines/baixa_verificat.py "<URL>" - /tmp/x`.
3. Regenera aquest document: `python3 eines/genera_inventari.py` (i commiteja'l).
4. Comprova que el build segueix funcionant (i, a macOS, el mínim 10.13).

> Detall complet: `docs/SEGURETAT.md`.
