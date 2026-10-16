# REFERÈNCIA — Piles tecnològiques i gràfiques de programes de referència
> Per a PROJECTE AUTO CHORDS — idea a l'hora de programar programes semblants
> Data: 2026-10-05 · Estat: referència viva

## 0. Per què aquest document
AUTO CHORDS ja funciona amb: Python 3.10+ (o el Python portable) + PyQt5 (amb QtSvg) + numpy<2 + Chordino + **plugins QM** via **host Vamp propi** (vegeu README.md).
Aquest document recull com ho fan REAPER, Audacity, MuseScore, Transcribe! i Sonic Visualiser,
amb èmfasi en la **pila gràfica/UI**, per decidir què copiar i què evitar.

## 1. Taula resum

| Programa | Llenguatge | Pila gràfica/UI | Àudio I/O | DSP/anàlisi | Build | Llicència |
|---|---|---|---|---|---|---|
| REAPER 7 (Cockos) | C/C++ | Win32 natiu + SWELL (WDL): GDK+Cairo a Linux, Cocoa a mac | motor propi 64-bit float | EEL2/JSFX, Lua, Python | make/MSVC | privat 60$ (WDL/SDK obert) |
| Audacity 4.0 (Muse Group) | C++ | Qt6+QML (abans wxWidgets fins 3.x) | PortAudio | Nyquist, VST3/LV2/AU, libsndfile, FFmpeg extern | CMake | GPLv3 |
| MuseScore Studio 4 (Muse Group) | C++ | Qt Widgets + QML | MuseSampler/MuseSounds + VST3 | engraving SMuFL propi | CMake+Ninja, submòduls muse_framework/muse_deps | GPLv3 + font exception |
| Transcribe! 9.6 (Seventh String, 1 dev) | C++ | wxWidgets a tot arreu des v7 (abans MFC a Win, PowerPlant/CodeWarrior a Mac) | GStreamer-1.0 + GTK-3 a Linux, CoreAudio/WASAPI | DSP propi temps real (half-speed, pitch, EQ 31 bandes) | make/MSVC | comercial tancat |
| Sonic Visualiser 5 (QMUL) | C++/SML | Qt6 (Qt5 fins v4) | PortAudio + JACK + Pulse + ALSA | Vamp SDK + Rubber Band + FFTW3/vDSP + LADSPA | Meson+Ninja | GPL-2.0 |

## 2. Fitxes

### 2.1 REAPER — lleuger perquè pinta gairebé directe
- Nucli C/C++ tancat, ~15 MB. API oberta: `reaper-sdk` + `WDL`.
- SWELL = capa fina que tradueix Win32 → GDK/Cairo (Linux) / Cocoa (mac). No Qt, no wx.
- Script: ReaScript EEL2 (propi, també JSFX/vídeo) + Lua encastat + Python extern.
- Lliçó AUTO CHORDS: una sola base + capa fina = 3 SO amb 2 devs. Nosaltres ja ho tenim amb Qt: no cal SWELL.

### 2.2 Audacity — de wxWidgets a Qt
- Fins 3.x: wxWidgets + PortAudio + libsndfile + SQLite (.aup3 en un sol fitxer).
- 4.0 (set-2026): UI reconstruïda amb Qt6+QML reutilitzant `muse_framework` de MuseScore. Nou `.aup4`.
- Arquitectura per capes: BlockFile sobre wxFiles; PortAudio amb codi condicional per SO.
- Lliçó: wxWidgets va bé per durar 20 anys, però Qt/QML dona workspaces i clip-tools moderns. AUTO CHORDS ja és a Qt: bon camí.

### 2.3 MuseScore — notació WYSIWYG amb Qt
- Fork de MusE (2002). C++ + Qt + QML, CMake.
- Natiu `.mscx` (XML) / `.mscz` (zip); MusicXML 4.0, MIDI, MEI, Guitar Pro.
- Fonts pròpies Leland/Edwin (SMuFL). Playback: abans FluidSynth/SoundFont, ara MuseSounds + VST3 (Linux VST3 des 4.6).
- Comparteix `muse_framework` amb Audacity 4.
- Lliçó: separar engraving (PDF/SVG/PNG) de playback. Per AUTO CHORDS: separar vista ona/acords de pipeline/export, com ja fa `app/visor.py` vs `app/pipeline.py`.

