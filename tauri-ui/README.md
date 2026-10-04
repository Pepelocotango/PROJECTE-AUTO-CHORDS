# Auto Chords — UI Tauri (versió multiplataforma)

Aquest és el **frontend Tauri** del projecte `PROJECTE AUTO CHORDS`.
Proveeix una interfície amigable i multiplataforma que envolta el
backend Python (detecció amb Chordino + Segmentino).

**Què és Tauri?** Un framework per a aplicacions d'escriptori que
combina un WebView natiu del sistema (no Chromium embebuit) amb un
backend en Rust. Resultat: aplicacions petites (10-30 MB) que veuen i
se senten natives a cada sistema operatiu.

**Per què Tauri 1.6?** Perquè **no usa AVX2** — per tant funciona
correctament al nostre Q9400 i altres CPU antigues. (Tauri 2.x usa
WebView2 a Windows que pot incloure optimitzacions AVX2.)

## Stack

| Component | Tecnologia | Per què |
|---|---|---|
| Shell desktop | **Tauri 1.6.3** | Lleuger (10-30 MB), sense AVX2, multi-OS |
| Backend | **Rust** (Tauri) | Crida el Python via `std::process::Command` |
| Frontend | **React 18** + **TypeScript 5** | Ecosistema madur, transferible des de GEP |
| Build tool | **Vite 5** | Dev server ràpid, HMR, build optimitzat |
| Gestor paquets | **pnpm** | Consistente amb la resta de projectes |
| Backend análisis | **Python 3** (`wav_a_wavs.py`) | Pipeline existent (Chordino + Segmentino) |

## Estructura

```
tauri-ui/
├── README.md             ← aquest fitxer
├── INSTALL.md            ← instal·lació i validació al Q9400
├── package.json          ← deps npm + scripts
├── tsconfig.json         ← config TypeScript (renderer)
├── tsconfig.node.json    ← config TypeScript (build/vite)
├── vite.config.ts        ← config Vite (port 1420, HMR)
├── index.html            ← entry HTML
├── src/                  ← frontend (renderer process)
│   ├── main.tsx          ← entry React
│   ├── App.tsx           ← component principal (Hello World)
│   ├── styles.css        ← tema fosc minimalista
│   └── lib/
│       └── api.ts        ← wrapper sobre Tauri commands
└── src-tauri/            ← backend (main process, Rust)
    ├── Cargo.toml        ← deps Rust + Tauri
    ├── tauri.conf.json   ← config Tauri (allowlist, bundle, etc.)
    ├── build.rs          ← build script (tauri-build)
    └── src/
        └── main.rs       ← entry Rust: Tauri commands + GUI lifecycle
```

## Setup ràpid (al PC de l'operador)

```bash
cd tauri-ui

# 1. Assegurar deps sistema (Linux/Ubuntu):
#    - rustup amb toolchain estable
#    - libwebkit2gtk-4.0-dev (Tauri 1.x usa WebKitGTK)
#    - pnpm + node 18+
#    - python3 amb wav_a_wavs.py executable
#    - Binaris: sonic-annotator, nnls-chroma.so, segmentino.so
#    (veure INSTALL.md per detalls)

# 2. Instal·lar deps JavaScript:
pnpm install

# 3. Desenvolupament (dev server + Rust):
pnpm tauri dev
# → S'obre una finestra amb la UI Hello World

# 4. Build per a distribució (AppImage):
pnpm tauri build
# → Genera:
#    src-tauri/target/release/bundle/appimage/Auto Chords_0.1.0_amd64.AppImage
#    src-tauri/target/release/bundle/deb/Auto Chords_0.1.0_amd64.deb
```

## Flux previst (futurs sprints)

Aquest és el **Hello World**: permet validar que Tauri 1.6 funciona
al Q9400. Les funcionalitats completes s'afegiran per sprints:

- **Sprint 1** *(actual)*: Hello World + integració Python (Hola món funcional).
- **Sprint 2**: Visor amb **wavesurfer.js** — ona + 2 lanes (acords + estructura).
- **Sprint 3**: Interacció DAW-like (drag/resize/snap/constraint propagation).
- **Sprint 4**: Selecció persistent, duplicar, eliminar, Undo/Redo.
- **Sprint 5**: Dreceres de teclat, multi-selecció, polish final.
- **Sprint 6**: Empaquetat final + AppImage verificat.

## Integració amb el projecte pare

L'app **reutilitza 100%** del backend Python existent:

- `app/pipeline.py` — detecció d'acords i estructura
- `wav_a_wavs.py` — entry point CLI (cridat des de `src-tauri/src/main.rs`)
- `sonic-annotator` + plugins — binaris d'anàlisi Vamp
- `app/visor.py` — la lògica de validació temporal (reaprofitada en JS)

**Res no es reescriu**: el pipeline Python continua sent l'única font de
veritat per a la detecció.

## Diferència amb la versió PyQt5 actual

Aquesta és una **alternativa** a `app/visor.py` + `app/timeline.py`. La intenció
és comparar-les i decidir quina oferir millor experiència d'usuari:

- **PyQt5** (existent): natiu Qt, validat al Q9400, però menys "amigable"
- **Tauri + React** (aquest): Web modern, animacions suaus, multi-OS, però
  cal validar al Q9400

Quan el Sprint 6 estigui llest, decidim quina mantenir (o si
coexisteixen).

## Llicència

GPLv3 — consistent amb el projecte pare.