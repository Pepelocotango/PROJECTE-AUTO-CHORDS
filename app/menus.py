"""Menús, dreceres i ajuda de la finestra (F3).

Extret de `app/main.py`. `MenusMixin` assumeix que la classe que l'hereta té
els slots i els widgets que els menús connecten.
"""
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QAction, QMessageBox

from . import __version__

class MenusMixin:
    """Menús, dreceres i diàlegs d'ajuda."""

    def _act(self, menu, text, shortcut, slot, checkable=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def _crea_menus(self):
        mb = self.menuBar()
        # --- Fitxer ---
        m = mb.addMenu("&Fitxer")
        self._act(m, "Obre àudio…", "Ctrl+O", self.tria_wav)
        self._act(m, "Obre projecte…", "", self._obre_projecte)
        self._act(m, "Obre recent…", "", self._obre_recent)
        m.addSeparator()
        self._act(m, "Desa", "Ctrl+S", self._desa_projecte)
        self._act(m, "Desa com…", "", self._desa_projecte_com)
        self._act(m, "Desa una còpia…", "", self._desa_copia)
        self._act(m, "Reverteix", "", self._reverteix)
        m.addSeparator()
        self.a_exporta = self._act(m, "Exporta WAV's…", "Ctrl+E",
                                   self.exporta)
        self.a_exporta_audio = self._act(
            m, "Exporta àudio…", "", self._exporta_audio_ui)
        self.a_exporta_audio.setStatusTip(
            "Exporta la còpia WAV de treball (ja editada) a WAV, MP3, FLAC, "
            "AAC/M4A, OGG o Opus.")
        self.a_exporta_audio.setEnabled(False)
        self.a_exporta_part = self._act(m, "Exporta la partitura…", "",
                                        self.exporta_partitura_ara)
        self.a_exporta_part.setStatusTip(
            "Genera la partitura (xifrat). El MusicXML sempre; el PDF i el "
            "MSCZ NOMÉS si hi ha MuseScore instal·lat.")
        self.a_exporta_part.setToolTip(self.a_exporta_part.statusTip())
        self.a_exporta.setEnabled(False)
        self.a_exporta_part.setEnabled(False)
        m.addAction(self.amb_part)      # Inclou la partitura (commutable)
        self._act(m, "Obre la carpeta de sortida", "", self.obre_carpeta)
        m.addSeparator()
        self._act(m, "Surt", "Ctrl+Q", self.close)
        # --- Edita ---
        m = mb.addMenu("&Edita")
        self._act(m, "Desfer", "Ctrl+Z", self._undo_visor)
        self._act(m, "Refer", "Ctrl+Y", self._redo_visor)
        self._act(m, "Refer (alternatiu)", "", self._redo_visor)
        m.addSeparator()
        self._act(m, "Retalla", "Ctrl+X", self._retalla_clips)
        self._act(m, "Copia", "Ctrl+C", self._copia_clips)
        self._act(m, "Enganxa", "Ctrl+V", self._enganxa_clips)
        m.addSeparator()
        self._act(m, "Afegeix acord…", "", self._afegeix_acord_ui)
        self._act(m, "Afegeix secció…", "", self._afegeix_seccio_ui)
        # A2 + regla d'or #11: en un model saturat (els clips cobreixen tota la
        # WAV) no hi ha forat per afegir-ne: cal PARTIR el clip que hi ha al
        # cursor — MATEIXA acció per a acord i secció.
        self._act(m, "Parteix l'acord al cursor…", "", self._parteix_acord_ui)
        self._act(m, "Parteix la secció al cursor…", "", self._parteix_seccio_ui)
        self._act(m, "Afegeix tram de tempo/compàs…", "",
                  self._afegeix_tram_ui)
        self._act(m, "Parteix el tram al cursor…", "", self._parteix_tram_ui)
        m.addSeparator()
        self._act(m, "Elimina element", "Del", self._elimina_element)
        self._act(m, "Duplica element", "Ctrl+D", self._duplica_element)
        self._act(m, "Reanomena element", "F2", self._renomena_element)
        self._act(m, "Troba i reemplaça…", "Ctrl+H", self._troba_i_reemplaca_ui)
        m.addSeparator()
        self._act(m, "Parteix el tempo al cursor", "",
                  self._talla_tempo_cursor)
        self._act(m, "Parteix l'estructura al cursor", "",
                  self._talla_estructura_cursor)
        self._act(m, "Parteix tempo i estructura al cursor", "",
                  self._talla_tempo_i_estructura_cursor)
        m.addSeparator()
        self._act(m, "Paràmetres…", "", self._focus_parametres)
        self._act(m, "Retard global de reproducció…", "",
                  self._ajusta_latencia_cursor)
        # --- Selecciona ---
        m = mb.addMenu("&Selecciona")
        self._act(m, "Selecciona l'acord del cursor", "", self._sel_acord_cursor)
        self._act(m, "Selecciona la secció del cursor", "", self._sel_seccio_cursor)
        self._act(m, "Selecciona el tram de tempo/compàs del cursor", "",
                  self._sel_tram_cursor)
        m.addSeparator()
        self._act(m, "Loop a la selecció", "L", self._loop_seleccio)
        self._act(m, "Marca inici de loop (A)", "Ctrl+[", self._marca_A_visor)
        self._act(m, "Marca fi de loop (B)", "Ctrl+]", self._marca_B_visor)
        self._act(m, "Neteja el loop", "", self._neteja_loop)
        self._act(m, "Activa/desactiva loop", "", self._loop_visor)
        m.addSeparator()
        # Eina del timeline i abast del rang (vegeu `timeline.set_tool`,
        # `keys_dins_marc` i `extend_selection`).
        self.a_eina_marc = self._act(
            m, "Eina de marc (rubber-band)", "", self._toggle_eina_marc,
            checkable=True)
        self.a_eina_marc.setToolTip(
            "Arrossegar pel timeline dibuixa un rectangle: queda seleccionat "
            "tot el que hi SONA a dins, i només de les pistes que cobreixi. "
            "El rectangle desapareix en deixar anar.")
        # (No hi ha opció de «selecció creuada»: el rang de Shift+clic és sempre
        # del carril clicat, i per agafar clips de les dues pistes es fa servir
        # el marquee — Ctrl+arrossega o l'eina «marc».)
        # --- Visualitza ---
        m = mb.addMenu("&Visualitza")
        self._act(m, "Zoom +", "Ctrl++", lambda: self._zoom_visor(0.5))
        self._act(m, "Zoom −", "Ctrl+-", lambda: self._zoom_visor(2.0))
        self._act(m, "Zoom total", "Ctrl+0", self._zoom_tot_visor)
        m.addSeparator()
        # (El visor és ara el widget central: ja no cal «Mostra el visor»)
        m.addAction(self.log_dock.toggleViewAction())
        self.log_dock.toggleViewAction().setText("Mostra el log")
        m.addAction(self.dock_xifrat.toggleViewAction())
        self.dock_xifrat.toggleViewAction().setText("Mostra els tipus d'acord")
        m.addSeparator()
        self.a_metro = self._act(m, "Metrònom", "", self._toggle_metro, checkable=True)
        self.a_metro.setToolTip("Clic de metrònom (només en mode BPM · compàs)")
        # --- Analitza ---
        m = mb.addMenu("&Analitza")
        self._act(m, "Analitza l'àudio (acords + estructura)", "F5",
                  lambda: self.executa())
        self._act(m, "Analitza només els acords…", "F6",
                  lambda: self.executa(nomes_acords=True))
        self._act(m, "Analitza acords al rang A–B…", "",
                  self._analitza_acords_rang)
        self._act(m, "Analitza beats, downbeats i BPM", "F7",
                  self._analitza_bpm)
        self._act(m, "Ajusta la graella als beats QM…", "",
                  self._ajusta_graella_beats)
        self._act(m, "Compàs del marcador…", "",
                  self._compas_del_marcador)
        m.addSeparator()
        self.a_compas_auto = self._act(
            m, "Detecta el compàs 1 automàticament", None,
            lambda: self._detecta_compas1())
        self._act(m, "Marca el compàs 1 aquí", "", self._marca_compas_1)
        self._act(m, "Quantitza el model…", "", self._quantitza_ui)
        sub_q = m.addMenu("Quantitza BPM")
        self._act(sub_q, "Sense decimals", "",
                  lambda: self._quantitza_bpm_ui(0))
        self._act(sub_q, "1 decimal", "",
                  lambda: self._quantitza_bpm_ui(1))
        self._act(sub_q, "2 decimals", "",
                  lambda: self._quantitza_bpm_ui(2))
        self._act(m, "Mapa de tempo i compàs…", "",
                  self._tempo_mapa_ui)
        self._act(m, "Marca el rang A–B com a rubato", "",
                  self._marca_rubato_rang)
        self._act(m, "Converteix el tram de tempo a rubato", "",
                  self._converteix_rubato_ui)
        self._act(m, "Converteix el rubato a normal", "",
                  self._converteix_normal_ui)
        self._act(m, "Detecta el tempo per trams…", "",
                  self._detecta_tempo_per_trams)
        self._act(m, "Detecta el mapa de tempo (per beats)…", "",
                  self._detecta_tempo_mapa)
        m.addSeparator()
        self._act(m, "Afegeix un marcador (M)", "",
                  self._marcador_cursor)
        self._act(m, "Esborra l'últim marcador", "",
                  self._esborra_ultim_marcador)
        self._act(m, "BPM a partir dels marcadors…", "",
                  self._bpm_dels_marcadors)
        self._act(m, "Ajusta BPMs a partir dels marcadors per trams", "",
                  self._ajusta_bpms_marcadors)
        self._act(m, "Ajusta un BPM (mínims quadrats) a partir dels marcadors",
                  "", self._ajusta_bpm_minims_quadrats)
        m.addSeparator()
        m.addAction(self.amb_est)      # Inclou estructura (commutable)
        # --- Ajuda ---
        m = mb.addMenu("A&juda")
        self._act(m, "Dreceres de teclat", "", self._mostra_dreceres)
        self._act(m, "Obre la carpeta del registre", "",
                  self.obre_carpeta_registre)
        self._act(m, "Quant a Auto Chords", "", self._quant_a)

    def _actualitza_desti_accions(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        try:
            # Detecta: prioritat A-B, tram seleccionat, tema sencer.
            loop = None
            try:
                loop = self._loop_actiu()
            except Exception:  # noqa: BLE001
                loop = None
            if loop is not None:
                desti_detecta = "Detecta: selecció A–B"
            else:
                kind, idx = vr.seleccio_activa()
                if kind == "tempo":
                    desti_detecta = f"Detecta: tram {idx}"
                else:
                    desti_detecta = "Detecta: tema sencer"
            # TAP: només amb un tram de tempo seleccionat (2026-11-01).
            kind, idx = vr.seleccio_activa()
            if kind == "tempo" and vr._index_valid("tempo", idx):
                desti_tap = f"TAP: tram {idx}"
                desti_temps = f"BPM/Compàs: tram {idx}"
            else:
                desti_tap = "TAP: tria un tram de tempo"
                desti_temps = "BPM/Compàs: transport (tram 0)"
            self.lb_desti_accions.setText(
                f"{desti_detecta} · {desti_tap} · {desti_temps}")
        except Exception:  # noqa: BLE001
            pass

    def _dreceres(self):
        """TOTES les dreceres, en grups (A3).

        Les de **menú** es llegeixen dels menús REALS (així el diàleg no pot
        quedar desfasat mai: si s'hi afegeix una drecera, hi surt sola); les que
        NO són de menú (teclat del visor i gestos de ratolí) van llistades aquí
        a mà, que és l'únic lloc on viuen.
        """
        grups = []
        for accio in self.menuBar().actions():
            menu = accio.menu()
            if menu is None:
                continue
            parells = []
            for a in menu.actions():
                if a.isSeparator() or a.menu() is not None:
                    continue
                drecera = a.shortcut().toString()
                if drecera:
                    parells.append((a.text().replace("&", ""), drecera))
            if parells:
                grups.append((accio.text().replace("&", ""), parells))
        grups.append(("Ratolí i tecles del visor (combinacions)", [
            ("seleccionar un clip", "Clic a un clip"),
            ("afegir / treure un clip de la selecció (disjunt)", "Ctrl+clic"),
            ("rang de clips del MATEIX carril", "Shift+clic"),
            ("moure un clip (tot el grup si està seleccionat)",
             "Arrossega el cos del clip"),
            ("duplicar l'element seleccionat (sense arrossegar)",
             "Ctrl+D"),
            ("eina de selecció temporal (mentre es mantenen)",
             "Ctrl+Shift"),
            ("redimensionar (inici / final)", "Arrossega una vora"),
            ("rectangle de selecció (marquee)",
             "Ctrl+arrossega (temporal) o Eina marc ▸ arrossega"),
            ("canviar d'eina del timeline (intel·ligent ⇄ marc)", "E"),
            ("cursor al punt clicat / buidar la selecció", "Clic al fons"),
            ("seleccionar TOT el que hi ha dins el loop", "Doble-clic al loop"),
            ("marcar / editar el loop A-B", "Arrossega sobre el regle"),
            ("menú d'accions del clip", "Botó dret a un clip"),
            ("desplaçar la vista (pan)", "Botó dret arrossegant"),
            ("zoom", "Roda del ratolí"),
            ("play / pausa", "Espai"),
            ("TAP del temps (tap tempo)", "T"),
            ("copiar / retallar / enganxar al cursor",
             "Ctrl+C / Ctrl+X / Ctrl+V"),
            ("enganxar SALTANT-SE el snap", "Ctrl+Alt+V"),
            ("moure un clip un pas de graella (Alt = vora dreta)",
             "← / →"),
            ("Alt+clic", "cap acció de l'app (el sistema pot interceptar-lo)"),
            ("cancel·lar: rang en curs · loop · selecció", "Esc"),
            ("desfer / refer", "Ctrl+Z / Ctrl+Y"),
            ("reanomenar (clip o grup del tipus actiu)", "F2"),
            ("esborrar la selecció", "Del"),
        ]))
        return grups

    def _text_dreceres(self):
        """El diàleg de dreceres en HTML (separat per poder-lo testar)."""
        blocs = []
        for grup, parells in self._dreceres():
            blocs.append(f"<b>{grup}</b><br>" + "<br>".join(
                f"{text} — {drecera}" for text, drecera in parells))
        return "<br><br>".join(blocs)

    def _mostra_dreceres(self):
        QMessageBox.information(self, "Dreceres de teclat", self._text_dreceres())

    def _quant_a(self):
        text = (
            "<b>Auto Chords</b><br>"
            f"Versió <b>{__version__}</b><br>"
            "wav → acords + estructura<br><br>"
            "Visor DAW-like (PyQt5).<br>"
            "Motor: Chordino (acords) + Queen Mary/qm (estructura) · Vamp.")
        QMessageBox.about(self, "Quant a Auto Chords", text)
