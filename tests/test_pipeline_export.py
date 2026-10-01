import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app import pipeline


class ExportPipelineTests(unittest.TestCase):
    def test_exporta_total_generates_expected_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "tema_ACORDS"
            csv_ac = base / "acords.csv"
            csv_seg = base / "segments.csv"
            abc = base / "estructura_ABC.csv"
            base.mkdir(parents=True, exist_ok=True)

            with csv_ac.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["0.0", "C"])
                writer.writerow(["2.0", "Am"])

            with csv_seg.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["0.0", "2.0", "0", "N1"])
                writer.writerow(["2.0", "4.0", "1", "A"])

            result = pipeline.exporta_total(
                csv_ac=str(csv_ac),
                csv_seg=str(csv_seg),
                sortida=str(base),
                bpm=120.0,
                bpb=4,
                offset=0.0,
                sr=44100,
                log=lambda msg: None,
                tempo_fix=True,
                amb_estructura=True,
            )

            self.assertEqual(result["acords_csv"], str(csv_ac))
            self.assertTrue(abc.exists())
            self.assertTrue((base / "wavs_acords").is_dir())
            self.assertTrue((base / "wavs_estructura").is_dir())

    def test_app_main_imports_as_module(self):
        root = Path(__file__).resolve().parents[1]
        code = (
            "import sys; sys.path.insert(0, r'" + str(root) + "'); "
            "import app.main; print('APP_IMPORT_OK')"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("APP_IMPORT_OK", proc.stdout)

    def test_section_split_and_merge(self):
        base = [(0.0, 4.0, "A", "A"), (4.0, 8.0, "B", "B")]
        split = pipeline.parteix_seccio(base, 0, 2.0)
        self.assertEqual(len(split), 3)
        self.assertEqual(split[0][0], 0.0)
        self.assertEqual(split[0][1], 2.0)
        self.assertEqual(split[1][0], 2.0)
        self.assertEqual(split[1][1], 4.0)
        merged = pipeline.fusiona_seccions(split, 0, amb="seguent")
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0][2], "A")
        self.assertEqual(merged[1][2], "B")


if __name__ == "__main__":
    unittest.main()
