# Àudio — reproducció (play) i motors per SO

> **2026-10-16 · v0.7.0** *(fusió de `PLAY.md` + `MOTOR_AUDIO_SO.md`).* Com sona
> l'àudio a l'app, per què està fet així i quin **motor** fa servir a cada SO.
> Codi: `app/audio_out.py` (motors) i `app/visor.py` (`_engega_des_de`,
> `_alimenta`, `_atura_proc`, `_tiquet`, `play_stop`, `_mono_bytes`).

## 1. Cadena

```
WAV (16 bits) ──_mono_bytes()──► mono 16 bits ──_alimenta()──► MOTOR ──► altaveus
   (cacat)                        + GUANY en directe (vol/mute)
```

El **MOTOR** el tria `app/audio_out.py` segons el SO (`plataforma.usa_audio_natiu`):

```
Linux   ─► MotorProc    ─► paplay --raw / aplay    ─► PipeWire/ALSA
mac/win ─► MotorStream  ─► PortAudio (sounddevice) ─► CoreAudio / WASAPI
```

| Peça | Què fa |
|------|--------|
| `_mono_bytes()` | converteix l'àudio a **mono 16 bits**, **cacat** (un sol cop per fitxer) |
| `_alimenta()` | fil que escriu el buffer al motor, **aplicant-hi el guany** (vol/mute) tros a tros |
| `MotorProc` | **Linux**: procés extern `paplay` (libpulse→PipeWire/Pulse) o, si no hi és, `aplay` (ALSA). `--raw --format=s16le --channels=1 --latency-msec=100` |
| `MotorStream` | **macOS/Windows**: reproducció **nativa dins el procés** amb **PortAudio** (`sounddevice`) → **CoreAudio** i **WASAPI** (fallback DirectSound→MME→WDM-KS). `close()` drena; `atura()` talla ja |
| `_tria_player()` | tria el motor **un sol cop** en obrir el visor: a mac/win, natiu; a Linux, `paplay`/`aplay`; si no n'hi ha cap → `None` i l'app **avisa** (la resta funciona igual) |
| `_tiquet()` | QTimer **50 ms**: mou el cursor, fa el loop A/B i detecta el final/els errors |
| `_atura_proc()` | atura el motor (`motor.atura()`) i invalida el fil d'alimentació (`_sess`) |
| `play_stop()` | alterna play/atura; emet `playStateChanged(bool)` per a la icona ▶/⏸ |

## 2. Decisions clau (i per què)

1. **El cursor va amb rellotge de paret** (`t0_pos + monotonic − t0_mono`), no
   amb la posició del motor (que no la reporta). Per això es baixa la
   **latència** a Linux (`--latency-msec=100`) perquè el cursor quadri amb el so.
