# Seguretat — què s'ha endurit i com es manté

> Resum pràctic de l'**enduriment de seguretat** de l'app i de la seva **cadena
> de subministrament**. El detall cronològic és al `CHANGELOG.md`; les regles
> d'or de l'app, a `docs/REGLES_DE_LA_APP.md`.
> Aquest document **no** és el canal per informar d'una vulnerabilitat (això és
> `SECURITY.md`, a l'arrel).

Principi general: **no es restringeix cap ruta** ni es posa cap sandbox — l'app
ha de poder llegir i escriure a qualsevol lloc (espais, accents, `#`, `&`,
cometes, unicode, unitats externes, UNC, enllaços i rutes llargues). El que
s'endureix és **l'entorn** (permisos, límits, origen de les dades), no
l'usuari.

## 1. Import d'àudio (ffmpeg/ffprobe) — `app/ffmpeg.py`

- Les comandes d'`info()` i `converteix_a_wav()` porten **`-nostdin`** i
  **`-protocol_whitelist file,pipe`** abans de l'entrada → un fitxer disfressat
  (playlist HLS/concat, subtítol…) **no pot** fer que ffmpeg llegeixi altres
  fitxers ni faci peticions de xarxa.
- Les rutes es passen **absolutes** (i amb `./` si comencessin amb `-`), **sense
  filtrar-ne cap caràcter**.
- **Fallback**: si el binari no entén una d'aquestes opcions (ffprobe no té
  `-nostdin`; ffmpeg molt vells no tenen `-protocol_whitelist`), es reintenta
  sense ella i es registra al log. **Mai es trenca l'obertura d'àudio.**
- Tests: `tests/test_pipeline_export.py` → `FfmpegSeguretatTests`.

## 2. Instància única — `app/plataforma.py`, `app/main.py`

- El fitxer de bloqueig viu en un directori **PER USUARI** (`XDG_RUNTIME_DIR` o
  el directori d'estat de `config.py`) i porta l'**uid/nom d'usuari al nom**: en
  una màquina compartida, un usuari no bloqueja un altre.
- S'obre amb `os.open(..., O_RDWR|O_CREAT|O_NOFOLLOW, 0o600)`: **no segueix
  enllaços simbòlics** i només el propietari hi accedeix. Windows manté
  `msvcrt.locking`.
- En sortir **només s'allibera el bloqueig**; **no s'esborra el fitxer**
  (esborrar-lo crearia una carrera entre instàncies).
- Tests: `InstanciaUnicaTests`.

## 3. Pont MCP — `app/mcp_bridge.py`

- El fitxer d'acord `temp/mcp_bridge.json` (que porta el **testimoni**) es crea
  amb **permisos `0600`** (`os.open` amb mode + `os.replace`).
- **Límit de longitud de línia (1 MiB)**: es respon error i es tanca la connexió
  **abans de processar-la**. **Límit de connexions simultànies (8)**.
- El **testimoni es valida abans de qualsevol altra feina** (comparació en temps
  constant) i abans de posar res a la cua.
- `ac_open_wav` **no restringeix** la ruta (invariant).
- Tests: `tests/test_mcp_bridge.py` → `TestPontSocket` (socket real).

## 4. Noms de fitxer — `app/pipeline.py:safe_filename()`

- Substitueix els **caràcters reservats a Windows** (`: * ? " < > |`), treu el
  **punt o espai final** i evita els **noms reservats** (`CON`, `PRN`, `AUX`,
  `NUL`, `COM0-9`, `LPT0-9`).
- Es fa **sempre** (també a Linux/macOS) perquè el mateix projecte doni els
  **mateixos noms a tots els SO**.
- Si dos noms queden iguals després de netejar/truncar, es **desambigüen amb un
  sufix** (`_2`, `_3`…). **Els noms únics no canvien mai.**
- Els noms d'acord habituals (`C`, `C#m7`, `N`, `Am/G`→`Am-G`…) són **idèntics**
  (hi ha un **test «daurat»**).
- Tests: `SafeFilenameTests`.

## 5. Directoris temporals — `app/pipeline.py`, `app/partitura.py`

- Els `ac_ttl_` / `ac_qm_` / `ac_key_` que crea l'anàlisi **s'esborren sempre**
  (en un `finally`, també si peta).
- `pipeline.esborra_tmp()` **només** esborra directoris amb aquests prefixos
  propis → mai pot esborrar una ruta arbitrària.
- Tests: `TemporalsTests`.

## 6. Cadena de subministrament — `eines/baixa_verificat.py` + `eines/deps_fixades.env`

- **`eines/baixa_verificat.py`** (només biblioteca estàndard, Python ≥ 3.8 del
  sistema): baixa per **HTTPS**, amb reintents i timeout, i **comprova el
  SHA256**; si no quadra → error, codi ≠ 0 i **no deixa cap fitxer a mitges**.
- **`eines/deps_fixades.env`** fixa **URL + versió + SHA256** de tot el que es
  baixa (CPython portable, ffmpeg de Linux/macOS/Windows, appimagetool, icones
  Lucide) i el **commit** dels repositoris que es compilen (qm-vamp-plugins,
  qm-dsp, vamp-plugin-sdk, libsndfile).
- Tests: `tests/test_baixa_verificat.py`.

### Com s'actualitza una versió

1. Canvia la versió/URL a `eines/deps_fixades.env`.
2. Calcula el SHA256 nou:
   ```sh
   python3 eines/baixa_verificat.py "<URL>" - /tmp/x
   ```
   El `-` vol dir «no verifiquis: digues-me el hash» → **confiança en el primer
   ús**. A partir d'aquí queda fixat al fitxer i **es verifica sempre**.
3. Enganxa'l a la variable `..._SHA256` corresponent.
4. Comprova que la baixada verificada funciona:
   ```sh
   python3 eines/baixa_verificat.py "<URL>" "<SHA256>" /tmp/x
   ```
5. Comprova que el build segueix funcionant. A **macOS**, a més, que es manté el
   mínim **10.13**: `eines/verifica_minos_macos.py`.

### Memòria cau (no baixar dues vegades)

- `baixa_verificat.py` desa cada fitxer verificat a **`.baixades/<sha256>`**
  (carpeta **gitignorada**; es pot canviar amb `$AUTO_CHORDS_BAIXADES`). La
  propera vegada **no es baixa**: es copia (i es torna a comprovar el hash).
  `--sense-cache` ho desactiva.
- Al **CI**, `actions/cache` conserva `.baixades` entre execucions (clau:
  `deps-<SO>-<hash de deps_fixades.env>`) → les baixades es fan **un cop per
  versió i plataforma**, no a cada build.
- Per què **no** es guarden al repositori: GitHub **rebutja fitxers > 100 MB**
  (el ffmpeg de Windows ja en fa 114), l'historial de git no oblida mai (cada
  versió afegiria una còpia sencera) i un binari al repo s'hauria de confiar
  cegament — en canvi, un hash verificat no.

### Què no s'ha de fer

- **No** baixar res amb `curl`/`Invoke-WebRequest` directament als scripts: cal
  fer servir `baixa_verificat.py` amb les variables de `deps_fixades.env`.
- **No** fixar mai URLs «mòbils» (`continuous`, `getrelease`, `latest`,
  `-release-`): sempre versió explícita.
- **No** pujar cap versió (numpy, PyQt5, ffmpeg, accions de GitHub…) sense
  comprovar-ho: la regla del projecte és **fixar el que funciona ara**.
- **No** fer servir `numpy ≥ 2` ni `PyQt6` (Q9400 sense AVX/SSE4.2).
