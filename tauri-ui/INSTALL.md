# Guia d'instal·lació i validació al Q9400 (Tauri 2)

Aquesta guia és per **verificar que Tauri 1.6 funciona correctament al
Q9400** (CPU sense AVX2). Si tot va bé, podem procedir amb el projecte.

## 0. Verificar el Q9400

El **Q9400 NO té AVX2**, però això **NO és un problema** per a Tauri 2.

- ✅ Tauri 2 usa **WebKitGTK natiu** (no Chromium embebut), que es compila
  amb el conjunt base x86-64 — sense instruccions il·legals al Q9400.
- ❌ El que cal evitar a Rust: `-C target-cpu=native` (activaria AVX2/AVX-512
  si la CPU els té). No cal amb target-cpu=generic o el default.
- 📚 L'apartat sobre AVX2 parlava de WebView2 de **Windows** (no et toca).

La verificació clàssica (per curiositat):

```bash
grep -o avx2 /proc/cpuinfo
```

- Si **no surt res** → perfecte, el Q9400 és el que esperem.
- Si surt "avx2" → la teva CPU sí que té AVX2, aleshores Tauri 2.x també
  funcionaria. Però Tauri 1.6 igualment funcionarà (i és més lleuger).

També comprova que tens SSE4.1 (necessari per a Tauri):

```bash
grep -o sse4_1 /proc/cpuinfo
```

Ha de sortir "sse4_1".

## 1. Prerequisits

### Per què Tauri 2 a Ubuntu 24.04 (i no 1.6)

A Ubuntu 24.04 **ja no existeix** `libwebkit2gtk-4.0-dev` (només hi ha la 4.1
i la 6.0). Tauri 1.x **exigeix** la 4.0, per tant no es pot compilar aquí.

Tauri 2.x funciona amb **WebKitGTK 4.1** i **libsoup-3.0** — disponibles als
repos oficials. **A Linux, Tauri 2 NO usa AVX2** (perquè la WebView és
nativa del sistema, no Chromium embebut). Per tant: **Tauri 2 és la tria
correcta per al Q9400**.

### Linux (Ubuntu 24.04 — la nostra configuració)

```bash
# 1. Rust toolchain (estable)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -t stable
source "$HOME/.cargo/env"

# 2. Deps de sistema per a WebKitGTK (Tauri 1.x a Linux usa WebKit)
sudo apt-get update
sudo apt-get install -y libwebkit2gtk-4.0-dev build-essential curl wget file \
    libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev

# 3. Node.js 18+ + pnpm
# (si ja tens GEP, segur que ja ho tens)
node --version    # >= 18
pnpm --version    # qualsevol recent

# 4. Python 3 amb el wav_a_wavs.py executable
python3 --version  # >= 3.10
# Assegurar que el wav_a_wavs.py del projecte pare funciona:
cd ..
python3 wav_a_wavs.py --help    # hauria de funcionar

# 5. Binaris del projecte (ja existeixen)
ls sonic-annotator
ls nnls-chroma-linux64-local/nnls-chroma.so
ls segmentino-linux64-local/segmentino.so
```

## 2. Pantalla en blanc? Problema gràfic al Q9400 (i molts altres)

El Q9400 porta una **GT 730 Kepler (GK208B)** amb driver NVIDIA 470 (l'últim
compatible amb Kepler). WebKitGTK 2.44 (el de Ubuntu 24.04) + driver
propietari NVIDIA és la combinació clàssica de **finestra en blanc** a Tauri 2.

Si l'app s'obre però no mostra res, és gairebé segur aquest problema. Solució:
desactivar el renderitzat accelerat per DMA-BUF/EGL.

### Solucions (provar en ordre)

```bash
# 1. La més comuna per a NVIDIA + WebKitGTK 2.44
WEBKIT_DISABLE_DMABUF_RENDERER=1 pnpm tauri dev

# 2. Si no funciona, també compositing
WEBKIT_DISABLE_COMPOSITING_MODE=1 WEBKIT_DISABLE_DMABUF_RENDERER=1 pnpm tauri dev

# 3. Últim recurs: OpenGL per programari
LIBGL_ALWAYS_SOFTWARE=1 WEBKIT_DISABLE_COMPOSITING_MODE=1 WEBKIT_DISABLE_DMABUF_RENDERER=1 pnpm tauri dev
```

