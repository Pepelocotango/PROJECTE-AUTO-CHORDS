"""Franja Editor del visor (F4).

Extret de `app/visor.py`: actualització i aplicació dels camps de l'editor
d'acords, estructura i tempo/rubato.
"""
import re

from . import bpm_unit as bpm_unit_mod
from . import icones, pipeline, rubato as rubato_mod, tempo_map
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
        self.ed_ini.setEnabled(True)
        self.ed_cb.setEnabled(True)
        self.ed_fi_lbl.setVisible(False)
        self.ed_fi.setVisible(False)
        self.ed_fi.setEnabled(False)
        self.ed_bpm_compas.setVisible(False)
        self.ed_bpm_compas.setEnabled(False)
        if k == "tempo" and 0 <= i < len(getattr(self, "tempo_trams", None) or []):
            tr = self.tempo_trams[i]
            ini, fi, bpm = float(tr[0]), float(tr[1]), float(tr[2])
            rubato = getattr(tr, "tipus", None) == "rubato"
            self.ed_icona.setPixmap(icones.ico("metronome", 20).pixmap(20, 20))
            self.ed_gran.setText(
                f"Tempo · {fi - ini:.2f} s"
                + (" · rubato (derivat)" if rubato else ""))
            self.ed_nom_lbl.setText("BPM:")
            self.ed_nom.setToolTip(
                "BPM del clip (30–350, en "
                f"{bpm_unit_mod.etiqueta(self.bpm_unit).lower()})"
                + (" · derivat del rubato" if rubato else ""))
            self.ed_nom.setText(self.bpm_mostra(bpm))
            self.ed_fam_lbl.setText("Compàs:")
            if rubato:
                self.ed_fam.setToolTip(
                    "Seqüència derivada del rubato (no editable)")
                self.ed_fam.setText(rubato_mod.presenta_compassos(tr.compassos))
            else:
                self.ed_fam.setToolTip("Compàs num/den")
                self.ed_fam.setText(f"{int(tr[3])}/{int(tr[4])}")
            self.ed_fam.setVisible(True)
            self.ed_fam_lbl.setVisible(True)
            if not rubato:
                self.ed_agr_lbl.setVisible(True)
                self.ed_agr.setVisible(True)
                self.ed_agr.setText(getattr(tr, "agrupacio", ""))
                self.ed_agr.setToolTip(
                    "Grups de temps del compàs (p. ex. 3+3, 2+2+3). "
                    "Buit = automàtic.")
            self.ed_ini.setText(f"{ini:.3f}")
            self.ed_cb.setText(self._secs_a_cb(ini))
            self.ed_fi_lbl.setVisible(True)
            self.ed_fi.setVisible(True)
            self.ed_fi.setText(f"{fi:.3f}")
            self.ed_cb.setEnabled(False)
            self.ed_bpm_compas.setVisible(True)
            self.ed_bpm_compas.setEnabled(not rubato)
            # Fase 3.1: els rubatos es mostren però no s'editen encara. La
            # frontera editable arribarà amb les accions de la fase 3.2.
            for w in (self.ed_nom, self.ed_fam, self.ed_agr, self.ed_ini,
                      self.ed_fi, self.ed_aplica):
                w.setEnabled(not rubato)
            if rubato:
                self.ed_fi.setEnabled(False)
        elif k == "chord" and 0 <= i < len(self.acords):
            t, nom = float(self.acords[i][0]), nom_acord(self.acords[i])
            self.ed_icona.setPixmap(icones.ico("music", 20).pixmap(20, 20))
            self.ed_gran.setText(nom)
            self.ed_nom.setText(nom)
            self.ed_nom.setToolTip("Nom de l'acord o lletra de la secció")
            self.ed_fam.setToolTip("Família de la secció (p. ex. N, A, B)")
            self.ed_ini.setText(f"{float(t):.3f}")
            self.ed_cb.setText(self._secs_a_cb(float(t)))
            self.ed_fam.setVisible(False); self.ed_fam_lbl.setVisible(False)
            self.ed_agr_lbl.setVisible(False); self.ed_agr.setVisible(False)
            for w in (self.ed_nom, self.ed_ini, self.ed_cb, self.ed_aplica):
                w.setEnabled(True)
        elif k == "section" and 0 <= i < len(self.seccions):
            ini, fi, lletra, fam = self.seccions[i]
            self.ed_icona.setPixmap(icones.ico("piano", 20).pixmap(20, 20))
            self.ed_gran.setText(f"{lletra} ({fam})")
            self.ed_nom.setText(lletra)
            self.ed_fam.setText(fam)
            self.ed_ini.setText(f"{float(ini):.3f}")
            self.ed_cb.setText(self._secs_a_cb(float(ini)))
            self.ed_fam.setVisible(True); self.ed_fam_lbl.setVisible(True)
            self.ed_agr_lbl.setVisible(False); self.ed_agr.setVisible(False)
            for w in (self.ed_nom, self.ed_fam, self.ed_ini, self.ed_cb,
                      self.ed_aplica):
                w.setEnabled(True)
        else:
            self.ed_icona.clear()
            self.ed_gran.setText("Selecciona un acord o una secció")
            for w in (self.ed_nom, self.ed_fam, self.ed_agr, self.ed_ini,
                      self.ed_cb, self.ed_aplica):
                w.setEnabled(False)
            self.ed_bpm_compas.setVisible(False)
            self.ed_bpm_compas.setEnabled(False)
            self.ed_nom.clear(); self.ed_fam.clear(); self.ed_agr.clear()
            self.ed_ini.clear(); self.ed_cb.clear()

    def avis_editor(self, text):
        """Avís de la franja Editor: al log I a la caixa d'informació.

        MAI en silenci: abans, sis camins de `_aplica_editor` tornaven sense dir
        res i el botó «Aplica» semblava no fer res (OC-6/394).
        """
        self.log(f"editor: {text}")
        self.infoMissatge.emit(text)

    def _aplica_editor_tempo(self, i):
        """Aplica BPM/compàs de la franja Editor a un clip de tempo.

        El rubato ja no es crea amb `0/0`: es mostra derivat i de només
        lectura. Ací només s'editen clips normals (`num/den`).
        """
        trams = list(getattr(self, "tempo_trams", None) or [])
        if not (0 <= i < len(trams)):
            self.avis_editor("Aquest clip de tempo ja no existeix.")
            return
        if getattr(trams[i], "tipus", None) == "rubato":
            self.avis_editor(
                "Els valors d'un rubato són derivats; fes servir les accions "
                "«Converteix a normal» o «Marca el rang A–B».")
            return
        txt = self.ed_nom.text().strip().replace(",", ".")
        try:
            bpm = self.bpm_entrada(txt)
        except (ValueError, TypeError):
            self.avis_editor(f"El BPM «{self.ed_nom.text()}» no és un número.")
            return
        txt_c = self.ed_fam.text().strip().lower()
        if txt_c in ("", "—", "-", "segons"):
            num = den = 0
        else:
            m = re.match(r"^\s*(\d+)\s*[/:]\s*(\d+)\s*$", txt_c)
            if not m:
                self.avis_editor(
                    f"El compàs «{self.ed_fam.text()}» no és vàlid "
                    "(num/den).")
                return
            num, den = int(m.group(1)), int(m.group(2))
        if num == 0 and den == 0:
            self.avis_editor(
                "El rubato no es crea escrivint 0/0; fes servir «Marca com a "
                "rubato» o «Converteix a rubato» (fase 3.2).")
            return
        try:
            bpm, num, den = tempo_map.valida_tempo(bpm, num, den)
            agr = tempo_map.valida_agrupacio(self.ed_agr.text(), num, den)
        except ValueError as e:
            self.avis_editor(str(e))
            return
        # ---- Inici / Fi (s): moure la FRONTERA (§13.6) --------------------
        ini, fi = float(trams[i][0]), float(trams[i][1])
        bpm0, num0, den0 = (float(trams[i][2]), int(trams[i][3]),
                            int(trams[i][4]))
        agr0 = getattr(trams[i], "agrupacio", "")
        canvi_bpm = (abs(bpm - bpm0) > 5e-4
                     or (num, den) != (num0, den0))
        canvi_agr = agr != agr0
        ini_nou, fi_nou = ini, fi
        for camp, actual in ((self.ed_ini, ini), (self.ed_fi, fi)):
            txt_t = camp.text().strip().replace(",", ".")
            if not txt_t:
                continue
            try:
                val = float(txt_t)
            except ValueError:
                self.avis_editor(f"«{camp.text()}» no és un temps vàlid.")
                return
            if camp is self.ed_ini:
                ini_nou = val
            else:
                fi_nou = val
        mou_ini = abs(ini_nou - ini) > 5e-3
        mou_fi = abs(fi_nou - fi) > 5e-3
        # El principi de la WAV i la seua fi no es poden moure: es rebutja i
        # s'avisa (no s'ha d'aplicar res més del formulari).
        if mou_ini and i == 0:
            self.avis_editor("L'inici del primer clip és l'inici de la WAV: "
                             "no es pot moure.")
            return
        if mou_fi and i == len(trams) - 1:
            self.avis_editor("La fi de l'últim clip és la fi de la WAV: "
                             "no es pot moure.")
            return
        d = self._durada_wav()
        off = float(getattr(self, "offset", 0.0) or 0.0)
        self._undo_marca()
        mapa = trams
        if mou_ini:
            mapa = self._mou_frontera_ui(mapa, i, ini_nou, d, off)
        if mapa is None:
            self._undo_commit()
            return
        if mou_fi:
            mapa = self._mou_frontera_ui(mapa, i + 1, fi_nou, d, off)
        if mapa is None:
            self._undo_commit()
            return
        if mapa is not trams:
            mapa = self._preserva_rubato(trams, mapa)
            self.aplica_tempo_trams(mapa)
        # Després de moure fronteres, si l'usuari HA CANVIAT el BPM/compàs al
        # formulari, manen (re-tempo local sobre el tram ja re-situat). Si no
        # els ha tocat, el BPM que hi ha és el que ha derivat la frontera: no
        # se li ha de tornar a imposar el valor vell (desfaria el moviment).
        if canvi_bpm or canvi_agr:
            self.edita_tempo_objectiu(i, bpm, num, den, agrupacio=agr)
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
