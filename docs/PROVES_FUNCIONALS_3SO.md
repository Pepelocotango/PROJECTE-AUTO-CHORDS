# Proves funcionals dels 3 paquets (v0.5.2)

> Guia ràpida per validar els **3 artefactes del CI** als **3 sistemes**.
> Els ZIP descarregats són a **`00last_artifacts_githubactions/`** (i a
> *Actions ▸ run ▸ Artifacts* del repo). Els noms porten el número de build;
> agafa sempre el **més recent** de cada SO.
>
> **Objectiu**: comprovar que l'app **arrenca, analitza, edita i exporta** en un
> sistema real. És l'únic pendent que no es pot verificar des del CI.
>
> 💡 **Per generar els 3 paquets alhora**: llança el workflow **`build-all.yml`**
> (Actions ▸ «Compilar els 3 SO (Linux + Windows + macOS)» ▸ *Run workflow*) —
> executa els 3 builds **en paral·lel**.

## 🐧 Linux (AppImage) — es pot provar des d'aquest host

```bash
# al directori on hagis descomprimit el ZIP de Linux.
# L'AppImage de dins es diu auto-chords-<sane>-x86_64.AppImage
# (el ZIP es diu AutoChords_v<ver>-<sane>-build<N>-Linux.zip):
chmod +x auto-chords-*-x86_64.AppImage
./auto-chords-*-x86_64.AppImage
```

- **No cal instal·lar res** (runtime estàtic; tampoc `libfuse2`).
- L'estat (log, opcions) va a **`~/.local/state/auto-chords/`**.
- Si l'AppImage no arrenca: `--appimage-extract` i mira `AppRun` per veure l'error.

## 🪟 Windows 10 (ZIP portable x64)

1. Descomprimeix el ZIP en una carpeta (p. ex. `C:\AutoChords`).
2. Executa **`AutoChords.exe`**.
3. Si Windows SmartScreen avisa: *Més informació ▸ Executa igualment*.
4. L'estat va a **`%LOCALAPPDATA%\auto-chords\`** (o la carpeta de l'usuari).

## 🍎 macOS High Sierra 10.13 (ZIP amb `.app`)

1. Descomprimeix el ZIP → surt un **`AUTO_CHORDS.app`**.
2. **Clic dret ▸ Obre** (el Gatekeeper del sistema està OFF, però el primer cop
   cal confirmar-ho).
3. Si diu que l'app és *malmesa*, treu la marca de quarantena:
   ```bash
   xattr -dr com.apple.quarantine AUTO_CHORDS.app
   ```
4. L'estat (i el **log**) va a **`~/.local/state/auto-chords/`** (l'`auto_chords.log` és aquí; **no** pas a `~/Library/Application Support/…`).

## ✅ Checklist comuna (5 minuts)

- [ ] **Arrenca**: surt la finestra principal sense errors.
- [ ] **Obre un WAV** (`Fitxer ▸ Obre…`, `Ctrl+O`) i prem **`F5`** (Analitza).
- [ ] **Timeline**: arrossega un acord (ha de fer **snap** a la graella).
- [ ] **Multi-selecció**: `Ctrl+clic` afegeix un clip; `Shift+clic` fa el rang.
- [ ] **Duplicar el grup**: `Ctrl+D` amb 2+ clips seleccionats.
- [ ] **Copiar/enganxar**: `Ctrl+C`, mou el cursor, `Ctrl+V` (enganxa al cursor).
- [ ] **Moure el grup**: arrossega un clip seleccionat (es mou tota la selecció).
- [ ] **Indicador de mode**: el regle mostra `120 BPM · 4/4` o `Lliure`.
- [ ] **Desfer**: `Ctrl+Z` desfà l'última operació (de grup, d'una sola vegada).
- [ ] **Exporta** (`Ctrl+E`) → escolta el WAV resultant.
- [ ] **Partitura** (`Fitxer ▸ Exporta la partitura…`) — opcional; necessita
      **MuseScore 4.6.x** (el 4.7+ no va en aquest maquinari).
- [ ] **Tanca net**: no ha de quedar cap procés penjat.

## ⚠️ Què mirar si alguna cosa falla

| Símptoma | Què comprovar |
|---|---|
| No arrenca / error de llibreria | Que el ZIP sigui **sencer** (no només l'executable); mira el missatge exacte |
| «No troba el host/plugins Vamp» | El paquet ha d'incloure `vamp_host_local` i els `.dll`/`.dylib`; avisa amb el text de l'error |
| Analitza però no detecta res | Que el WAV no sigui buit ni massa curt; prova el mateix WAV al Linux (control) |
| L'exportació falla | Comprova que `ffmpeg` hi sigui al paquet; el log diu la comanda exacta |
| La partitura no surt | MuseScore 4.6.x instal·lat i detectat (`~/Applications` o `/Applications`) |

> **Com reportar-ho**: copia el **text del log** (el tauler de baix, *Visualitza ▸
> Mostra el log*) i el **SO + versió del paquet** (nom del ZIP). Amb això n'hi ha
> prou per reproduir-ho.
