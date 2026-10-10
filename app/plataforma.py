"""Abstracció de plataforma: tot el que canvia entre Linux, Windows i macOS.

Objectiu: que la resta del codi no hagi de saber a quin SO corre. **Al Linux no
canvia res** del comportament actual (els valors que retorna són els d'abans).

Vegeu `ROADMAP.md` secció 9 (desplegament a altres SO).
"""
import os
import signal
import subprocess
import sys

ES_WINDOWS = sys.platform.startswith("win")
ES_MAC = sys.platform == "darwin"
ES_LINUX = not ES_WINDOWS and not ES_MAC

SO = "win" if ES_WINDOWS else ("mac" if ES_MAC else "linux")

# --- Noms de binaris --------------------------------------------------------
EXE = ".exe" if ES_WINDOWS else ""
NOM_HOST = "vamp_host_local" + EXE
NOM_FFMPEG = "ffmpeg" + EXE
NOM_FFPROBE = "ffprobe" + EXE


def executable(ruta):
    """Cert si `ruta` és un executable utilitzable en aquest SO.

    A Windows `os.access(..., X_OK)` no és fiable: n'hi ha prou que el fitxer
    hi sigui.
    """
    if not os.path.isfile(ruta):
        return False
    return True if ES_WINDOWS else os.access(ruta, os.X_OK)


# --- Plugins Vamp -----------------------------------------------------------
_DIRS_PLUGINS = {
    "linux": ("nnls-chroma-linux64-local", "qm-vamp-plugins-linux64-local"),
    "win": ("nnls-chroma-win64-local", "qm-vamp-plugins-win64-local"),
    "mac": ("nnls-chroma-macos-local", "qm-vamp-plugins-macos-local"),
}


def dirs_plugins(arrel):
    """Directoris dels plugins Vamp per a aquest SO."""
    return [os.path.join(arrel, n) for n in _DIRS_PLUGINS[SO]]


def path_env_vamp(dirs):
    """`VAMP_PATH` amb el separador del SO (`:` a Linux/macOS, `;` a Windows)."""
    return os.pathsep.join(dirs)


# --- Intèrpret de Python ----------------------------------------------------
def python_actual():
    """Intèrpret per tornar a invocar el projecte (mai un `python3` fix).

    Amb PyInstaller congelat `sys.executable` és la mateixa app: en aquest cas
    cal cridar en procés (ho decideix `congelat()`).
    """
    return sys.executable or "python"


def congelat():
    """Cert si correm dins un executable empaquetat (PyInstaller)."""
    return bool(getattr(sys, "frozen", False))


# --- Reproductor d'àudio ----------------------------------------------------
def candidats_reproductor():
    """Reproductors EXTERNS per `stdin` (només Linux; vegeu `usa_audio_natiu`).

    Linux: `paplay` (PipeWire/Pulse) i `aplay` (ALSA) — els de qualsevol
    escriptori. A macOS/Windows **no** es fa servir cap procés extern: el motor
    natiu (`app/audio_out.py`, sobre PortAudio) reprodueix dins el procés.
    """
    if ES_WINDOWS or ES_MAC:
        return ()
    return ("paplay", "aplay")


def usa_audio_natiu():
    """Cert si cal el motor d'àudio natiu (PortAudio/`sounddevice`).

    macOS (**CoreAudio**) i Windows (**MME**, el back-end més compatible, amb
    fallback DirectSound/WASAPI/ASIO). A Linux es manté el reproductor extern de
    sempre (`paplay`/`aplay`) — no es toca.
    """
    return ES_WINDOWS or ES_MAC


def missatge_sense_audio():
    """Missatge d'error (segons el SO) quan no es pot obrir cap sortida d'àudio."""
    if ES_WINDOWS or ES_MAC:
        return ("No he pogut obrir la sortida d'àudio del sistema.\n\n"
                "Comprova que l'equip tingui una sortida d'àudio activa.\n"
                "La resta de l'app (analitzar, editar, exportar) funciona igual.")
    return ("No hi ha cap reproductor d'àudio (ni `paplay` ni `aplay`).\n\n"
            "Cal **PipeWire** o **PulseAudio** per poder escoltar.\n"
            "La resta de l'app (analitzar, editar, exportar) funciona igual.")


# --- Grups de processos (matar el reproductor sencer) -----------------------
def kwargs_nou_grup():
    """Kwargs de `subprocess.Popen` perquè el procés quedi en un grup propi."""
    if ES_WINDOWS:
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def mata_grup(proc, forcat=False):
    """Mata el procés (i els fills si el SO ho permet). Mai llança."""
    if proc is None:
        return
    if ES_WINDOWS:
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            # best-effort (neteja en tancar): silenciós intencionat
            pass
        return
    sig = signal.SIGKILL if forcat else signal.SIGTERM
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            (proc.kill if forcat else proc.terminate)()
        except Exception:  # noqa: BLE001
            # best-effort: el procés ja pot haver mort; silenciós intencionat
            pass


# --- Instància única --------------------------------------------------------
def bloqueja_instancia_unica(fitxer):
    """Bloqueig NO bloquejant sobre `fitxer`. True si l'hem obtingut.

    Linux/macOS: `fcntl.flock`. Windows: `msvcrt.locking` (cal un byte al
    fitxer per poder-lo bloquejar).
    """
    if ES_WINDOWS:
        import msvcrt
        fitxer.seek(0)
        fitxer.write("0")
        fitxer.flush()
        try:
            msvcrt.locking(fitxer.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl
    try:
        fcntl.flock(fitxer.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (BlockingIOError, OSError):
        return False


def desbloqueja(fitxer):
    """Allibera el bloqueig d'instància única (mai llança)."""
    if fitxer is None:
        return
    try:
        if ES_WINDOWS:
            import msvcrt
            fitxer.seek(0)
            msvcrt.locking(fitxer.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fitxer.fileno(), fcntl.LOCK_UN)
    except Exception:  # noqa: BLE001
        # alliberar el lock és best-effort; silenciós intencionat
        pass
