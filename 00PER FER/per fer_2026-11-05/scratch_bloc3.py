"""
Script de modificació per al BLOC 3: eliminació de funcions mortes puntuals.
Genera els fitxers modificats a PAQUET_USB_2026-11-05/BLOC3_CODI_MORT_PUNTUAL/MODIFICATS/app/
"""
import os
import difflib

BASE = os.path.abspath('.')
OUT_DIR = os.path.join(BASE, '00PER FER', 'PAQUET_USB_2026-11-05', 'BLOC3_CODI_MORT_PUNTUAL', 'MODIFICATS', 'app')
DIFFS_DIR = os.path.join(BASE, '00PER FER', 'PAQUET_USB_2026-11-05', 'BLOC3_CODI_MORT_PUNTUAL', 'DIFFS')
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(DIFFS_DIR, exist_ok=True)

def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def remove_block(text, start_marker, end_markers):
    """Elimina el bloc que comença a start_marker fins al primer end_marker."""
    idx = text.find(start_marker)
    if idx == -1:
        raise ValueError(f"Marcador no trobat: {start_marker!r}")
    # Busca la línia on comença
    start = text.rfind('\n', 0, idx) + 1  # inici de la línia
    # Busca el final del bloc (pròxima definició al mateix nivell)
    after = idx + len(start_marker)
    end = len(text)
    for em in end_markers:
        pos = text.find(em, after)
        if pos != -1 and pos < end:
            end = pos
    # Recua fins a l'inici de la línia
    end = text.rfind('\n', 0, end) + 1
    removed = text[start:end]
    return text[:start] + text[end:], removed

changes = []

# ============================================================
# 1. app/pipeline.py — duplica_acord i duplica_seccio
# ============================================================
src = 'app/pipeline.py'
text = read(src)

# duplica_acord: de def fins a def duplica_seccio
marker = 'def duplica_acord(acords, idx, durada, marge=MIN_GAP_TEMPS):'
end_m = ['def duplica_seccio(seccions, idx, marge=MIN_GAP_TEMPS):']
text, removed = remove_block(text, marker, end_m)
changes.append(f'pipeline.py: eliminat duplica_acord ({len(removed.splitlines())} línies)')

# duplica_seccio: de def fins a def duplica_bloc_clips
marker = 'def duplica_seccio(seccions, idx, marge=MIN_GAP_TEMPS):'
end_m = ['def duplica_bloc_clips(']
text, removed = remove_block(text, marker, end_m)
changes.append(f'pipeline.py: eliminat duplica_seccio ({len(removed.splitlines())} línies)')

write(os.path.join(OUT_DIR, 'pipeline.py'), text)
print(f'pipeline.py: {changes[-2]}\n  {changes[-1]}')

# ============================================================
# 2. app/plataforma.py — proces_viu
# ============================================================
src = 'app/plataforma.py'
text = read(src)
marker = 'def proces_viu(pid):'
# Busca la seguent funció de nivell 0 (def o class)
idx = text.find(marker)
after = idx + len(marker)
# Busca el seguent def/class al nivel 0 (sense indentació)
import re
m = re.search(r'\ndef [^\s]|\nclass [^\s]', text[after:])
end_pos = after + (m.start() + 1 if m else len(text[after:]))
start_line = text.rfind('\n', 0, idx) + 1
# Inclou el bloc de comentari previ (si hi ha)
# Mira si hi ha una línea de comentari/docstring abans
pre = text[:start_line].rstrip('\n')
pre_line_start = pre.rfind('\n') + 1
pre_line = pre[pre_line_start:]
# Recull la funció sencera
removed = text[start_line:end_pos]
text = text[:start_line] + text[end_pos:]
n = len(removed.splitlines())
changes.append(f'plataforma.py: eliminat proces_viu ({n} línies)')
write(os.path.join(OUT_DIR, 'plataforma.py'), text)
print(f'plataforma.py: {changes[-1]}')

# ============================================================
# 3. app/tempo_map.py — clip_te_temps_sencer
# ============================================================
src = 'app/tempo_map.py'
text = read(src)
marker = 'def clip_te_temps_sencer(tram, graella=None):'
end_m = ['def valida_i_normalitza_compassos(']
text, removed = remove_block(text, marker, end_m)
n = len(removed.splitlines())
changes.append(f'tempo_map.py: eliminat clip_te_temps_sencer ({n} línies)')
write(os.path.join(OUT_DIR, 'tempo_map.py'), text)
print(f'tempo_map.py: {changes[-1]}')

# ============================================================
# 4. app/metronom.py — _ha_de_sonar, _es_accent, beats_a_temps
# ============================================================
src = 'app/metronom.py'
text = read(src)

# _ha_de_sonar: fins a _es_accent
marker = 'def _ha_de_sonar(mode, beat, num, den):'
end_m = ['def _es_accent(mode, beat, num, den):']
text, removed = remove_block(text, marker, end_m)
n = len(removed.splitlines())
changes.append(f'metronom.py: eliminat _ha_de_sonar ({n} línies)')

# _es_accent: fins a beats_a_temps
marker = 'def _es_accent(mode, beat, num, den):'
end_m = ['def beats_a_temps(']
text, removed = remove_block(text, marker, end_m)
n = len(removed.splitlines())
changes.append(f'metronom.py: eliminat _es_accent ({n} línies)')

