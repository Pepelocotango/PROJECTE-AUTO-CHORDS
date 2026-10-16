#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera les VISTES de l'esquema de la UI a partir de la FONT ÚNICA `.md`.

- **Font única**: `docs/ESQUEMA_UI.md` (que l'agent de codi manté i que un test
  valida contra la UI real → cadena: codi → `.md` → vistes).
- **Vistes generades** (NO editar a mà):
    - `docs/ESQUEMA_UI.html` — la pàgina (estil fosc) amb l'esquema i les taules.
    - `docs/ESQUEMA_UI.svg`  — l'esquema (regenerable) amb el dibuix de text.

Ús:
    python3 eines/genera_esquema_ui.py            # escriu les dues vistes
    python3 eines/genera_esquema_ui.py --check    # diu si estan al dia (per al test/CI)

Sense dependències (stdlib). El fa servir el test `tests/test_esquema_ui_gen.py`.
"""
from __future__ import annotations

import html as _h
import os
import re
import sys

ARREL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(ARREL, "docs", "ESQUEMA_UI.md")
HTML = os.path.join(ARREL, "docs", "ESQUEMA_UI.html")
SVG = os.path.join(ARREL, "docs", "ESQUEMA_UI.svg")

CAPÇALERA = "Generat per eines/genera_esquema_ui.py a partir de docs/ESQUEMA_UI.md — NO editar a mà."


# --------------------------------------------------------------------------- #
#  Markdown (subconjunt) -> HTML
# --------------------------------------------------------------------------- #
def _inline(text: str) -> str:
    """Negretes, codi i enllaços d'una línia (després d'escapar l'HTML)."""
    s = _h.escape(text.strip())
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<i>\1</i>", s)
    return s


def _es_taula(l: str) -> bool:
    return l.strip().startswith("|") and l.strip().endswith("|")


def _files_taula(l: str) -> list:
    return [c.strip() for c in l.strip().strip("|").split("|")]


def md_a_cos(md: str) -> str:
    """Converteix el `.md` (subconjunt) en el cos HTML."""
    out = []
    lín = md.splitlines()
    i = 0
    n = len(lín)
    while i < n:
        l = lín[i]
        s = l.strip()
        # -- bloc de codi --
        if s.startswith("```"):
            i += 1
            buf = []
            while i < n and not lín[i].strip().startswith("```"):
                buf.append(lín[i])
                i += 1
            i += 1
            out.append("<pre>" + _h.escape("\n".join(buf)) + "</pre>")
            continue
        # -- taula --
        if _es_taula(l) and i + 1 < n and set(lín[i + 1].strip()) <= set("|-: "):
            caps = _files_taula(l)
            i += 2
            files = []
            while i < n and _es_taula(lín[i]):
                files.append(_files_taula(lín[i]))
                i += 1
            th = "".join(f"<th>{_inline(c)}</th>" for c in caps)
            cos = "".join(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in f) + "</tr>"
                for f in files)
            out.append(f"<table><tr>{th}</tr>{cos}</table>")
            continue
        # -- cita (bloc `>`) --
        if s.startswith(">"):
            buf = []
            while i < n and (lín[i].strip().startswith(">")
                             or (buf and not lín[i].strip())):
                t = lín[i].strip()
                if t.startswith(">"):
                    buf.append(t[1:].strip())
                else:
                    buf.append("")
                i += 1
            while buf and not buf[-1]:
                buf.pop()
            out.append("<blockquote>" + "<br>".join(_inline(x) for x in buf)
                       + "</blockquote>")
            continue
        # -- títols --
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            k = len(m.group(1))
            out.append(f"<h{k}>{_inline(m.group(2))}</h{k}>")
            i += 1
            continue
        # -- regla --
        if s in ("---", "***", "___"):
            out.append("<hr>")
            i += 1
            continue
        # -- llista --
        if re.match(r"^\s*[-*]\s+", l):
            buf = []
            while i < n and re.match(r"^\s*[-*]\s+", lín[i]):
                txt = re.sub(r"^\s*[-*]\s+", "", lín[i])
                i += 1
                # continuacions engaltades (línies indentades sense marcador)
                while i < n and lín[i].strip() and not re.match(
                        r"^\s*[-*#>|`]", lín[i]) and not _es_taula(lín[i]):
                    txt += " " + lín[i].strip()
                    i += 1
                buf.append(f"<li>{_inline(txt)}</li>")
            out.append("<ul>" + "".join(buf) + "</ul>")
            continue
        # -- línia buida --
        if not s:
            i += 1
            continue
        # -- paràgraf --
        buf = [l.strip()]
        i += 1
        while (i < n and lín[i].strip()
               and not re.match(r"^(#{1,6}\s|>|```|\s*[-*]\s)", lín[i])
               and not _es_taula(lín[i]) and lín[i].strip() not in ("---",)):
            buf.append(lín[i].strip())
            i += 1
        out.append("<p>" + " ".join(_inline(x) for x in buf) + "</p>")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
