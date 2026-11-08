#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera el mapa de funcionalitats en ODF (docs/FUNCIONALITATS_AUTO_CHORDS.ods).

La font de veritat és `eines/funcionalitats_dades.json`: un fitxer de text amb
una fila per línia (fàcil de revisar i de versionar). Este script construeix
l'ODS, les fulles derivades (`Resum` i `Mapa mental`) i, amb `--check`,
comprova que l'ODS versionat estiga al dia.

Ús:
    .venv/bin/python eines/genera_funcionalitats.py
    .venv/bin/python eines/genera_funcionalitats.py --check

El guardat és **determinista**: el ZIP es reescriu amb dates fixes. Així,
regenerar sense canvis no produeix cap diff binari.
"""
import argparse
import json
import os
import re
import sys
import zipfile
from collections import OrderedDict

from odf import teletype
from odf.opendocument import OpenDocumentSpreadsheet, load
from odf.style import (ParagraphProperties, Style, TableCellProperties,
                       TableColumnProperties, TextProperties)
from odf.table import (DatabaseRange, DatabaseRanges, Table, TableCell,
                       TableColumn, TableHeaderRows, TableRow)
from odf.text import P

BASE = os.path.dirname(os.path.abspath(__file__))
ARREL = os.path.dirname(BASE)
FONT = os.path.join(BASE, "funcionalitats_dades.json")
DESTI = os.path.join(ARREL, "docs", "FUNCIONALITATS_AUTO_CHORDS.ods")

# Columnes de cada full (les derivades es construeixen a `taules()`).
CAPÇALERES = {
    "Resum": ["Àrea", "Funcionalitats", "Amb menú", "Amb botó/control",
              "Amb drecera", "Amb contextual", "Amb ratolí", "Amb diàleg",
              "Amb automatisme"],
    "Llegenda": ["Apartat", "Contingut"],
    "Mapa mental": ["Nivell", "Contingut", "Superfície", "Drecera", "Què fa"],
    "Funcionalitats": ["Àrea", "Grup", "Funcionalitat / acció",
                       "Què fa exactament", "Superfícies (resum)",
                       "Menú principal", "Botó / barra / camp",
                       "Drecera teclat", "Menú contextual",
                       "Ratolí / timeline", "Finestra emergent",
                       "Disponible quan", "Notes / límits"],
    "Menús": ["Menú", "Acció", "Drecera", "Què fa", "Disponible"],
    "Botons i controls": ["Ubicació", "Control", "Tipus", "Acció", "Drecera",
                          "Disponible"],
    "Dreceres i gestos": ["Grup", "Combinació / gest", "On", "Acció", "Notes"],
    "Finestres i diàlegs": ["Finestra", "Quan apareix", "Controls / accions",
                            "Resultat"],
    "Flux de treball": ["Pas", "Objectiu", "Accions", "On", "Resultat"],
}

AMPLE = {
    "Resum": ["4.2cm", "2.2cm", "1.6cm", "2.4cm", "1.9cm", "2.1cm", "1.9cm",
              "1.8cm", "2.4cm"],
    "Llegenda": ["3.2cm", "22.0cm"],
    "Mapa mental": ["2.7cm", "8.5cm", "5.0cm", "2.8cm", "10.5cm"],
    "Funcionalitats": ["2.6cm", "2.6cm", "4.6cm", "8.2cm", "4.0cm", "4.6cm",
                       "4.8cm", "2.6cm", "4.4cm", "4.6cm", "4.6cm", "3.4cm",
                       "5.2cm"],
    "Menús": ["2.6cm", "10.0cm", "2.6cm", "12.0cm", "5.0cm"],
    "Botons i controls": ["4.0cm", "5.4cm", "3.4cm", "12.0cm", "3.0cm",
                          "5.0cm"],
    "Dreceres i gestos": ["2.8cm", "5.2cm", "3.2cm", "10.5cm", "8.0cm"],
    "Finestres i diàlegs": ["5.8cm", "8.0cm", "12.0cm", "6.5cm"],
    "Flux de treball": ["1.4cm", "5.4cm", "11.0cm", "6.0cm", "8.0cm"],
}


def carrega():
    """Llig i valida la font JSON."""
    with open(FONT, encoding="utf-8") as f:
        d = json.load(f)
    for clau in ("funcionalitats", "menus", "botons", "dreceres", "dialegs",
                 "flux", "llegenda"):
        if clau not in d:
            raise SystemExit(f"Falta la clau «{clau}» a {FONT}")
    n = len(CAPÇALERES["Funcionalitats"])
    for i, fila in enumerate(d["funcionalitats"], 1):
        if len(fila) != n:
            raise SystemExit(
                f"funcionalitats línia {i}: {len(fila)} columnes (esperades {n})")
    for clau, full in (("menus", "Menús"), ("botons", "Botons i controls"),
                       ("dreceres", "Dreceres i gestos"),
                       ("dialegs", "Finestres i diàlegs"),
                       ("flux", "Flux de treball"),
                       ("llegenda", "Llegenda")):
        n = len(CAPÇALERES[full])
        for i, fila in enumerate(d[clau], 1):
            if len(fila) != n:
                raise SystemExit(
                    f"{clau} línia {i}: {len(fila)} columnes (esperades {n})")
    return d


def _resum(funcionalitats):
    """Full «Resum»: recompte per àrea i superfícies."""
    per_area = OrderedDict()
    for fila in funcionalitats:
        per_area.setdefault(fila[0], []).append(fila)
    files = []
    for area, files_area in per_area.items():
        files.append([
            area, len(files_area),
            sum(1 for x in files_area if x[5]),
            sum(1 for x in files_area if x[6]),
            sum(1 for x in files_area if x[7]),
            sum(1 for x in files_area if x[8]),
            sum(1 for x in files_area if x[9]),
            sum(1 for x in files_area if x[10]),
            sum(1 for x in files_area
                if "Automàtic" in x[4] or "Automàtic" in x[11]),
        ])
    files.append([
        "TOTAL", len(funcionalitats),
        sum(1 for x in funcionalitats if x[5]),
        sum(1 for x in funcionalitats if x[6]),
        sum(1 for x in funcionalitats if x[7]),
        sum(1 for x in funcionalitats if x[8]),
        sum(1 for x in funcionalitats if x[9]),
        sum(1 for x in funcionalitats if x[10]),
        sum(1 for x in funcionalitats
            if "Automàtic" in x[4] or "Automàtic" in x[11]),
    ])
    return files


def _mapa_mental(funcionalitats):
    """Full «Mapa mental»: àrea → grup → acció."""
    grups = OrderedDict()
    for fila in funcionalitats:
        grups.setdefault(fila[0], OrderedDict()).setdefault(
            fila[1], []).append(fila)
    files = []
    for area, grps in grups.items():
        files.append(["1 · ÀREA", area, "", "", ""])
        for grup, files_grup in grps.items():
            files.append(["2 · GRUP", grup, "", "", ""])
            for fila in files_grup:
                files.append(["3 · ACCIÓ", fila[2], fila[4], fila[7], fila[3]])
    return files


def taules(d):
    """Retorna les taules en l'orde de fulls: (nom, files)."""
    return [
        ("Resum", _resum(d["funcionalitats"])),
        ("Llegenda", d["llegenda"]),
        ("Mapa mental", _mapa_mental(d["funcionalitats"])),
        ("Funcionalitats", d["funcionalitats"]),
        ("Menús", d["menus"]),
        ("Botons i controls", d["botons"]),
        ("Dreceres i gestos", d["dreceres"]),
        ("Finestres i diàlegs", d["dialegs"]),
        ("Flux de treball", d["flux"]),
    ]


