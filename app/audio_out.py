"""Sortida d'àudio: motors de reproducció (un per SO, mateixa interfície).

L'app reprodueix àudio enviant **PCM mono 16 bits** a un «motor». N'hi ha dos:

- **`MotorProc`** (**Linux**): un procés extern (`paplay`/`aplay`) que rep el
  PCM per `stdin`. És exactament el que funcionava i **no es toca**.
- **`MotorStream`** (**macOS/Windows**): reproducció **nativa dins el procés**
  amb **PortAudio** (`sounddevice`) → **CoreAudio** a macOS i **MME** (el
  back-end més compatible) a Windows, amb fallback a DirectSound → WASAPI →
  WDM-KS. No cal cap procés extern (`ffplay`/`afplay`).

Tots dos exposen la **mateixa interfície mínima** que el visor ja feia servir
sobre el `subprocess.Popen`:

    motor.stdin.write(bytes)   # escriu PCM (bloqueja al ritme del so)
    motor.stdin.close()        # tanca; en natiu drena el buffer pendent
    motor.poll()               # None = sonant; 0 = acabat; !=0 = error
    motor.returncode           # codi de sortida (None si encara sona)
    motor.pid                  # pid del procés extern (None en natiu)
    motor.atura()              # atura JA (stop/seek/tancament)

Gràcies a això, el fil d'alimentació del visor (`_alimenta`) no canvia: només
escriu trossos de PCM, i el motor els reprodueix.
"""
import subprocess

import numpy as np

from app import plataforma

# Nom del «player» que indica el motor natiu (sounddevice).
NOM_NATIU = "sounddevice"


def crea_motor(player, args, sr, ferr):
    """Crea el motor adient per al `player` triat (vegeu `visor._tria_player`)."""
    if player == NOM_NATIU:
        return MotorStream(sr)
    return MotorProc(player, args, ferr)


class MotorProc:
    """Reproductor extern (Linux: `paplay`/`aplay`) que rep PCM per `stdin`."""

    def __init__(self, player, args, ferr):
        self.player = player
        # start_new_session: el player queda en grup propi → el podem matar
        # sencer (ell + fills) encara que la finestra mori.
        self.proc = subprocess.Popen(
            [player, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=ferr,
            **plataforma.kwargs_nou_grup())

    @property
    def stdin(self):
        return self.proc.stdin

    def poll(self):
        return self.proc.poll()

    @property
    def returncode(self):
        return self.proc.returncode

    @property
    def pid(self):
        return self.proc.pid

    def atura(self):
        proc = self.proc
        plataforma.mata_grup(proc)                  # SIGTERM (o terminate a Windows)
        try:
            proc.wait(timeout=2)
        except (subprocess.TimeoutExpired, OSError):
            plataforma.mata_grup(proc, forcat=True)  # SIGKILL
        try:
            proc.wait(timeout=1)
        except (subprocess.TimeoutExpired, OSError):
            pass


class MotorStream:
    """Reproducció nativa (mac/win) amb PortAudio (`sounddevice`).

    `close()` **drena** el buffer pendent (l'usuari sent la cua fins al final);
    `atura()` el talla immediatament.
    """

    def __init__(self, sr):
        import sounddevice as sd      # import tardà: només a mac/win

        self._sd = sd
        self.sr = int(sr)
        self._fi = False
        self._err = False
        self._rc = None
        self.stream = None
        self._device = None
        # Prova els host APIs en ordre de preferència fins que un obri.
        ultim = None
        for dev in _dispositius_candidats(sd):
            try:
                self.stream = sd.OutputStream(
                    samplerate=self.sr, channels=1, dtype="int16",
                    device=dev, latency="high")
                self.stream.start()
                self._device = dev
                return
            except Exception as e:  # noqa: BLE001
                ultim = e
                try:
                    if self.stream is not None:
                        self.stream.close()
                except Exception:  # noqa: BLE001
                    pass
                self.stream = None
        self._err = True
        self._rc = 1
        raise RuntimeError(f"no s'ha pogut obrir cap sortida d'àudio: {ultim}")

    # --- interfície compatible amb el reproductor extern ---
    @property
    def stdin(self):
        return self

    def write(self, dades):
        if self.stream is None or self._err or self._fi:
            raise ValueError("stream d'àudio tancat")
        try:
            self.stream.write(np.frombuffer(dades, dtype=np.int16))
        except Exception as e:  # noqa: BLE001
            self._err = True
            self._rc = 1
            raise ValueError(str(e)) from e

    def close(self):
        try:
            if self.stream is not None and not self._err:
                self.stream.stop()      # drena el buffer pendent
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._abaixa()

    def _abaixa(self):
        if self.stream is not None:
            try:
                self.stream.close()
            except Exception:  # noqa: BLE001
                pass
        self._fi = True

    def poll(self):
        if self._err:
            return self._rc or 1
        return 0 if self._fi else None

    @property
    def returncode(self):
        if self._err:
            return self._rc or 1
        return 0 if self._fi else None

    @property
    def pid(self):
        return None

    def atura(self):
        try:
            if self.stream is not None and not self._err:
                self.stream.abort()     # talla JA
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._abaixa()


# Ordre de host APIs preferit per SO, del més «modern/professional» al més
# compatible. Windows: **WASAPI** primer (és el que fan servir DAWs i VLC en
# mode compartit), amb **DirectSound** i **MME** (el més universal) com a xarxa
# de seguretat; WDM-KS i ASIO al final (requereixen drivers/exclusivitat).
# macOS: **Core Audio** (l'únic). (Linux no passa per aquí.)
_ORDRE_APIS = {
    "win": ["Windows WASAPI", "Windows DirectSound", "MME", "Windows WDM-KS"],
    "mac": ["Core Audio"],
}


def _dispositius_candidats(sd):
    """Dispositius de sortida per ordre de preferència (host API).

    Retorna una llista d'índexs de dispositiu; l'últim és `None` (= el
    dispositiu per defecte de PortAudio) com a últim recurs.
    """
    ordre = _ORDRE_APIS.get(plataforma.SO, [])
    try:
        apis = sd.query_hostapis()
    except Exception:  # noqa: BLE001
        return [None]
    devs = []
    for nom in ordre:
        for a in apis:
            try:
                if nom.lower() in str(a.get("name", "")).lower():
                    d = a.get("default_output_device", -1)
                    if isinstance(d, int) and d >= 0 and d not in devs:
                        devs.append(d)
            except Exception:  # noqa: BLE001
                continue
    devs.append(None)
    return devs