### 2.4 Transcribe! — el mirall més proper a AUTO CHORDS
- Player especialitzat per transcriure (no editor): waveform + markers + loops + half-speed instantani sense preprocés.
- Història clau: doble codi MFC/PowerPlant fins v6 → reescriptura v7.0 (2004) en C++ + wxWidgets amb un sol source Win/Mac/Linux.
- Linux actual: 64-bit, GStreamer-1.0 + GTK-3. Eviteu Flatpak (l'autor diu que no va bé).
- Lliçó directa: el flux `Processa → revisa/edita → Finalitza` d'AUTO CHORDS és el mateix patró que Transcribe! (Fx + loops + annotacions). Mantenir temps real on-the-fly.

### 2.5 Sonic Visualiser — el patró acadèmic obert (i el nostre proveïdor via Vamp)
- C++ + Qt6, Meson+Ninja. Deps al `meson.build`: libsndfile, libsamplerate, Rubber Band, FFTW3, bqfft/bqresample/bqaudioio, Sord/Serd (RDF), Cap'n Proto + Piper, liblo (OSC), mad, oggz/fishsound, Opus.
- I/O: PortAudio + JACK + Pulse + ALSA a Linux, CoreAudio a mac.
- Plugins: **Vamp** per acords/beat/estructura (Chordino + Queen Mary). AUTO CHORDS els fa servir via el **seu propi host** (`vamp_host_local`), no via Sonic Annotator.
- Lliçó: si cal DSP nou, fer-ho com a plugin Vamp (C++) i cridar-lo des de Python, no reescriure Chordino.

## 3. Piles gràfiques comparades (el que demana el títol)

- Qt Widgets + QML (Audacity 4, MuseScore, Sonic): multiplataforma real, acceleració GPU, temes, QML per panells moderns. Cost: pes + dependències Qt6.
- wxWidgets (Audacity 3, Transcribe!): natiu per SO, lleuger, ideal 1 dev. Menys vistós que QML.
- Win32 + SWELL/GDK/Cairo (REAPER): mínim i rapidíssim, però has de mantenir la capa tu.
- Python PyQt5 + QtSvg (AUTO CHORDS actual): ràpid, ona/cursor/navegació sense C++. Prou per Q9400 sense AVX (tkinter/Qt per defecte a MATE sense composite).
- Regla Q9400: verificar `grep -o avx /proc/cpuinfo` (buit = sense AVX) abans d'instal·lar binaris moderns; preferir Python/Node, Qt5, builds SSE4.1.

## 4. Què copiar per AUTO CHORDS
1. Mantenir Python + PyQt5 per visor; C++ només via l'host Vamp propi i els plugins.
2. Patró Transcribe!: efectes en temps real sense preprocés, drecera de teclat configurable, foot-pedal/script.
3. Patró Sonic: tot DSP nou com a Vamp + `sonic-annotator` local (ja al repo), no dins `app/`.
4. Patró Audacity/MuseScore: un sol framework UI (`app/theme.py` ja centralitza) + SQLite si cal projecte en un sol fitxer més endavant.
5. No copiar: Flatpak Transcribe!, ALSA `hw:` directe tipus REAPER en gravació, ni dependències AVX2.

## 5. Fonts
- github.com/audacity/audacity, github.com/musescore/MuseScore, github.com/sonic-visualiser/sonic-visualiser (README, meson.build, COMPILE_linux.md)
- seventhstring.com/xscribe/history.html, cockos.com/wdl + EEL2, reaper-sdk / reascripthelp.html
- Viquipèdies Audacity/MuseScore (canvi wx→Qt6 documentat 2024-2026)

*Document viu: actualitzeu-lo quan canvieu `app/visor.py`, `app/pipeline.py` o versions Vamp.*
