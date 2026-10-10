#!/usr/bin/env bash
# smoke_macos.sh — Smoke test de l'.app de macOS (headless, sense GUI).
#
# Executa l'executable de l'.app amb AUTO_CHORDS_SMOKE=1 (l'app crea la
# finestra, ho registra al log i surt sola) i comprova que ARRENCA de debò.
# Prova diverses plataformes Qt (offscreen → minimal → per defecte) i, si
# totes fallen, imprimeix TOT el diagnòstic possible (stdout/stderr, el log de
# l'app i el log unificat de macOS) i emet un ::error:: compacte.
#
# Ús: smoke_macos.sh [ruta .app]      (per defecte dist/AUTO_CHORDS.app)
# Sortida: 0 = OK; 1 = ha fallat. Sempre deixa `smoke_diag.txt`.
set -u

APP="${1:-dist/AUTO_CHORDS.app}"
BIN="$APP/Contents/MacOS/AUTO_CHORDS"
DIAG="$(pwd)/smoke_diag.txt"
: > "$DIAG"

log() { printf '%s\n' "$*" | tee -a "$DIAG"; }

log "=== Smoke test de $APP ==="
if [ ! -x "$BIN" ]; then
  log "!! no existeix l'executable: $BIN"
  echo "::error::Smoke: no existeix $BIN"
  exit 1
fi
PLUGS="$(find "$APP" -type d -name platforms 2>/dev/null | head -1)"
log "platforms dir: ${PLUGS:-<cap>}"
[ -n "$PLUGS" ] && log "$(ls "$PLUGS" 2>/dev/null)"

log "--- warn de PyInstaller (moduls/data que falten) ---"
cat build/*/warn-*.txt 2>/dev/null | grep -iE "pyqt|qt5|qtcore|sip|numpy|missing" | head -30 | sed 's/^/  | /' || true
log "--- arbre del bundle (directoris, maxdepth 4) ---"
find "$APP" -maxdepth 4 -type d 2>/dev/null | head -50 | sed 's/^/  | /'
log "--- Contents/MacOS ---"; ls "$APP/Contents/MacOS" 2>/dev/null | sed 's/^/  | /'
log "--- Contents/Frameworks (primeres 30) ---"; ls "$APP/Contents/Frameworks" 2>/dev/null | head -30 | sed 's/^/  | /'

# Intenta arrencar l'app amb una plataforma Qt. Retorna 0 si arrenca bé.
try() {
  plat="$1"
  tmp="$(mktemp -d)"
  out="$tmp/smoke.out"
  export AUTO_CHORDS_SMOKE=1
  export AUTO_CHORDS_TEMP="$tmp/ac-temp"
  export TMPDIR="$tmp"                 # aïlla el lock d'instància única
  if [ "$plat" = "__default__" ]; then unset QT_QPA_PLATFORM
  else export QT_QPA_PLATFORM="$plat"; fi

  log ""
  log "--- intent QT_QPA_PLATFORM=${plat} ---"
  "$BIN" >"$out" 2>&1 &
  pid=$!
  # timeout portable (macOS no té `timeout`): espera fins a 25 s
  n=0
  while kill -0 "$pid" 2>/dev/null && [ "$n" -lt 50 ]; do sleep 0.5; n=$((n + 1)); done
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM "$pid" 2>/dev/null; sleep 1; kill -KILL "$pid" 2>/dev/null
    rc=124
  else
    wait "$pid" 2>/dev/null; rc=$?
  fi
  log "rc=$rc"
  log "stdout/stderr de l'app:"
  sed 's/^/  | /' "$out" 2>/dev/null | tail -40

  aclog="$(find "$APP" "$HOME/.local/state/auto-chords" "$tmp" \
           -name auto_chords.log 2>/dev/null | head -1)"
  if [ -n "$aclog" ]; then
    log "log de l'app ($aclog):"
    tail -40 "$aclog" | sed 's/^/  | /'
  else
    log "log de l'app: (no s'ha creat cap auto_chords.log)"
  fi

  log "log unificat de macOS (process AUTO_CHORDS):"
  /usr/bin/log show --style compact --last 3m \
    --predicate 'process == "AUTO_CHORDS"' 2>/dev/null \
    | tail -20 | sed 's/^/  | /' || true

  if [ "$rc" = "0" ] && [ -n "$aclog" ] \
     && grep -q "SMOKE: finestra principal creada" "$aclog" 2>/dev/null; then
    return 0
  fi
  return 1
}

OK=0
for plat in offscreen minimal __default__; do
  if try "$plat"; then log ""; log "OK: l'app arrenca amb QT_QPA_PLATFORM=$plat"; OK=1; break; fi
done

if [ "$OK" = "1" ]; then
  echo "SMOKE OK"
  exit 0
fi

echo "::error::Smoke FALLIT: l'.app no arrenca (cap plataforma Qt). Vegeu smoke_diag.txt."
# Anotacio compacte (1 linia) amb l'essencial, llegible per API sense auth.
python3 - <<'PY' 2>/dev/null || true
import re
try:
    txt = open("smoke_diag.txt", encoding="utf-8", errors="replace").read()
except OSError:
    txt = ""
msg = " ".join(txt.split())
print("::error::" + msg[-1400:])
PY
exit 1