# beats_a_temps: fins a mescla_metronom
marker = 'def beats_a_temps(k, bpm, offset=0.0, den=4):'
end_m = ['def mescla_metronom(']
text, removed = remove_block(text, marker, end_m)
n = len(removed.splitlines())
changes.append(f'metronom.py: eliminat beats_a_temps ({n} línies)')

write(os.path.join(OUT_DIR, 'metronom.py'), text)
print(f'metronom.py: 3 funcions eliminades')

# ============================================================
# 5. app/main.py — _idx_acord_del_cursor, _idx_seccio_del_cursor, _idx_tram_del_cursor
# ============================================================
src = 'app/main.py'
text = read(src)

# _idx_acord_del_cursor: fins a _parteix_acord_ui
marker = '    def _idx_acord_del_cursor(self):'
end_m = ['    def _parteix_acord_ui(self):']
text, removed = remove_block(text, marker, end_m)
n = len(removed.splitlines())
changes.append(f'main.py: eliminat _idx_acord_del_cursor ({n} línies)')

# _idx_seccio_del_cursor: fins a _parteix_seccio_ui
marker = '    def _idx_seccio_del_cursor(self):'
end_m = ['    def _parteix_seccio_ui(self):']
text, removed = remove_block(text, marker, end_m)
n = len(removed.splitlines())
changes.append(f'main.py: eliminat _idx_seccio_del_cursor ({n} línies)')

# _idx_tram_del_cursor: fins a _afegeix_tram_ui
marker = '    def _idx_tram_del_cursor(self):'
end_m = ['    def _afegeix_tram_ui(self):']
text, removed = remove_block(text, marker, end_m)
n = len(removed.splitlines())
changes.append(f'main.py: eliminat _idx_tram_del_cursor ({n} línies)')

write(os.path.join(OUT_DIR, 'main.py'), text)
print(f'main.py: 3 funcions eliminades')

# ============================================================
# 6. app/ffmpeg.py — VELOCITATS, PREFIX_VELOCITAT, cadena_atempo, ruta_velocitat, estira_a_wav
# NOTA: cadena_atempo i prepara_escolta son usades per visor.py (velocitat de reproduccio)!
# Nomes eliminem: VELOCITATS (constant del guiat), ruta_velocitat i estira_a_wav
# CONSERVEM: cadena_atempo, prepara_escolta, PREFIX_VELOCITAT (usades per visor)
# ============================================================
src = 'app/ffmpeg.py'
text = read(src)

# Eliminar el comentari-secció i la constant VELOCITATS + PREFIX_VELOCITAT
old_vel = """\n# --- Velocitat amb el to mantingut (Anàlisi guiat v3, R11) -------------------
#: Velocitats que ofereix el diàleg d'ancoratges: ½ · ⅔ (1÷1,5) · 1 · 1,5 · 2 · 4.
VELOCITATS = (0.5, 1.0 / 1.5, 1.0, 1.5, 2.0, 4.0)
#: Prefix dels temporals d'estirament (R19: viuen al directori temporal).
PREFIX_VELOCITAT = \"auto_chords_vel_\"\n"""
new_vel = """\n# --- Velocitat amb el to mantingut -------------------------------------------
#: Prefix dels temporals d'estirament (R19: viuen al directori temporal).
PREFIX_VELOCITAT = \"auto_chords_vel_\"\n"""
assert old_vel in text, 'Bloc VELOCITATS no trobat'
text = text.replace(old_vel, new_vel)
changes.append('ffmpeg.py: eliminat VELOCITATS (constant del guiat v3)')

# Eliminar ruta_velocitat: fins a cadena_atempo
# cadena_atempo va ABANS de ruta_velocitat a la definicio! Revisa l'ordre
# Llegim les linies per verificar l'ordre
with open(src, 'r', encoding='utf-8') as f:
    all_lines = f.readlines()
for i, l in enumerate(all_lines, 1):
    if 'def cadena_atempo' in l or 'def ruta_velocitat' in l or 'def estira_a_wav' in l or 'def prepara_escolta' in l:
        print(f'  ORDRE ffmpeg.py L{i}: {l.strip()}')

write(os.path.join(OUT_DIR, 'ffmpeg.py'), text)
print('ffmpeg.py: VELOCITATS eliminat (cadena_atempo/prepara_escolta conservades)')

# ============================================================
# 7. Genera bloc3.patch unificat
# ============================================================
all_files = ['pipeline.py', 'plataforma.py', 'tempo_map.py', 'metronom.py', 'main.py', 'ffmpeg.py']
full_patch = ''
for rel in all_files:
    orig_path = os.path.join(BASE, 'app', rel)
    mod_path = os.path.join(OUT_DIR, rel)
    with open(orig_path, 'r', encoding='utf-8') as f:
        orig_lines = f.readlines()
    with open(mod_path, 'r', encoding='utf-8') as f:
        mod_lines = f.readlines()
    diff = difflib.unified_diff(
        orig_lines, mod_lines,
        fromfile=f'a/app/{rel}', tofile=f'b/app/{rel}', lineterm=''
    )
    diff_text = '\n'.join(diff)
    if diff_text:
        full_patch += f'diff --git a/app/{rel} b/app/{rel}\n' + diff_text + '\n'

patch_path = os.path.join(DIFFS_DIR, 'bloc3.patch')
with open(patch_path, 'w', encoding='utf-8') as f:
    f.write(full_patch)

print(f'\nbloc3.patch generat: {len(full_patch)} caracters')
print('\nREsum canvis:')
for c in changes:
    print(f'  {c}')
