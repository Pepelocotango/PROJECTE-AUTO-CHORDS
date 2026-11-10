"""Franja Editor del visor (F4).

Extret de `app/visor.py`: actualització i aplicació dels camps de l'editor
d'acords, estructura i tempo/rubato.
"""
import re

from . import bpm_unit as bpm_unit_mod
from . import mapa_tempo, pipeline, tempo_map
from .visor_io import nom_acord

class EditorMixin:
    """Franja Editor del visor."""

    def _actualitza_editor(self):
        """Mostra a la franja Editor l'element seleccionat (o el buit)."""
        k, i = getattr(self, "_ed_kind", None), getattr(self, "_ed_idx", -1)
        # La franja és compartida: cada mode hi posa les seues etiquetes.
        self.ed_nom_lbl.setText("Nom:")
        self.ed_fam_lbl.setText("Família:")
        self.ed_agr_lbl.setVisible(False)
        self.ed_agr.setVisible(False)
        self.ed_n_lbl.setVisible(False)
        self.ed_n.setVisible(False)
        self.ed_rol_lbl.setVisible(False)
        self.ed_ini_lbl.setVisible(False)
        self.ed_ini.setVisible(False)
        self.ed_ini.setEnabled(True)
        self.ed_cb_lbl.setText("≈")
        self.ed_cb_fi_lbl.setVisible(False)
        self.ed_cb_fi.setVisible(False)
        self.ed_cb.setEnabled(True)
        self.ed_bpm_compas.setVisible(False)
        self.ed_bpm_compas.setEnabled(False)
        if k == "tempo" and 0 <= i < len(getattr(self, "tempo_trams", None) or []):
            tr = self.tempo_trams[i]
            ini, fi, bpm = float(tr[0]), float(tr[1]), float(tr[2])
            self.ed_gran.setText(f"TOTAL: {fi - ini:.2f} s")
            self.ed_nom_lbl.setText("BPM:")
            self.ed_nom.setToolTip(
                "BPM del clip (30–350, en "
                f"{bpm_unit_mod.etiqueta(self.bpm_unit).lower()})")
            self.ed_nom.setText(self.bpm_mostra(bpm))
            self.ed_fam_lbl.setText("Compàs:")
            self.ed_fam.setToolTip("Compàs num/den")
            self.ed_fam.setText(f"{int(tr[3])}/{int(tr[4])}")
            self.ed_fam.setVisible(True)
            self.ed_fam_lbl.setVisible(True)
            self.ed_agr_lbl.setVisible(True)
            self.ed_agr.setVisible(True)
            self.ed_agr.setText(getattr(tr, "agrupacio", ""))
            self.ed_agr.setToolTip(
                "Grups de temps del compàs (p. ex. 3+3, 2+2+3). "
                "Buit = automàtic.")
            self.ed_n_lbl.setVisible(True)
            self.ed_n.setVisible(True)
            n_val = getattr(tr, "n", None)
            if n_val is None:
                try:
                    n_val = tempo_map._compassos_del_tram(
                        tr, i, getattr(self, "offset", 0.0))
                except (TypeError, ValueError):
                    n_val = 0.0
            self.ed_n.setText(f"{float(n_val):.3f}")
            self.ed_n.setToolTip(
                "Nombre de compassos. En interiors ha de ser enter; "
                "l'últim/únic pot ser fraccionari.")
            rol = tempo_map.rol_tram(self.tempo_trams, i)
            if tempo_map.es_preroll_tram(
                    self.tempo_trams, i, getattr(self, "offset", 0.0)):
                rol = "preroll"
            self.ed_rol_lbl.setText(f"Rol: {rol}")
            self.ed_rol_lbl.setVisible(True)
            self.ed_cb_lbl.setText("Ini (c):")
            self.ed_cb.setText(self._secs_a_cb(ini))
            self.ed_cb.setEnabled(True)
            self.ed_cb_fi_lbl.setVisible(True)
            self.ed_cb_fi.setVisible(True)
            self.ed_cb_fi.setEnabled(True)
            self.ed_cb_fi.setText(self._secs_a_cb(fi))
            self._ed_cb_ini_text = self.ed_cb.text()
            self._ed_cb_fi_text = self.ed_cb_fi.text()
            self.ed_bpm_compas.setVisible(True)
            self.ed_bpm_compas.setEnabled(True)
            for w in (self.ed_nom, self.ed_fam, self.ed_agr, self.ed_n,
                      self.ed_aplica):
                w.setEnabled(True)
        elif k == "chord" and 0 <= i < len(self.acords):
            t, nom = float(self.acords[i][0]), nom_acord(self.acords[i])
            self.ed_gran.setText(nom)
            self.ed_nom.setText(nom)
            self.ed_nom.setToolTip("Nom de l'acord o lletra de la secció")
            self.ed_fam.setToolTip("Família de la secció (p. ex. N, A, B)")
            self.ed_ini_lbl.setVisible(True)
            self.ed_ini.setVisible(True)
            self.ed_ini.setText(f"{float(t):.3f}")
            self.ed_cb_lbl.setText("≈")
            self.ed_cb.setText(self._secs_a_cb(float(t)))
            self.ed_fam.setVisible(False); self.ed_fam_lbl.setVisible(False)
            self.ed_agr_lbl.setVisible(False); self.ed_agr.setVisible(False)
            self.ed_n_lbl.setVisible(False); self.ed_n.setVisible(False)
            self.ed_rol_lbl.setVisible(False)
            for w in (self.ed_nom, self.ed_ini, self.ed_cb, self.ed_aplica):
                w.setEnabled(True)
        elif k == "section" and 0 <= i < len(self.seccions):
            ini, fi, lletra, fam = self.seccions[i]
            self.ed_gran.setText(f"{lletra} ({fam})")
            self.ed_nom.setText(lletra)
            self.ed_fam.setText(fam)
            self.ed_ini_lbl.setVisible(True)
            self.ed_ini.setVisible(True)
            self.ed_ini.setText(f"{float(ini):.3f}")
            self.ed_cb_lbl.setText("≈")
            self.ed_cb.setText(self._secs_a_cb(float(ini)))
            self.ed_fam.setVisible(True); self.ed_fam_lbl.setVisible(True)
            self.ed_agr_lbl.setVisible(False); self.ed_agr.setVisible(False)
            self.ed_n_lbl.setVisible(False); self.ed_n.setVisible(False)
            self.ed_rol_lbl.setVisible(False)
            for w in (self.ed_nom, self.ed_fam, self.ed_ini, self.ed_cb,
                      self.ed_aplica):
                w.setEnabled(True)
        else:
            self.ed_gran.setText("Selecciona un acord o una secció")
            for w in (self.ed_nom, self.ed_fam, self.ed_agr, self.ed_n,
                      self.ed_ini, self.ed_cb, self.ed_aplica):
                w.setEnabled(False)
            self.ed_bpm_compas.setVisible(False)
            self.ed_bpm_compas.setEnabled(False)
            self.ed_nom.clear(); self.ed_fam.clear(); self.ed_agr.clear()
            self.ed_n.clear()
            self.ed_ini.clear(); self.ed_cb.clear(); self.ed_cb_fi.clear()

    def avis_editor(self, text):
        """Avís de la franja Editor: al log I a la caixa d'informació.

        MAI en silenci: abans, sis camins de `_aplica_editor` tornaven sense dir
        res i el botó «Aplica» semblava no fer res (OC-6/394).
        """
        self.log(f"editor: {text}")
        self.infoMissatge.emit(text)

    def _aplica_editor_tempo(self, i):
        """Aplica BPM, compàs, agrupació i N a un clip de tempo."""
        trams = list(getattr(self, "tempo_trams", None) or [])
        if not (0 <= i < len(trams)):
            self.avis_editor("Aquest clip de tempo ja no existeix.")
            return
        tr = trams[i]
        try:
            bpm = self.bpm_entrada(self.ed_nom.text())
        except (ValueError, TypeError):
            self.avis_editor(f"El BPM «{self.ed_nom.text()}» no és un número.")
            return
        m = re.match(r"^\s*(\d+)\s*[/:]\s*(\d+)\s*$",
                     self.ed_fam.text().strip())
        if not m:
            self.avis_editor(
                f"El compàs «{self.ed_fam.text()}» no és vàlid (num/den).")
            return
        num, den = int(m.group(1)), int(m.group(2))
        if num <= 0 or den <= 0:
            self.avis_editor(
                "El compàs ha de ser num/den positiu; el rubato és només "
                "un flag i no s'escriu 0/0.")
            return
        try:
            bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
            agr = tempo_map.valida_agrupacio(self.ed_agr.text(), num, den)
        except ValueError as e:
            self.avis_editor(str(e))
            return
        try:
            n_val = float(self.ed_n.text().strip().replace(",", "."))
        except (ValueError, TypeError):
            self.avis_editor(f"El N «{self.ed_n.text()}» no és un número.")
            return
        if n_val <= 0:
            self.avis_editor("N ha de ser positiu.")
            return
        n_actual = getattr(tr, "n", None)
        if n_actual is None:
            try:
                n_actual = tempo_map._compassos_del_tram(
                    tr, i, getattr(self, "offset", 0.0))
            except (TypeError, ValueError):
                n_actual = 0.0
        canvi_n = abs(n_val - float(n_actual)) > 1e-3
        if (canvi_n and i != len(trams) - 1
                and abs(n_val - round(n_val)) > 1e-3):
            self.avis_editor(
                "Només l'últim o el tram únic poden tindre N fraccionari.")
            return
        canvi_bpm = (abs(bpm - float(tr.bpm)) > 5e-4
                     or (num, den) != (int(tr.num), int(tr.den)))
        canvi_agr = agr != getattr(tr, "agrupacio", "")

        ini_nou = self._cb_a_secs(self.ed_cb.text())
        fi_nou = self._cb_a_secs(self.ed_cb_fi.text())
        if ini_nou is None or fi_nou is None:
            self.avis_editor(
                "El compàs d'inici o de fi no és vàlid (cal compàs.temps).")
            return
        mou_ini = (self.ed_cb.text().strip()
                   != getattr(self, "_ed_cb_ini_text", None))
        mou_fi = (self.ed_cb_fi.text().strip()
                  != getattr(self, "_ed_cb_fi_text", None))
        if (mou_ini or mou_fi) and (canvi_bpm or canvi_n):
            self.avis_editor(
                "No barreges Ini (c)/Fi (c) amb BPM/N en un mateix Aplica: "
                "canvia els camps o mou els compassos, no les dues coses.")
            return
        if mou_ini and i == 0:
            self.avis_editor("L'inici del primer clip és l'inici de la WAV: "
                             "no es pot moure.")
            return
        if mou_fi and i == len(trams) - 1:
            self.avis_editor("La fi de l'últim clip és la fi de la WAV: "
                             "no es pot moure.")
            return
        if not (canvi_bpm or canvi_n or canvi_agr or mou_ini or mou_fi):
            return

        d = self._durada_wav()
        off = float(getattr(self, "offset", 0.0) or 0.0)
        self._undo_marca()
        try:
            mapa = trams
            if mou_ini:
                mapa = self._mou_frontera_ui(mapa, i, ini_nou, d, off)
            if mapa is None:
                return
            if mou_fi:
                mapa = self._mou_frontera_ui(mapa, i + 1, fi_nou, d, off)
            if mapa is None:
                return
            if mapa is not trams:
                mapa = mapa_tempo.reenganxa_metadades(trams, mapa)
            if canvi_bpm or canvi_n:
                try:
                    mapa = mapa_tempo.recalcula_tram_c(
                        mapa, i, d, offset=off,
                        n=n_val if canvi_n else None, bpm=bpm,
                        num=num, den=den,
                        camp="n" if canvi_n else "bpm")
                except ValueError as e:
                    self.avis_editor(f"Tempo: {e}")
                    return
            if canvi_agr:
                mapa = list(mapa)
                tr2 = mapa[i]
                mapa[i] = mapa_tempo.TramMapa(
                    tr2.ini, tr2.fi, tr2.bpm, tr2.tipus, tr2.compassos,
                    agr, getattr(tr2, "n", None))
            self.aplica_tempo_trams(mapa)
        finally:
            self._undo_commit()
        self._actualitza_editor()

    def _aplica_editor(self):
        """Aplica els canvis de la franja Editor al model (amb undo).

        Tots els camins que NO apliquen donen feedback visible (`avis_editor`):
        un botó que no fa res i no diu per què és un defecte.
        """
        k, i = getattr(self, "_ed_kind", None), getattr(self, "_ed_idx", -1)
        if k is None or i < 0:
            self.avis_editor("Selecciona un acord, una secció o un clip de "
                             "tempo (clic al clip) abans d'aplicar.")
            return
        if k == "tempo":
            self._aplica_editor_tempo(i)
            return
        # Multi-selecció del MATEIX tipus → renom EN BLOC (estil fulla de càlcul):
        # el camp Nom s'aplica a TOTS els seleccionats del tipus actiu. L'INICI
        # NO s'aplica en bloc (no s'han d'apilar tots els clips al mateix instant).
        _n = len(self.acords) if k == "chord" else len(self.seccions)
        idxs = sorted({j for (kk, j) in self.timeline.selected_keys()
                       if kk == k and 0 <= j < _n})
        if len(idxs) >= 2:
            nom = self.ed_nom.text().strip()
            if k == "chord":
                if not self._renomena_acords(idxs, nom):
                    self.avis_editor("Renom en bloc: nom o canvi no vàlid.")
            else:
                if not self._renomena_seccions(idxs, nom or self.seccions[i][2]):
                    self.avis_editor("Renom en bloc: lletra o canvi no vàlid.")
            return
        # inici: prioritza el camp de segons; si esta buit, el de compas.beat
        txt = self.ed_ini.text().strip()
        if txt:
            try:
                ini = float(txt.replace(",", "."))
            except ValueError:
                self.avis_editor(f"L'inici «{txt}» no és un número vàlid.")
                return
        else:
            ini = self._cb_a_secs(self.ed_cb.text())
            if ini is None:
                self.avis_editor(f"El compàs «{self.ed_cb.text()}» no és vàlid.")
                return
        nom = self.ed_nom.text().strip()
        if k == "chord":
            if not nom or not (0 <= i < len(self.acords)):
                self.avis_editor("Cal un nom, i l'acord ha d'existir (potser "
                                 "l'has esborrat).")
                return
            # Mateix sanejat que l'alta i l'export (coherència nom CSV ↔ WAV).
            nom = pipeline.saneja_nom_acord(nom)
            if not nom:
                self.avis_editor("El nom de l'acord no és vàlid.")
                return
            # Si l'inici NO s'ha tocat, conserva el valor INTERN de precisió
            # completa: l'editor només en mostra 2 decimals i re-escriure'l
            # arrodonit podria fer que l'acord "xoqui" amb el veí.
            if abs(ini - float(self.acords[i][0])) <= 0.005:
                ini = float(self.acords[i][0])
            self._undo_marca()
            nova = list(self.acords)
            _a = nova[i]
            nova[i] = pipeline.Clip(ini, float(_a[1]),
                                    (nom,) + tuple(_a[2][1:]))
            try:
                self.acords = self._normalitza_acords(nova)
            except ValueError as e:
                self.avis_editor(f"canvi invalid ({e})")
                return
            self._undo_commit()
            self.timeline.set_data(self.acords, self.seccions)
            self._desa_i_regenera()
            self.log(f"editor: acord {i} -> {nom} @ {ini:.3f}s")
            # Si s'ha mogut l'inici, l'acord pot haver canviat de fila → re-localitza.
            i = next((j for j, a in enumerate(self.acords)
                      if abs(float(a[0]) - ini) <= 1e-6
                      and nom_acord(a) == nom), i)
        else:
            if not (0 <= i < len(self.seccions)):
                self.avis_editor("Aquesta secció ja no existeix (potser l'has "
                                 "esborrada).")
                return
            _ini, fi, _ll, _f = self.seccions[i]
            # (mateix motiu que als acords) si l'inici no s'ha tocat, conserva
            # la precisió completa -> evita falsos solapaments amb la secció
            # anterior, que acaba EXACTAMENT aquí.
            if abs(ini - _ini) <= 0.005:
                ini = _ini
            lletra = nom or self.seccions[i][2]
            fam = self.ed_fam.text().strip() or self.seccions[i][3]
            self._undo_marca()
            nova = list(self.seccions)
            nova[i] = (ini, max(ini + self.MIN_SECCIO_S, fi), lletra, fam)
            try:
                # Manté la contigüitat (#2) com el drag del timeline.
                nova = self._contiguitat_seccions(nova, i)
                self.seccions = self._normalitza_seccions(nova)
            except ValueError as e:
                self.avis_editor(f"canvi invalid ({e})")
                return
            self._undo_commit()
            self.timeline.set_data(self.acords, self.seccions)
            self._regenera_abc_des_de_totes_les_seccions("editat des de l'editor")
            self.log(f"editor: seccio {i} -> {lletra} @ {ini:.3f}s")
            i = next((j for j, s in enumerate(self.seccions)
                      if abs(float(s[0]) - ini) <= 1e-6 and s[2] == lletra), i)
        self._refresca_post_edicio(k, i)

    def posa_nom_editor(self, nom):
        """Posa `nom` a la casella «Nom» de la franja Editor (**sense aplicar**).

        El fa servir el panell «Tipus d'acord»: clicar un tipus només **omple**
        la casella; l'usuari decideix quan prem «Aplica» (o Enter).
        """
        self.ed_nom.setText(str(nom or ""))
        self.ed_nom.setFocus()
        self.ed_nom.selectAll()
        self.avis_editor(f"tipus d'acord: «{nom}» llest per aplicar")

    def _focus_editor(self, kind, idx):
        """Selecciona l'element i enganxa el focus a la franja Editor
        (en comptes d'obrir cap finestra emergent)."""
        self._ed_kind, self._ed_idx = kind, idx
        self.timeline.select_clip(kind, idx)
        if kind == "chord":
            self._centra_fila_llista(self.llista_ac, idx)
        elif kind == "section":
            self._centra_fila_llista(self.llista_ab, idx)
        elif kind == "tempo":
            self._centra_fila_llista(self.llista_tempo, idx)
        self._actualitza_editor()
        self.ed_nom.setFocus()
        self.ed_nom.selectAll()
