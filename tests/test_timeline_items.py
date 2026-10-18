"""Zones dels clips del timeline (`ChordItem` / `SectionItem`).

`_zone_at(x)` és el hit-test del gest: decideix si l'arrossegament mou una
**vora** o el **cos** del clip. Fins ara els tests posaven `_drag_mode` a mà i
la funció no s'exercitava mai directament (auditoria 18-10-2026).

A més es comprova la **paritat d'affordances** (regla #11): els dos tipus han de
tindre la mateixa amplada de nansa i els mateixos llindars.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _temporals  # noqa: E402
_ = _temporals  # higiene dels tests: l'import té efecte (esborra els temporals en plegar)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from app import timeline_items  # noqa: E402
from app import visor as visor_mod  # noqa: E402

ACORDS = "0.0,2.0,C\n2.0,5.0,Am\n5.0,10.0,G\n"
SECCIONS = ("inici_s,fi_s,durada_s,lletra,família,compas_ini,compas_fi\n"
            "0.0,5.0,5.0,A,A,1.1,3.1\n"
            "5.0,10.0,5.0,B,B,3.1,5.1\n")


def _visor():
    td = tempfile.mkdtemp()
    wav = os.path.join(td, "t.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 44100 * 10)
    out = os.path.join(td, "AUTOCHORDS_t")
    os.makedirs(out)
    ca = os.path.join(out, "acords.csv")
    sa = os.path.join(out, "estructura_ABC.csv")
    with open(ca, "w", encoding="utf-8") as f:
        f.write("inici_s,fi_s,acord\n" + ACORDS)
    with open(sa, "w", encoding="utf-8") as f:
        f.write(SECCIONS)
    v = visor_mod.Visor(wav, ca, sa, bpm=120, bpb=4, tempo_fix=True)
    v.td, v.sortida = td, out
    return v


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = visor_mod.QApplication.instance() or visor_mod.QApplication([])


class TestZonesDelsClips(_Base):

    def _items(self):
        v = _visor()
        self.addCleanup(v.close)
        return v.timeline._chord_items[0], v.timeline._section_items[0]

    def test_les_zones_de_les_vores_i_del_cos(self):
        for it in self._items():
            lx, rx = it._x_left(), it._x_right()
            c = timeline_items.ChordItem
            self.assertEqual(it._zone_at(lx - 5), c.ZONE_NONE, "fora a l'esquerra")
            self.assertEqual(it._zone_at(rx + 5), c.ZONE_NONE, "fora a la dreta")
            self.assertEqual(it._zone_at(lx + 1), c.ZONE_LEFT)
            self.assertEqual(it._zone_at(rx - 1), c.ZONE_RIGHT)
            self.assertEqual(it._zone_at((lx + rx) / 2.0), c.ZONE_BODY)

    def test_paritat_d_affordances_entre_els_dos_tipus(self):
        """Regla #11: mateixa amplada de nansa i mateixos codis de zona."""
        ch, se = timeline_items.ChordItem, timeline_items.SectionItem
        self.assertEqual(ch.HANDLE_W, se.HANDLE_W,
                         "l'amplada de la nansa ha de ser la mateixa")
        self.assertEqual(ch.ZONE_NONE, se.ZONE_NONE)
        self.assertEqual(ch.ZONE_LEFT, se.ZONE_LEFT)
        self.assertEqual(ch.ZONE_BODY, se.ZONE_BODY)
        self.assertEqual(ch.ZONE_RIGHT, se.ZONE_RIGHT)

    def test_el_llindar_es_exactament_la_nansa(self):
        """La nansa ocupa NOMÉS `HANDLE_W` px (ni un més)."""
        ch, _se = self._items()
        lx = ch._x_left()
        self.assertEqual(ch._zone_at(lx + ch.HANDLE_W), ch.ZONE_LEFT)
        self.assertEqual(ch._zone_at(lx + ch.HANDLE_W + 0.5), ch.ZONE_BODY)


if __name__ == "__main__":
    unittest.main()
