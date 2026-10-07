"""Genera el text (en català) de les notes d'un Release de GitHub.

Extreu la secció de la versió del `CHANGELOG.md` i la combina amb una
capçalera i unes instruccions d'instal·lació per a l'AppImage.

Ús:
    .venv/bin/python eines/notes_release.py 0.5.0            -> stdout
    .venv/bin/python eines/notes_release.py 0.5.0 > notes.md
    .venv/bin/python eines/notes_release.py v0.5.0 --fitxer notes.md
"""

import os
import re
import sys

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(ARREL, "CHANGELOG.md")

CAPÇALERA = """## AUTO CHORDS v{versio}

Aplicació d'escriptori per **analitzar un àudio, navegar-ne els acords i
l'estructura, corregir-los i exportar clips preparats per al DAW**.

Aquesta versió inclou l'**AppImage autocontinguda** per a Linux x86_64
(no cal instal·lar Python, ni Qt, ni res: només executar-la).

### 📥 Com executar l'AppImage

```bash
chmod +x AutoChords_*.AppImage
./AutoChords_*.AppImage
```

O bé **doble clic** al fitxer (pot caler marcar «Executa» a les propietats).

> ⚠️ **Requisit d'àudio per ESCOLTAR**: cal **PipeWire** o **PulseAudio**
> (a qualsevol escriptori Linux actual). Sense ells l'app funciona igual
> (analitzar, editar, exportar); només avisa que no pot sonar.
>
> ✅ **No cal `libfuse2`**: el runtime de l'AppImage és **estàtic** (ho porta
> tot a dins). Només cal el suport **FUSE del nucli** (estàndard a tot Linux).
> Si mai fallés: `./AutoChords_*.AppImage --appimage-extract-and-run`

---

## Canvis d'aquesta versió

{canvis}

---

*Generat automàticament a partir de `CHANGELOG.md`.*

**Autor:** Pëp (pepelocotango@gmail.com) · **Llicència:** GPL-3.0-or-later.

Desenvolupat en col·laboració amb agents i assistents d'IA: **opencode** (amb
models com **DeepSeek**, **Claude**, **Gemini**...), **Claude** (Anthropic),
**Gemini** i **Google AI Studio**, **Devin**, **Chatbox**, **VS Code +
GitHub Copilot** i **Windsurf + SWE**. Gràcies! 💙
"""


def _seccio_changelog(versio):
    """Retorna el text de la secció `## [versio]` del CHANGELOG (o '')."""
    if not os.path.isfile(CHANGELOG):
        return ""
    with open(CHANGELOG, encoding="utf-8") as f:
        text = f.read()
    # ## [0.5.0] — data   ... fins a la següent ## [
    patro = re.compile(
        r"^##\s+\[" + re.escape(versio) + r"\][^\n]*\n(.*?)(?=^##\s+\[|\Z)",
        re.M | re.S)
    m = patro.search(text)
    if not m:
        return ""
    cos = m.group(1).strip()
    # treu subratllats de markdown exagerats i espais de sobra
    cos = re.sub(r"\n{3,}", "\n\n", cos)
    return cos


def notes(versio):
    versio = versio.lstrip("v")
    canvis = _seccio_changelog(versio)
    if not canvis:
        canvis = ("_No s'ha trobat la secció d'aquesta versió al CHANGELOG; "
                  "consulta'l al repositori._")
    return CAPÇALERA.format(versio=versio, canvis=canvis)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("Ús: notes_release.py <versio> [--fitxer <sortida>]", file=sys.stderr)
        return 2
    text = notes(args[0])
    if "--fitxer" in sys.argv:
        desti = sys.argv[sys.argv.index("--fitxer") + 1]
        with open(desti, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"notes escrites a {desti}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