def _afegeix_estil(doc, name, bg=None, bold=False, color=None, size="9pt",
                   wrap=True, border="0.3pt solid #c9d1d9"):
    s = Style(name=name, family="table-cell")
    kw = {"wrapoption": "wrap" if wrap else "none",
          "padding": "0.05cm", "verticalalign": "top", "border": border}
    if bg:
        kw["backgroundcolor"] = bg
    s.addElement(TableCellProperties(**kw))
    tx = TextProperties(fontsize=size)
    if bold:
        tx.setAttribute("fontweight", "bold")
    if color:
        tx.setAttribute("color", color)
    s.addElement(tx)
    doc.automaticstyles.addElement(s)
    return name


def _estils(doc):
    hdr = _afegeix_estil(doc, "hdr", bg="#1f3b57", bold=True,
                         color="#ffffff", size="9.5pt")
    cell = _afegeix_estil(doc, "cell")
    alt = _afegeix_estil(doc, "alt", bg="#f2f5f8")
    note = _afegeix_estil(doc, "note", bg="#fff8e1")
    area = _afegeix_estil(doc, "area", bg="#dce9f5", bold=True,
                          color="#14324f", size="10pt")
    group = _afegeix_estil(doc, "group", bg="#eef4fa", bold=True,
                           color="#1f3b57")
    pcell = Style(name="pcell", family="paragraph")
    pcell.addElement(ParagraphProperties(margin="0cm", lineheight="115%"))
    doc.automaticstyles.addElement(pcell)
    phdr = Style(name="phdr", family="paragraph")
    phdr.addElement(ParagraphProperties(margin="0cm"))
    doc.automaticstyles.addElement(phdr)
    return {"hdr": hdr, "cell": cell, "alt": alt, "note": note,
            "area": area, "group": group, "pcell": pcell, "phdr": phdr}


def _amplada(doc, name, w):
    s = Style(name=name, family="table-column")
    s.addElement(TableColumnProperties(columnwidth=w))
    doc.automaticstyles.addElement(s)
    return s


def _cella(text, style, pstyle):
    c = TableCell(stylename=style, valuetype="string")
    c.addElement(P(stylename=pstyle, text="" if text is None else str(text)))
    return c