2. **Al final NO s'atura pel rellotge**: s'espera que el motor acabi de buidar el
   buffer (l'EOF del procés, o `poll()==0` quan el stream ha drenat). Si s'aturés
   a `t >= durada`, es tallaria la cua. Xarxa de seguretat: si el rellotge se'n va
   >15 s, sí que s'atura (encallat).
3. **El guany (volum/mute) s'aplica EN VIU** al fil d'alimentació, no al buffer.
   Així canviar-lo **no reinicia** el motor ni fa cap punxada.
4. **`_mono_bytes` és cacat**: convertir estereo→mono + copiar trigava **~450 ms**
   en temes llargs i es feia a cada play/seek/reinici (congelava la GUI). Ara
   un sol cop: **468 ms → 0,03 ms**.
5. **S'atura abans d'operacions pesades**: `_atura_si_sona()` s'invoca a
   `Analitza` (plugins), `🎯 Detecta`, `🧭 Compàs 1` i `_carrega_visor`
   (redibuix). No té sentit sonar mentre s'analitza o es redibuixa.
6. **Si el motor mor amb error** (codi ≠ 0) s'avisa al log; abans
   s'aturava en silenci.
7. **Per què PortAudio i no un binari**: `afplay` (macOS) llegeix fitxers, no
   `stdin`; i `ffplay` s'hauria d'empaquetar a cada build. PortAudio és **una
   sola API** per a CoreAudio/WASAPI/ASIO.

## 3. Motors per SO (què fem servir i què fan els programes «pro»)

| SO | Què fem servir | API nativa de sota | Què fan DAWs / VLC |
|----|----------------|--------------------|--------------------|
| **macOS** | `sounddevice` (PortAudio), dins el procés | **CoreAudio** | CoreAudio (tothom; és l'única via) |
| **Windows** | `sounddevice` (PortAudio), **WASAPI primer** | **WASAPI** (compartit) | WASAPI (VLC/foobar); ASIO o WASAPI-exclusiu als DAWs |
| **Linux** | `paplay` / `aplay` (procés extern) | PulseAudio/PipeWire / ALSA | JACK/PipeWire-JACK (DAWs); Pulse/ALSA (la resta) |

### macOS
- L'única API «de debò» és **CoreAudio** (AudioToolbox/AVFoundation). `afplay` n'és un simple embolcall.
- PortAudio (`sounddevice`) **fa servir CoreAudio** → és correcte i és el que fan Ableton, Logic, Reaper, VLC…
- No cal res especial (ni ASIO ni exclusiu: CoreAudio ja és de baixa latència).
- **v0.6.1:** `MotorStream` utilitza teardown **idempotent i serialitzat** (`_tancat` + `threading.Lock`) per evitar crashes (`EXC_BAD_ACCESS` a CoreAudio) quan es tanca l'stream de PortAudio des de diferents fils.

### Windows — ordre de qualitat/latència (PortAudio exposa les mateixes APIs)
| API | Latència | Qui la fa servir |
|---|---|---|
| **ASIO** | molt baixa | DAWs amb interfaç «pro» (driver propi) |
| **WASAPI exclusiu** | baixa | DAWs «in the box» |
| **WASAPI compartit** | mitjana | **VLC, foobar2000, navegadors, jocs → el nostre cas** |
| DirectSound | mitjana | llegat (pre-Vista) |
| **MME** | alta | **màxima compatibilitat**, llegat |
| WDM-KS | molt baixa | rar (accés directe al nucli) |
- Triem **WASAPI compartit primer**, amb fallback **DirectSound → MME → WDM-KS** i, si no, el dispositiu per defecte. **Alineat amb VLC/foobar2000**.
- **No** auto-triem ASIO (necessita el driver del dispositiu i accés **exclusiu** → no coexisteix amb altres apps). Es podria oferir com a opció avançada per a interfaços pro.

### Linux
- **No es toca**: es manté `paplay` (Pulse) / `aplay` (ALSA), que ja funciona.
- Els DAWs a Linux fan **JACK / PipeWire-JACK** (PortAudio també ho pot fer servir), però no és el nostre cas.

## 4. Estats / invariants

- `self.sona` ∈ {True, False} — només `play_stop()` el canvia.
- `self.proc` — el **motor** viu (o `None`). `_atura_proc()` sempre el deixa a `None`.
- `self._sess` — comptador de sessió; el fil d'alimentació plega si canvia.
- `self.mut` / `self.vol` — el guany; els llegeix `_alimenta` a cada tros.
- Tornar a engegar (`_engega_des_de`) **sempre** crida `_atura_proc()` abans.

## 5. Com provar-ho sense fer soroll (Linux)

Amb un **null sink** de PipeWire:
```bash
MOD=$(pactl load-module module-null-sink sink_name=prova_ac)
PULSE_SINK=prova_ac .venv/bin/python el_teu_script.py
pactl unload-module $MOD
```
Verificat així: volum/mute **sense cap event stop/play**; STOP únic al final
(6,10 s per una wav de 6,00 s, cursor a 6,00 s → cua sencera).

## 6. Pendent

- Valorar `pw-play` (PipeWire natiu) com a alternativa a `paplay` a Linux.
- **ASIO** a Windows com a possible opció avançada per a interfícies «pro».

> ✅ **FET (2026-10-13, `aac8b26`)**: l'**avís és VISIBLE** (no només al log) quan
> el motor d'àudio mor per error — un sol cop per reproducció (`_avis_audio_fet`).

> 💡 **Resum**: **macOS** → CoreAudio (via PortAudio) ✅ · **Windows** → WASAPI
> compartit (via PortAudio, fallback MME/DirectSound) ✅ · **Linux** → intacte ✅.
> PortAudio és **exactament** la capa que fa servir molt programari madur; no
> inventem res: triem, per a cada SO, el mateix host API que els referents.
