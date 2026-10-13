# ⚠️ REGLES DE LA APP — invariants inmutables

> ## 🔴 IMPORTANT — LLEGEIX-HO ABANS DE TOCAR CODI
> Aquestes són les **regles d'or (invariants)** d'AUTO CHORDS.
> **Cap canvi de codi pot trencar-les.** Si una funcionalitat nova xoca amb una
> regla, es canvia **la funcionalitat**, no la regla (tret de decisió explícita
> de l'operador, que s'ha de documentar aquí **i** al `CHANGELOG`).
>
> Cada regla té la seva **validació** al codi i un **test** que la comprova.
> Referenciades a `ROADMAP.md` (§Notes d'implementació) i `DEVELOPING.md`.

## 1. Ordre estricte dels clips
Els clips (acords i seccions) estan **ordenats pel temps d'inici**, **sense
solapaments ni inversions**. → `visor._valida_canvis_acords` /
`_valida_canvis_seccions`.

## 2. Contigüitat
Cada clip comença **exactament** on acaba l'anterior: `prev.fi == curr.t` (acords)
i `prev.fi == curr.ini` (seccions) — sense forats ni encavalcaments.
→ `timeline.py` · `pipeline.filtra_seccions`.

## 3. Durades derivades
La durada d'un clip **no s'emmagatzema**: es **deriva** (l'inici del següent, o
la durada de la WAV per a l'últim).

## 4. Cobertura total
**La suma dels clips d'acords = la durada de la WAV** i **la suma dels clips
d'estructura = la durada**, en qualsevol mode (**Lliure** o **BPM · compàs**) i
amb o sense **snap**: el 1r clip arrenca a **0** (capçalera «N» si cal) i
l'últim arriba a la **durada**. La regla **mana sobre el snap** (que només
quantitza els límits **interiors**). → `pipeline.normalitza_cobertura()`, aplicat
en carregar el **visor** i en **exportar** (CSV/ABC + wavs).

## 5. Una sola font de veritat
El **backend** (`app.pipeline`) és l'única font de dades; la UI (`app.visor` +
`app.timeline`) **en reflecteix** l'estat.

## 6. Les WAVs només via `exporta()`
L'edició **mai** toca les WAVs generades; només s'escriuen en **exportar**
(`pipeline.exporta_total`). «Mai toca els WAVs generats.»

## 7. Instància única
No poden córrer **dues instàncies** de l'app alhora (un lock a `tempfile`).
→ `main.py` + `plataforma.bloqueja_instancia_unica`.

## 8. Temps vàlids
Cap temps **negatiu** ni cap durada **≤ 0**.

## 9. Portabilitat
Tot el que sigui natiu es compila per a **macOS 10.13+** i **sense AVX**
(el Q9400): cap binari del paquet pot superar **`minos 10.13`** ni requerir AVX.
→ `PLANIFICACIO_MACOS.md` · verificat al CI (`eines/verifica_minos_macos.py`).

## 10. Estat en un directori escriptible
El **log / opcions / temp** van sempre a un directori **escriptible** — mai dins
un paquet de només lectura (AppImage, `.app` en quarantena). → `app/config.py`.

---

> 📌 **En afegir una regla nova**: numera-la aquí, afegeix-ne la validació al
> codi i un test que la comprovi (les regles **1, 2, 4, 7, 8** ja en tenen).
