"""Abstracció de plataforma: tot el que canvia entre Linux, Windows i macOS.

Objectiu: que la resta del codi no hagi de saber a quin SO corre. **Al Linux no
canvia res** del comportament actual (els valors que retorna són els d'abans).

Vegeu `ROADMAP.md` secció 9 (desplegament a altres SO).
"""
import os
import signal
import subprocess
import sys
import tempfile

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
def _sufix_usuari():
    """Identificador curt de l'usuari (uid + nom) per al fitxer de bloqueig.

    El bloqueig ha de ser PER USUARI: en una màquina compartida, un usuari no
    ha de poder bloquejar-ne un altre.
    """
    try:
        uid = str(os.getuid())          # POSIX; a Windows no hi és
    except AttributeError:
        uid = ""
    try:
        import getpass
        usuari = getpass.getuser() or ""
    except Exception:  # noqa: BLE001
        usuari = ""
    # El nom d'usuari forma part del NOM DEL FITXER (no és una ruta de
    # l'usuari): en traiem els caràcters que complicarien el nom.
    usuari = "".join(c for c in usuari if c.isalnum() or c in "-_.")
    return "_".join(p for p in (uid, usuari) if p) or "usuari"


def dir_instancia():
    """Directori PER USUARI i escriptible per al bloqueig d'instància única.

    Linux: `XDG_RUNTIME_DIR` (per usuari, 0700 i efímer) si existeix i s'hi pot
    escriure; si no, el directori d'estat de `config.py` (també per usuari).
    Així NO fem servir un `/tmp` compartit amb un nom global.
    """
    xdg = os.getenv("XDG_RUNTIME_DIR")
    if xdg and os.path.isdir(xdg) and os.access(xdg, os.W_OK):
        return xdg
    try:
        from app import config
        d = config.DADES_DIR
    except Exception:  # noqa: BLE001
        d = tempfile.gettempdir()
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def fitxer_instancia():
    """Ruta del fitxer de bloqueig d'instància única (per usuari)."""
    return os.path.join(
        dir_instancia(), f"auto_chords_single_instance_{_sufix_usuari()}.lock")


def obre_fitxer_instancia():
    """Obre (o crea) el fitxer de bloqueig d'instància única. `None` si no pot.

    Linux/macOS: `os.open` amb `O_RDWR|O_CREAT|O_NOFOLLOW` i mode `0o600` → no
    segueix enllaços simbòlics i només el propietari hi pot accedir. Windows:
    `os.open` + `msvcrt.locking` (allà `O_NOFOLLOW` no existeix).

    No esborra el fitxer si ja existeix (pot ser d'una sessió anterior): només
    l'obre. El bloqueig el gestiona `bloqueja_instancia_unica`.
    """
    path = fitxer_instancia()
    if ES_WINDOWS:
        flags, mode = os.O_RDWR | os.O_CREAT, "r+"
    else:
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        mode = "a+"
    try:
        fd = os.open(path, flags, 0o600)
    except OSError:
        return None
    try:
        return os.fdopen(fd, mode, encoding="utf-8")
    except OSError:
        os.close(fd)
        return None


def bloqueja_instancia_unica(fitxer):
    """Bloqueig NO bloquejant sobre `fitxer`. True si l'hem obtingut.

    Linux/macOS: `fcntl.flock`. Windows: `msvcrt.locking` (cal un byte al
    fitxer per poder-lo bloquejar).
    """
    if ES_WINDOWS:
        import msvcrt
        # ⚠️ El seek/write/flush van DINS el try: a Windows, ESCRIURE en una
        # regió ja bloquejada LLANÇA OSError (no torna False) → si quedés fora,
        # la 2a instància petaria en lloc de ser rebutjada. I el seek(0) final
        # fa que el locking bloquegi l'offset 0 (coherent amb `desbloqueja`).
        try:
            fitxer.seek(0); fitxer.write("0"); fitxer.flush(); fitxer.seek(0)
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


def proces_viu(pid):
    """Cert si `pid` és un procés VIU (cross-platform).

    ⚠️ A **Windows**, `os.kill(pid, 0)` **NO és una sonda**: acaba cridant
    `TerminateProcess` (podria MATAR el procés!) i, per a un pid inexistent,
    llança `OSError` → es confonia amb «mort». Per això, allà es consulta amb
    `OpenProcess` + `GetExitCodeProcess` (només lectura, mai mata res).
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if not ES_WINDOWS:
        try:
            os.kill(pid, 0)          # senyal 0: només comprova que existeixi
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True              # existeix (d'un altre usuari)
        except OSError:
            return False
    try:
        import ctypes
        from ctypes import wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        k = ctypes.windll.kernel32
        h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            codi = wintypes.DWORD()
            if not k.GetExitCodeProcess(h, ctypes.byref(codi)):
                return False
            return codi.value == STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    except Exception:  # noqa: BLE001
        return False
