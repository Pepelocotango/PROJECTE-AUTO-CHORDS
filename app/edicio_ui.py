"""Accions d'edició de la finestra (F3).

Extret de `app/main.py`: proxies prims cap a `Visor.executa_edicio()` i els
diàlegs de trobar/reemplaçar. No muta el model directament.
"""
from PyQt5.QtWidgets import QDialog

from . import dialegs

class EdicioMixin:
    """Accions d'edició delegades al visor."""

    def _clip_seleccionat(self):
        """Retorna (kind, idx) de l'element actiu del timeline (3 carrils)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return None, -1
        return vr.seleccio_activa()

    def _elimina_element(self):
        """`Del`: el despatx únic resol la selecció (una o múltiple, 3 carrils)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        return vr.executa_edicio("elimina")

    def _duplica_element(self):
        """`Ctrl+D`: el despatx únic resol el clip o el grup seleccionat."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        return vr.executa_edicio("duplica")

    def _troba_i_reemplaca_ui(self):
        """Troba i reemplaça xifrats (acords) o etiquetes (estructura) a tot el tema."""
        vr = self.visor_ref
        if vr is None:
            self.avisa_info("Auto Chords", "No hi ha cap tema obert.")
            return
        dlg = dialegs.DialegTrobaReemplaca(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        troba, reemplaca = dlg.troba(), dlg.reemplaca()
        if not troba or not reemplaca:
            self.avisa_info("Auto Chords",
                            "Cal omplir «Troba» i «Reemplaça per».")
            return
        n = vr.troba_i_reemplaca(dlg.camp(), troba, reemplaca)
        if n:
            self.registra(f"substituïts {n} elements: «{troba}» → «{reemplaca}»")
        else:
            self.avisa_info("Auto Chords",
                            f"No s'ha trobat cap «{troba}» per substituir.")

    def _copia_clips(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            return vr.executa_edicio("copia")
        return False

    def _retalla_clips(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            return vr.executa_edicio("retalla")
        return False

    def _enganxa_clips(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            return vr.executa_edicio("enganxa")
        return False

    def _renomena_element(self):
        vr = getattr(self, "visor_ref", None)
        if vr is not None:
            return vr.executa_edicio("reanomena")
        return False

    def _parteix_acord_ui(self):
        """Parteix l'acord que conté el cursor pel punt del cursor (regla #11)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.registra("Parteix: no hi ha visor carregat")
            return False
        if vr.executa_edicio("parteix", "chord", t=vr.pos):
            self.registra(f"acord partit a {vr.pos:.3f} s")
            return True
        self.registra("Parteix: el cursor no és dins cap acord")
        return False

    def _parteix_seccio_ui(self):
        """Parteix la secció que conté el cursor pel punt del cursor (A2)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.registra("Parteix: no hi ha visor carregat")
            return False
        if vr.executa_edicio("parteix", "section", t=vr.pos):
            self.registra(f"secció partida a {vr.pos:.3f} s")
            return True
        self.registra("Parteix: el cursor no és dins cap secció")
        return False

    def _afegeix_tram_ui(self):
        """«Afegeix un canvi de tempo/compàs» al cursor (despatx únic)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        if vr.executa_edicio("afegeix", "tempo", t=vr.pos):
            self.registra(f"afegit un canvi de tempo/compàs a {vr.pos:.3f} s")
            return True
        self.registra("Afegeix tram: ja hi ha una frontera en eixe punt")
        return False

    def _parteix_tram_ui(self):
        """Parteix el tram de tempo/compàs que conté el cursor (paritat #11)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.registra("Parteix: no hi ha visor carregat")
            return False
        if vr.executa_edicio("parteix", "tempo", t=vr.pos):
            self.registra(f"tram de tempo/compàs partit a {vr.pos:.3f} s")
            return True
        self.registra("Parteix: el cursor ja és en una frontera del mapa")
        return False

    def _afegeix_acord_ui(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        if vr.executa_edicio("afegeix", "chord", t=vr.pos):
            self.registra(f"afegit acord a {vr.pos:.3f}s")
            return True
        return False

    def _afegeix_seccio_ui(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        if vr.executa_edicio("afegeix", "section", t=vr.pos):
            self.registra(f"afegida secció a {vr.pos:.3f}s")
            return True
        return False

    def _sel_cursor(self, kind):
        """Selecciona el clip de `kind` que conté el cursor (despatx únic)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return False
        idx = vr._idx_a_t(kind, vr.pos)
        if idx is None:
            return False
        return bool(vr.executa_edicio("selecciona", kind, idx, mode="set"))

    def _sel_acord_cursor(self):
        """Selecciona l'acord que conté la posició del cursor."""
        return self._sel_cursor("chord")

    def _sel_tram_cursor(self):
        """Selecciona el tram de BPM/compàs que conté la posició del cursor."""
        return self._sel_cursor("tempo")

    def _sel_seccio_cursor(self):
        """Selecciona la secció que conté la posició del cursor."""
        return self._sel_cursor("section")

    def _loop_seleccio(self):
        """`L`: loop A/B a la unió de la selecció (3 carrils)."""
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            self.registra("Loop a la selecció: no hi ha visor carregat")
            return False
        return bool(vr.executa_edicio("loop_seleccio"))

    def _neteja_loop(self):
        vr = getattr(self, "visor_ref", None)
        if vr is None:
            return
        vr._undo_marca()          # A1: el loop també és desfer/fer
        vr.loop_a = vr.loop_b = None
        vr.loop_on = False
        if hasattr(vr, "b_loop"):
            vr.b_loop.setChecked(False)
        if hasattr(self, "tb_loop"):
            self.tb_loop.setChecked(False)
        vr.timeline.set_loop(None, None)
        self.registra("loop netejat")
        vr._undo_commit()