#  HTML complet
# --------------------------------------------------------------------------- #
_CSS = """
 :root{--bg:#15181d;--shell:#20242c;--txt:#e8edf5;--muted:#9aa6b8;
       --accent:#5b8dd6;--line:#3a4150;--code:#12151b;--borda:#4d5056;}
 *{box-sizing:border-box}
 body{margin:0;padding:26px 30px;background:var(--bg);color:var(--txt);
      font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
      line-height:1.5;max-width:1180px}
 h1{font-size:21px;margin:0 0 6px}
 h2{font-size:15px;margin:30px 0 10px;color:var(--muted);
    text-transform:uppercase;letter-spacing:1.3px;border-bottom:1px solid var(--line);
    padding-bottom:5px}
 h3{font-size:14px;margin:20px 0 8px;color:#c9d3e2}
 h4,h5,h6{font-size:13px;margin:14px 0 6px}
 code{font-family:ui-monospace,Consolas,"DejaVu Sans Mono",monospace;
      font-size:12px;background:var(--code);border:1px solid var(--line);
      border-radius:4px;padding:1px 4px}
 pre{background:var(--code);border:1px solid var(--line);border-radius:8px;
     padding:14px 16px;overflow:auto;font-size:12px;line-height:1.35;
     font-family:ui-monospace,Consolas,"DejaVu Sans Mono",monospace;color:#cdd6e4}
 table{border-collapse:collapse;width:100%;margin:10px 0 16px;font-size:13px}
 th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;
       vertical-align:top}
 th{background:#1b2029;color:#c9d3e2}
 blockquote{margin:12px 0;padding:10px 16px;border-left:3px solid var(--accent);
            background:#1a1f27;border-radius:0 8px 8px 0;color:#d7deea}
 hr{border:0;border-top:1px solid var(--line);margin:26px 0}
 a{color:#7db1f5}
 ul{margin:8px 0 16px;padding-left:22px}
 li{margin:3px 0}
 .peu{margin-top:34px;padding-top:12px;border-top:1px solid var(--line);
      color:var(--muted);font-size:12px}
"""


def genera_html(md: str) -> str:
    # El primer H1 del .md és el títol; la resta, el cos.
    cos = md_a_cos(md)
    return ("<!DOCTYPE html>\n<html lang=\"ca\">\n<head>\n"
            "<meta charset=\"utf-8\">\n"
            "<title>Auto Chords — Esquema visual de la GUI</title>\n"
            f"<style>{_CSS}</style>\n</head>\n<body>\n{cos}\n"
            f"<div class=\"peu\">{_h.escape(CAPÇALERA)}</div>\n"
            "</body>\n</html>\n")


# --------------------------------------------------------------------------- #
#  SVG (esquema regenerable: els dibuixos de text del .md)
# --------------------------------------------------------------------------- #
def _blocs_codi(md: str) -> list:
    """Els blocs ``` ``` ``` del `.md` (els dibuixos), amb el títol anterior."""
    blocs = []
    lín = md.splitlines()
    titol = ""
    i = 0
    while i < len(lín):
        s = lín[i].strip()
        if s.startswith("#"):
            titol = _pla(s.lstrip("# ").strip())
        if s.startswith("```"):
            i += 1
            buf = []
            while i < len(lín) and not lín[i].strip().startswith("```"):
                buf.append(lín[i])
                i += 1
            blocs.append((titol, buf))
        i += 1
    return blocs


