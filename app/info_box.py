"""Caixa d'informació i rotatori de consells de la finestra (F3).

Extret de `app/main.py`. `InfoBoxMixin` assumeix que la classe que l'hereta
té `info_box`, `_info_timer`, `_info_*` i `visor_ref` (o `getattr` amb defecte).
"""
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication

from . import theme

# Caixa d'informacio (a baix, a la dreta del log): quan el ratoli no es sobre
# res amb info, hi gira el rotatori de consells i dreceres. Cada quan canvia de
# «pantalla», i quanta estona es queda aturada després d'un clic a la caixa.
# 8 s per «pantalla»: les pantalles ara són CURTES (3-4 línies) i moltes, així
# que el cicle sencer es veu abans. (Abans: 8 s amb pantalles llarguíssimes →
# no es llegien; després 14 s → el cicle no s'acabava mai.)
_INFO_ROTACIO_S = 8.0
_INFO_PAUSA_S = 30.0        # clic a la caixa → el rotatori es para aquest temps


class InfoBoxMixin:
    """Info box + rotatori de consells/dreceres."""

    def _missatge_info(self, text):
        """Missatge TRANSITORI a la caixa d'informacio (desfer/refer, avisos).

        Te un format propi (banner blau) per distingir-lo del **rotatori** de
        consells i dreceres, que es mostra quan no hi ha res a dir.
        """
        import time as _t
        cap = (f"<b style='color:{theme.BLAU_INFO}'>● Missatge</b> "
               f"<span style='color:{theme.MUTED}'>· torna al rotatori aviat"
               "</span>")
        self.info_box.setHtml(
            cap + f"<br><b style='color:{theme.BLAU_INFO}'>{text}</b>")
        self._info_html_actual = None   # força reescriure quan passi el temps
        self._info_msg_fins = _t.monotonic() + 4.0

    def _clic_info_box(self):
        """Clic a la caixa: 1r → PARA el rotatori (dura mes); seguents → avancen.

        Cada clic tambe **allarga** la pausa `_INFO_PAUSA_S`, de manera que es
        pot llegir al ritme de cadascu: clic per aturar, clic per passar de
        pagina. Passada la pausa, el rotatori es torna a moure sol.
        """
        import time as _t
        ara = _t.monotonic()
        if ara < getattr(self, "_info_pausa_fins", 0.0):
            # Ja estava pausat (per un clic anterior) → avanca una «pantalla».
            self._info_panell = getattr(self, "_info_panell", 0) + 1
            self._info_panell_t = ara
        self._info_pausa_fins = ara + _INFO_PAUSA_S
        self._actualitza_info_widget()

    def _actualitza_info_widget(self):
        """Mostra a la caixa d'informacio la info del que hi ha sota el ratoli.

        Si el ratoli es sobre un boto, un camp o una zona del visor amb
        informacio → l'explica. Si NO es sobre res amb info → passa al
        **rotatori de dreceres i consells** (`_info_panells`).
        """
        import time as _t
        if _t.monotonic() < getattr(self, "_info_msg_fins", 0.0):
            return          # hi ha un missatge transitori (desfer/refer...)
        try:
            w = QApplication.widgetAt(QCursor.pos())
        except Exception:  # noqa: BLE001
            # timer de hover (hot): fallback silenciós intencionat
            return
        html = None
        if w is not None:
            # El VISOR (timeline) es un sol giny: li demanem la zona del ratoli
            # (el seu "ratoli intel·ligent") per explicar quina accio hi faria.
            vr = getattr(self, "visor_ref", None)
            if vr is not None:
                tv = getattr(vr, "timeline", None)
                if tv is not None and (w is tv or w is tv.viewport()):
                    try:
                        pos = tv.viewport().mapFromGlobal(QCursor.pos())
                        zona = tv.info_zona(pos)
                        if zona:
                            html = f"<b>{zona}</b>"
                    except Exception:  # noqa: BLE001
                        # timer de hover (hot): fallback silenciós intencionat
                        pass
            if html is None:
                # pugem fins a un widget que tingui tooltip (els fills solen no
                # tenir-ne)
                x = w
                while x is not None and not x.toolTip():
                    x = x.parentWidget()
                if x is not None:
                    nom = x.text() if hasattr(x, "text") else ""
                    tip = x.toolTip()
                    html = f"<b>{nom}</b><br>{tip}" if nom else f"<b>{tip}</b>"
        if html is None:
            # Fora de qualsevol giny amb info → rotatori. Si el ratoli es sobre
            # la MATEIXA caixa, no rotem (que no canviï mentre es llegeix).
            html = self._info_defecte_html(_t.monotonic(),
                                           rota=(w is not self.info_box))
        if html:
            self._posa_info(html)

    def _posa_info(self, html):
        """Escriu la caixa d'informacio nomes si el contingut ha canviat.

        Comparar amb el darrer HTML escrit (i no amb `toHtml()`, que el
        normalitza) evita reescriure-la a cada tic del timer: si no, el
        desplaçament de la caixa es reiniciaria sense parar.
        """
        if html != getattr(self, "_info_html_actual", None):
            self._info_html_actual = html
            self.info_box.setHtml(html)

    def _info_panells(self):
        """Panells de la caixa d'informacio per defecte: consells + dreceres.

        Cada pantalla és **curta** (3-4 línies) i agrupada per **quan la
        necessites** (seleccionar, moure, copiar, loop, transport…), no per
        «la llista sencera de dreceres». El **primer** panell s'adapta a l'eina
        vigent del timeline. Les dreceres **dels menús** no hi surten: viuen
        senceres al dialeg **Ajuda ▸ Dreceres de teclat** (una sola font,
        `_dreceres()`), i l'últim panell ho recorda.
        """
        return [
            self._panell_eina(),
            ("Seleccionar clips", [
                ("Un clip", "Clic"),
                ("Afegir/treure un clip (disjunt)", "Ctrl+clic"),
                ("Rang del carril del clip clicat", "Shift+clic"),
                ("Eina de selecció temporal", "Ctrl+Shift"),
                ("Rectangle: el que HI SONA a dins", "Ctrl+arrossega"),
            ]),
            ("El rectangle (marquee)", [
                ("Agafa els clips que SONEN a dins, no només els que hi "
                 "comencen", ""),
                ("Només de les pistes que cobreix (si no toca les seccions, "
                 "no les agafa)", ""),
                ("Es temporal: Ctrl+arrossega · o fix: Eina marc", ""),
            ]),
            ("Duplicar un clip", [
                ("Duplicar l'element seleccionat (o el grup)", "Ctrl+D"),
                ("L'arrossegament normal mou; no duplica", ""),
            ]),
            ("Moure i redimensionar", [
                ("Moure (tot el grup si està seleccionat)",
                 "Arrossega el cos del clip"),
                ("Moure l'inici o el final", "Arrossega una vora"),
                ("Un pas de graella", "← / →"),
                ("La vora DRETA un pas de graella", "Alt+← / Alt+→"),
                ("Alt+clic", "cap acció de l'app"),
            ]),
            ("Copiar, retallar i enganxar", [
                ("Al cursor", "Ctrl+C / Ctrl+X / Ctrl+V"),
                ("L'enganxat SUBSTITUEIX el tram: la cançó no creix mai", ""),
                ("Enganxar saltant-se el snap", "Ctrl+Alt+V"),
            ]),
            ("Loop A-B", [
                ("Crear-lo o editar-lo", "Arrossega sobre el regle"),
                ("Marcar l'inici / el final al cursor", "Ctrl+[ / Ctrl+]"),
                ("Seleccionar TOT el que hi ha a dins", "Doble-clic al loop"),
                ("Loop a la selecció (unió dels 3 carrils)", "L"),
            ]),
            ("Transport", [
                ("Play / aturar", "Espai"),
                ("TAP del temps (tap tempo)", "T"),
                ("Canviar d'eina del timeline (intel·ligent ⇄ marc)", "E"),
            ]),
            ("Tecla Esc (cancel·lar)", [
                ("Rang en curs (rectangle) → l'anul·la", "Esc"),
                ("Loop a mig marcar → el descarta", "Esc"),
                ("Loop actiu → el desactiva i ESBORRA (fora la caixa groga)",
                 "Esc"),
                ("Alguna cosa seleccionada → la buida", "Esc"),
            ]),
            ("Editar i desfer", [
                ("Desfer / refer", "Ctrl+Z / Ctrl+Y"),
                ("Reanomenar (clip o grup del tipus actiu)", "F2"),
                ("Esborrar la selecció", "Del"),
            ]),
            ("Zoom i navegació", [
                ("Zoom", "Roda del ratolí"),
                ("Zoom + / − / total", "Ctrl++ / Ctrl+− / Ctrl+0"),
                ("Menú del clip (o pan arrossegant)", "Botó dret"),
            ]),
            ("Quantitza: què fa i què NO toca", [
                ("Mou només els INICIS dels clips a la graella; el final de "
                 "cada clip es deriva del següent", ""),
                ("Abast: tot, només la selecció, tot però només acords o tot "
                 "però només estructura", ""),
                ("Graella d'acords: de corxera a 1 compàs. Graella "
                 "d'estructura: d'1 a 64 compassos", ""),
                ("No toca BPM, compàs, offset ni el cru de l'anàlisi: "
                 "treballa sobre el model que veus", ""),
                ("És una sola operació: Ctrl+Z la desfà i Ctrl+Y la refer", ""),
            ]),
            ("Per què l'enganxat sobreescriu", [
                ("Els clips cobreixen SEMPRE tota la WAV (regla d'or #4)", ""),
                ("Per això copiar/enganxar és com una cinta: substitueix", ""),
                ("Totes les dreceres dels menús: Ajuda ▸ Dreceres de teclat", ""),
            ]),
        ]

    def _panell_eina(self):
        """Panell que **segueix l'eina vigent** del timeline (marc/intel·ligent)."""
        tool = "intel·ligent"
        try:
            tv = getattr(getattr(self, "visor_ref", None), "timeline", None)
            if tv is not None:
                tool = tv.tool()
        except Exception:  # noqa: BLE001
            pass
        if str(tool).startswith("marc"):
            return ("Eina del timeline: SELECCIÓ", [
                ("Arrossega pel timeline per DIBUIXAR un rectangle", ""),
                ("Selecciona el que hi SONA a dins, i només de les pistes "
                 "que cobreixi", ""),
                ("No mou cap clip; el rectangle desapareix en deixar anar", ""),
                ("Botó «Eina» a la barra (o Selecciona) per canviar d'eina", ""),
            ])
        return ("Eina del timeline: intel·ligent", [
            ("La fletxa s'adapta al que toques (no cal triar res)", ""),
            ("Cos del clip = MOURE · vores del clip = redimensionar", ""),
            ("Regle = crea el LOOP A-B · roda = zoom", ""),
            ("Shift+clic = rang · Ctrl+clic = afegir/treure de la selecció", ""),
            ("Botó «Eina» a la barra (o Selecciona) per passar a «marc»", ""),
        ])

    def _info_defecte_html(self, ara, rota=True):
        """HTML del panell actual de dreceres/consells (rotant cada ~14 s).

        `rota=False` congela el panell (ratoli sobre la caixa). I si hi ha una
        **pausa per clic** vigent (`_info_pausa_fins`), tampoc no rota.
        """
        panells = self._info_panells()
        if not panells:
            return None
        n = len(panells)
        if ara < getattr(self, "_info_pausa_fins", 0.0):
            rota = False        # pausat per un clic a la caixa
        t0 = getattr(self, "_info_panell_t", 0.0)
        if t0 <= 0.0:
            self._info_panell_t = ara          # primera vegada: sense rotar
        elif rota and ara - t0 >= _INFO_ROTACIO_S:
            self._info_panell = (getattr(self, "_info_panell", 0) + 1) % n
            self._info_panell_t = ara
        i = getattr(self, "_info_panell", 0) % n
        titol, parells = panells[i]
        files = []
        for text, dr in parells:
            files.append(f"{text} · <b>{dr}</b>" if dr else text)
        cap = (f"<b style='color:{theme.BLAU_INFO}'>Dreceres i consells</b> "
               f"<span style='color:{theme.MUTED}'>({i + 1}/{n})</span>")
        peu = ("<br><br><i style='color:%s'>Ratolí per un botó → què fa · "
               "<b>clic aquí</b> → atura i passa de pàgina.</i>" % theme.MUTED)
        return cap + f"<br><b>{titol}</b><br>" + "<br>".join(files) + peu
