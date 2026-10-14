# Motor d'àudio per SO — què fem servir i què fan els programes «pro»

> **2026-10-14 · v0.7.0.** Respon a: «estem fent servir els motors d'àudio adequats a cada
> SO com ho fan DAWs, VLC…?». Complementa `app/audio_out.py` i `app/plataforma.py`.

## Resum

| SO | Què fem servir | API nativa de sota | Què fan DAWs / VLC |
|----|----------------|--------------------|--------------------|
| **macOS** | `sounddevice` (PortAudio), dins el procés | **CoreAudio** | CoreAudio (tothom; és l'única via) |
| **Windows** | `sounddevice` (PortAudio), **WASAPI primer** | **WASAPI** (compartit) | WASAPI (VLC/foobar); ASIO o WASAPI-exclusiu als DAWs |
| **Linux** | `paplay` / `aplay` (procés extern) | PulseAudio/PipeWire / ALSA | JACK/PipeWire-JACK (DAWs); Pulse/ALSA (la resta) |

## macOS
- L'única API «de debò» és **CoreAudio** (AudioToolbox/AVFoundation). `afplay` n'és un simple embolcall.
- PortAudio (`sounddevice`) **fa servir CoreAudio** → és correcte i és el que fan Ableton, Logic, Reaper, VLC…
- No cal res especial (ni ASIO ni exclusiu: CoreAudio ja és de baixa latència).
- **v0.6.1:** `MotorStream` utilitza teardown **idempotent i serialitzat** (`_tancat` + `threading.Lock`) per evitar crashes (`EXC_BAD_ACCESS` a CoreAudio) quan es tanca l'stream de PortAudio des de diferents fils.

## Windows — ordre de qualitat/latència (PortAudio exposoa les mateixes APIs)
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

## Linux
- **No es toca**: es manté `paplay` (Pulse) / `aplay` (ALSA), que ja funciona.
- Els DAWs a Linux fan **JACK / PipeWire-JACK** (PortAudio també ho pot fer servir), però no és el nostre cas.

## Conclusió
- **macOS**: CoreAudio via PortAudio → ✅ correcte i estàndard.
- **Windows**: WASAPI compartit via PortAudio (fallback MME/DirectSound) → ✅ alineat amb VLC/foobar; **ASIO** quedaria com a possible opció avançada.
- **Linux**: intacte ✅.

> Nota tècnica: PortAudio és **exactament** la capa que fa servir molta programari
> per parlar amb aquestes APIs. No inventem res: triem, per a cada SO, el mateix
> host API que els programes madurs.