def _esc(t: str) -> str:
    return _h.escape(t)


def _pla(t: str) -> str:
    """Text pla (treu els accents de markdown) per als titols de l'SVG."""
    t = re.sub(r"`([^`]+)`", r"\1", t)
    return t.replace("**", "")


def genera_svg(md: str) -> str:
    titol_md = md.splitlines()[0].lstrip("# ").strip()
    blocs = _blocs_codi(md)
    # amplada = el bloc més ample
    ample_txt = max((max((len(x) for x in b), default=0) for _t, b in blocs),
                    default=60)
    ample_txt = max(ample_txt, len(_pla(titol_md)))
    CW, LH, M = 7.05, 14.5, 18          # amplada de caràcter, alçada de línia, marge
    cap = 54
    ample = int(ample_txt * CW + 2 * M)
    alt = cap + sum(len(b) * LH + 30 for _t, b in blocs) + 34

    p = []
    p.append('<?xml version="1.0" encoding="UTF-8"?>')
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ample} {alt}"'
             f' width="{ample}" height="{alt}"'
             ' font-family="ui-monospace,Consolas,monospace">')
    p.append(f"  <title>{_esc(_pla(titol_md))}</title>")
    p.append(f'  <rect width="{ample}" height="{alt}" fill="#15181d"/>')
    p.append(f'  <text x="{M}" y="26" fill="#e8edf5" font-size="15" font-weight="700"'
             ' font-family="system-ui,sans-serif">'
             f"{_esc(_pla(titol_md))}</text>")
    p.append(f'  <text x="{M}" y="43" fill="#9aa6b8" font-size="11"'
             ' font-family="system-ui,sans-serif">'
             "Font única: docs/ESQUEMA_UI.md · generat (no editar a mà)</text>")
    y = cap
    for titol_bloc, bloc in blocs:
        if titol_bloc:
            p.append(f'  <text x="{M}" y="{y}" fill="#7db1f5" font-size="12"'
                     ' font-weight="700" font-family="system-ui,sans-serif">'
                     f"{_esc(titol_bloc)}</text>")
        y += 16
        alcada = len(bloc) * LH + 14
        p.append(f'  <rect x="{M - 6}" y="{y - 4}" width="{int(ample_txt * CW + 12)}"'
                 f' height="{alcada}" rx="7" fill="#0f1218" stroke="#3a4150"/>')
        for k, linia in enumerate(bloc):
            yy = y + 14 + k * LH
            p.append(f'  <text x="{M}" y="{yy}" fill="#cdd6e4" font-size="12"'
                     f' xml:space="preserve">{_esc(linia)}</text>')
        y += alcada + 22
    p.append(f'  <text x="{M}" y="{alt - 12}" fill="#9aa6b8" font-size="10.5"'
             ' font-family="system-ui,sans-serif">'
             "Esquema regenerable (no editar a mà) — eines/genera_esquema_ui.py</text>")
    p.append("</svg>")
    return "\n".join(p) + "\n"


# --------------------------------------------------------------------------- #
#  main
# --------------------------------------------------------------------------- #
def _llegeix(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in argv
    md = _llegeix(MD)
    html = genera_html(md)
    svg = genera_svg(md)
    if check:
        mal = []
        for path, text in ((HTML, html), (SVG, svg)):
            actual = _llegeix(path) if os.path.exists(path) else ""
            if actual != text:
                mal.append(os.path.relpath(path, ARREL))
        if mal:
            print("DESACTUALITZAT: " + ", ".join(mal)
                  + "  → corre `python3 eines/genera_esquema_ui.py`.")
            return 1
        print("OK: les vistes estan al dia amb docs/ESQUEMA_UI.md")
        return 0
    for path, text in ((HTML, html), (SVG, svg)):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print("escrit:", os.path.relpath(path, ARREL))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