### Solució permanent

Quan trobis la combinació que funciona, pots fer-la permanent afegint
aquestes variables al principi de `run()` a `src-tauri/src/lib.rs`:

```rust
#[cfg(target_os = "linux")]
{
    std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
    std::env::set_var("WEBKIT_DISABLE_COMPOSITING_MODE", "1");
}
```

Això ja està implementat al projecte per defecte — pots comentar-ho si
el teu sistema sí que funciona correctament amb acceleració.

### Comprovacions útils

```bash
# Quina gràfica/driver tens?
glxinfo -B | head -20
lspci -k | grep -A3 -i vga

# Si Vite respon amb tauri dev en marxa:
curl -I http://127.0.0.1:1420

# Si la finestra continua en blanc, click dret → Inspect Element → Console
# i reporta els errors
```



```bash
cd tauri-ui
pnpm install                    # ~30-60s la primera vegada

# Test de build (pot trigar 5-15 min la primera vegada per
# la compilació de totes les deps de Rust):
pnpm tauri build
```

Si la build falla amb errors d'`instréus llegals` o `SIGILL`, **atura't
i reporta**. Vol dir que la toolchain Rust ha generat codi AVX2 i cal
ajustar-la:

```bash
# Verificar que la toolchain actual NO usa AVX2
rustc --print cfg | grep target_feature

# Si veus "target_feature=avx2", cal canviar toolchain:
rustup default stable
# I tornar a compilar:
cargo clean
pnpm tauri build
```

## 3. Provar l'AppImage

```bash
# L'AppImage generat hauria d'estar a:
ls src-tauri/target/release/bundle/appimage/

# Executar-la:
./src-tauri/target/release/bundle/appimage/Auto\ Chords_0.1.0_amd64.AppImage
```

Si arrenca → **Tauri 1.6 + Q9400 és viable**. Procedim amb els següents
sprints.

Si peta amb "illegal instruction" o "SIGILL" → **Tauri 1.6 no és viable**.
Possibles workarounds:
- Usar Rust amb `-C target-feature=-avx2` (forçar sense AVX2)
- Recórrer a PyQt5 (la versió existent del projecte)

## 4. Mode desenvolupament

Si la build ha funcionat, pots provar el dev server:

```bash
pnpm tauri dev
```

Això inicia:
1. Vite dev server a `http://localhost:1420` (només per Tauri)
2. Compilació del backend Rust (1-2 min la primera vegada)
3. Obrir una finestra nativa amb la UI

Per provar:
1. Click "Tria WAV…" → file dialog natiu
2. Selecciona una WAV
3. Click "Detecta" → invoca `python3 wav_a_wavs.py` i mostra la sortida

Si la sortida mostra informació de detecció d'acords → **tot funciona**.

## 5. Troubleshooting

### "illegal hardware instruction"
La build o l'execució ha usat AVX2. Cal:
- Verificar que Rust toolchain és estable (no nightly amb optimitzacions)
- Afegir `.cargo/config.toml` amb:
  ```toml
  [target.x86_64-unknown-linux-gnu]
  rustflags = ["-C", "target-feature=-avx2"]
  ```

### "WebKit2GTK not found"
Instal·lar:
```bash
sudo apt-get install libwebkit2gtk-4.0-dev
```

### "Permission denied" en obrir la WAV
Tauri té una llista d'allowlist (whitelist) per a fitxers. Si tens
problemes, comprova `src-tauri/tauri.conf.json`:
```json
"allowlist": {
  "dialog": { "open": true },
  "shell": { "execute": true }
}
```

### Python "No such file or directory"
Si `wav_a_wavs.py` no es troba, comprova:
- Has executat la build des de `tauri-ui/` (no des de la directrie arrel)
- O defineix `AUTO_CHORDS_ROOT=/path/to/PROJECTE AUTO CHORDS` abans d'executar

## 6. Verificació final

Quan **tot funcioni**, ja podem procedir amb els següents sprints:

1. ✅ Tauri 1.6 compila al Q9400
2. ✅ L'AppImage resultant s'executa
3. ✅ File dialog funciona
4. ✅ Python subprocess s'invoca correctament
5. ⚠️ *(pendent)* Sprint 2: integrar wavesurfer.js i les 2 lanes

Aleshores podem començar a **replicar** el visor actual en React/TS.