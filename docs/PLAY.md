# Reproducció (play) — arquitectura i coherència

> **2026-10-07 · v0.5.0.** Com sona l'àudio a l'app i per què està fet així.
> Codi: `app/visor.py` (`_engega_des_de`, `_alimenta`, `_atura_proc`,
> `_tiquet`, `play_stop`, `_mono_bytes`).

## Cadena

```
WAV (16 bits) ──_mono_bytes()──► mono 16 bits ──_alimenta()──► paplay --raw ──► PipeWire ──► altaveus
   (cacat)                        + GUANY en directe (vol/mute)      (grup propi, start_new_session)
```

| Peça | Què fa |
|------|--------|
| `_mono_bytes()` | converteix l'àudio a **mono 16 bits**, **cacat** (un sol cop per fitxer) |
| `_alimenta()` | fil que escriu el buffer al pipe de `paplay`, **aplicant-hi el guany** (vol/mute) tros a tros |
| `paplay` | reproductor **preferit** (libpulse→PipeWire/Pulse), `--raw --format=s16le --channels=1 --latency-msec=100` |
| `_tria_player()` | tria el reproductor **un sol cop** en obrir el visor: `paplay` si hi és; si no, `aplay` (ALSA directe); si no n'hi ha cap → `None` i l'app **avisa** (la resta funciona igual) |
| `_tiquet()` | QTimer **50 ms**: mou el cursor, fa el loop A/B i detecta el final/els errors |
| `_atura_proc()` | mata el **grup** del reproductor (`killpg`) i invalida el fil d'alimentació (`_sess`) |
| `play_stop()` | alterna play/atura; emet `playStateChanged(bool)` per a la icona ▶/⏸ |

## Decisions clau (i per què)

1. **El cursor va amb rellotge de paret** (`t0_pos + monotonic − t0_mono`), no
   amb la posició del reproductor (paplay no la reporta). Per això es baixa la
   **latència** (`--latency-msec=100`) perquè el cursor quadri amb el que se sent.
2. **Al final NO s'atura pel rellotge**: s'espera l'**EOF** de paplay (que va
   per darrere per la latència). Si s'aturés a `t >= durada`, es tallaria la cua.
   Xarxa de seguretat: si el rellotge se'n va >15 s, sí que s'atura (encallat).
3. **El guany (volum/mute) s'aplica EN VIU** al fil d'alimentació, no al buffer.
   Així canviar-lo **no reinicia** el reproductor ni fa cap punxada (s'aplica
   tan aviat com es buida el buffer del servidor).
4. **`_mono_bytes` és cacat**: convertir estereo→mono + copiar trigava **~450 ms**
   en temes llargs i es feia a cada play/seek/reinici (congelava la GUI). Ara
   un sol cop: **468 ms → 0,03 ms**.
5. **S'atura abans d'operacions pesades**: `_atura_si_sona()` s'invoca a
   `Analitza` (plugins), `🎯 Detecta`, `🧭 Compàs 1` i `_carrega_visor`
   (redibuix). No té sentit sonar mentre s'analitza o es redibuixa.
6. **Si el reproductor mor amb error** (codi ≠ 0) s'avisa al log; abans
   s'aturava en silenci.

## Estats / invariants

- `self.sona` ∈ {True, False} — només `play_stop()` el canvia.
- `self.proc` — el `Popen` viu (o `None`). `_atura_proc()` sempre el deixa a `None`.
- `self._sess` — comptador de sessió; el fil d'alimentació plega si canvia.
- `self.mut` / `self.vol` — el guany; els llegeix `_alimenta` a cada tros.
- Tornar a engegar (`_engega_des_de`) **sempre** crida `_atura_proc()` abans.

## Com provar-ho sense fer soroll

Amb un **null sink** de PipeWire:
```bash
MOD=$(pactl load-module module-null-sink sink_name=prova_ac)
PULSE_SINK=prova_ac .venv/bin/python el_teu_script.py
pactl unload-module $MOD
```
Verificat així: volum/mute **sense cap event stop/play**; STOP únic al final
(6,10 s per una wav de 6,00 s, cursor a 6,00 s → cua sencera).

## Pendent
- Mostrar un avís visible (no només log) si el reproductor mor per error.
- Valorar `pw-play` (PipeWire natiu) com a alternativa a `paplay`.
