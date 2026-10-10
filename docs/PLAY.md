# Reproducció (play) — arquitectura i coherència

> **2026-10-10 · v0.6.0.** Com sona l'àudio a l'app i per què està fet així.
> Codi: `app/audio_out.py` (motors) i `app/visor.py` (`_engega_des_de`,
> `_alimenta`, `_atura_proc`, `_tiquet`, `play_stop`, `_mono_bytes`).

## Cadena

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

## Decisions clau (i per què)

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
   sola API** per a CoreAudio/WASAPI/ASIO. Vegeu `docs/MOTOR_AUDIO_SO.md`.

## Estats / invariants

- `self.sona` ∈ {True, False} — només `play_stop()` el canvia.
- `self.proc` — el **motor** viu (o `None`). `_atura_proc()` sempre el deixa a `None`.
- `self._sess` — comptador de sessió; el fil d'alimentació plega si canvia.
- `self.mut` / `self.vol` — el guany; els llegeix `_alimenta` a cada tros.
- Tornar a engegar (`_engega_des_de`) **sempre** crida `_atura_proc()` abans.

## Com provar-ho sense fer soroll (Linux)

Amb un **null sink** de PipeWire:
```bash
MOD=$(pactl load-module module-null-sink sink_name=prova_ac)
PULSE_SINK=prova_ac .venv/bin/python el_teu_script.py
pactl unload-module $MOD
```
Verificat així: volum/mute **sense cap event stop/play**; STOP únic al final
(6,10 s per una wav de 6,00 s, cursor a 6,00 s → cua sencera).

## Pendent
- Mostrar un avís visible (no només log) si el motor mor per error.
- Valorar `pw-play` (PipeWire natiu) com a alternativa a `paplay` a Linux.