def _afegeix_taula(doc, est, nom, files):
    """Crea una fulla amb capçalera repetida i files de text."""
    t = Table(name=nom)
    for i, w in enumerate(AMPLE[nom]):
        t.addElement(TableColumn(stylename=_amplada(doc, f"{nom}_c{i}", w)))
    tr = TableRow()
    for h in CAPÇALERES[nom]:
        tr.addElement(_cella(h, est["hdr"], est["phdr"]))
    hr = TableHeaderRows()
    hr.addElement(tr)
    t.addElement(hr)
    for ri, fila in enumerate(files):
        st = est["cell"]
        if nom == "Llegenda":
            st = est["note"]
        elif nom == "Mapa mental" and fila and fila[0] == "1 · ÀREA":
            st = est["area"]
        elif nom == "Mapa mental" and fila and fila[0] == "2 · GRUP":
            st = est["group"]
        elif nom == "Resum" and fila and fila[0] == "TOTAL":
            st = est["area"]
        elif ri % 2:
            st = est["alt"]
        tr = TableRow()
        for val in fila:
            tr.addElement(_cella(val, st, est["pcell"]))
        t.addElement(tr)
    doc.spreadsheet.addElement(t)
    if nom == "Funcionalitats":
        drs = DatabaseRanges()
        drs.addElement(DatabaseRange(
            name="FiltreFuncionalitats",
            targetrangeaddress=f"Funcionalitats.A1:M{len(files) + 1}",
            containsheader="true", displayfilterbuttons="true"))
        doc.spreadsheet.addElement(drs)


def _normalitza_zip(path):
    """Reescriu el ZIP amb dates fixes (guardat determinista)."""
    tmp = path + ".tmp"
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w") as zout:
        noms = ["mimetype"] + sorted(
            n for n in zin.namelist() if n != "mimetype")
        for nom in noms:
            dades = zin.read(nom)
            if nom == "meta.xml":
                # odfpy hi escriu la seua versió: la fixem perquè el fitxer
                # no canvie si s'actualitza la llibreria.
                text = dades.decode("utf-8")
                text = re.sub(
                    r"<meta:generator>.*?</meta:generator>",
                    "<meta:generator>AUTO CHORDS · funcionalitats"
                    "</meta:generator>", text)
                dades = text.encode("utf-8")
            info = zipfile.ZipInfo(nom, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = (zipfile.ZIP_STORED if nom == "mimetype"
                                  else zipfile.ZIP_DEFLATED)
            info.external_attr = 0o600 << 16
            zout.writestr(info, dades)
    os.replace(tmp, path)


def genera(desti=DESTI, comprova=False):
    d = carrega()
    files = taules(d)
    if comprova:
        return _comprova(desti, files)
    doc = OpenDocumentSpreadsheet()
    est = _estils(doc)
    for nom, rows in files:
        _afegeix_taula(doc, est, nom, rows)
    os.makedirs(os.path.dirname(desti), exist_ok=True)
    doc.save(desti)
    _normalitza_zip(desti)
    return 0


def _llegeix_ods(path):
    """Llig un ODS com a {fulla: [[cel·la, ...], ...]}."""
    doc = load(path)
    out = OrderedDict()
    for t in doc.spreadsheet.getElementsByType(Table):
        files = []
        for tr in t.getElementsByType(TableRow):
            vals = [teletype.extractText(c)
                    for c in tr.getElementsByType(TableCell)]
            while vals and vals[-1] == "":
                vals.pop()
            files.append(vals)
        out[t.getAttribute("name")] = files
    return out


def _esperat(files):
    out = OrderedDict()
    for nom, rows in files:
        cap = [str(x) for x in CAPÇALERES[nom]]
        files_ = [cap] + [[str(x) for x in fila] for fila in rows]
        for fila in files_:
            while fila and fila[-1] == "":
                fila.pop()
        out[nom] = files_
    return out


def _comprova(desti, files):
    if not os.path.isfile(desti):
        print(f"ERROR: no trobo {desti}; executa «make docs».")
        return 1
    esperat = _esperat(files)
    actual = _llegeix_ods(desti)
    if list(esperat) != list(actual):
        print("ERROR: les fulles no coincideixen.")
        print("  esperades:", ", ".join(esperat))
        print("  trobades: ", ", ".join(actual))
        return 1
    for nom in esperat:
        a, b = esperat[nom], actual[nom]
        if len(a) != len(b):
            print(f"ERROR: {nom}: {len(b)} files (esperades {len(a)}).")
            return 1
        for i, (fa, fb) in enumerate(zip(a, b), 1):
            if fa != fb:
                print(f"ERROR: {nom}, fila {i} desactualitzada.")
                print(f"  esperat: {fa}")
                print(f"  trobat:  {fb}")
                return 1
    print(f"OK: {os.path.relpath(desti, ARREL)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Genera el mapa de funcionalitats en ODF.")
    ap.add_argument("--check", action="store_true",
                    help="comprova que l'ODS versionat estiga al dia")
    args = ap.parse_args(argv)
    return genera(comprova=args.check)


if __name__ == "__main__":
    sys.exit(main())
