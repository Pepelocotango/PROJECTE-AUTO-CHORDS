"""
Script de modificació per al BLOC 3 (part 2): elimina ruta_velocitat i estira_a_wav de ffmpeg.py
Ja que test_ancoratges.py s'elimina al BLOC 2, i ruta_velocitat/estira_a_wav no son usades
per cap fitxer viu de producció.
"""
import os, re, difflib

BASE = os.path.abspath('.')
OUT_DIR = os.path.join(BASE, '00PER FER', 'PAQUET_USB_2026-11-05', 'BLOC3_CODI_MORT_PUNTUAL', 'MODIFICATS', 'app')
DIFFS_DIR = os.path.join(BASE, '00PER FER', 'PAQUET_USB_2026-11-05', 'BLOC3_CODI_MORT_PUNTUAL', 'DIFFS')

# Llegim el fitxer JA MODIFICAT (sense VELOCITATS)
path = os.path.join(OUT_DIR, 'ffmpeg.py')
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Trobem les posicions
def find_def(lines, name):
    for i, l in enumerate(lines):
        if l.strip().startswith(f'def {name}('):
            return i
    return -1

# ruta_velocitat: des de L288 fins a prepara_escolta (L314 en el fitxer modificat)
idx_ruta = find_def(lines, 'ruta_velocitat')
idx_prepara = find_def(lines, 'prepara_escolta')
# estira_a_wav: des del seu inici fins al final del fitxer o pròxima def
idx_estira = find_def(lines, 'estira_a_wav')

print(f'ruta_velocitat: L{idx_ruta+1}, prepara_escolta: L{idx_prepara+1}, estira_a_wav: L{idx_estira+1}')

# Elimina el bloc de ruta_velocitat (des de la línia anterior si és un comentari)
# Comprova si hi ha comentari previ
pre_ruta = idx_ruta - 1
while pre_ruta >= 0 and (lines[pre_ruta].strip().startswith('#') or lines[pre_ruta].strip() == ''):
    pre_ruta -= 1
pre_ruta += 1  # Primera línia a eliminar del bloc de ruta_velocitat
# El bloc arriba fins a prepara_escolta
new_lines = lines[:pre_ruta] + lines[idx_prepara:]

# Ara elimina estira_a_wav des del nou índex
idx_estira2 = None
for i, l in enumerate(new_lines):
    if l.strip().startswith('def estira_a_wav('):
        idx_estira2 = i
        break

if idx_estira2 is not None:
    # El bloc arriba fins al final del fitxer
    # Comprova si hi ha comentari previ
    pre_estira = idx_estira2 - 1
    while pre_estira >= 0 and (new_lines[pre_estira].strip().startswith('#') or new_lines[pre_estira].strip() == ''):
        pre_estira -= 1
    pre_estira += 1
    new_lines = new_lines[:pre_estira]
    # Assegura que el fitxer acabi amb newline
    if new_lines and not new_lines[-1].endswith('\n'):
        new_lines[-1] += '\n'

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f'ffmpeg.py net: ruta_velocitat i estira_a_wav eliminades ({len(lines)} -> {len(new_lines)} linies)')

# Regenera el patch complet del bloc 3
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
print(f'bloc3.patch actualitzat: {len(full_patch)} caracters')
