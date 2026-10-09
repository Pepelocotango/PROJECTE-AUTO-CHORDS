## AUTO CHORDS v0.5.2

Aplicació d'escriptori per **analitzar un àudio, navegar-ne els acords i
l'estructura, corregir-los i exportar clips preparats per al DAW**.

Aquesta versió inclou l'**AppImage autocontinguda** per a Linux x86_64
(no cal instal·lar Python, ni Qt, ni res: només executar-la).

### 📥 Com executar l'AppImage

```bash
chmod +x AutoChords_*.AppImage
./AutoChords_*.AppImage
```

O bé **doble clic** al fitxer (pot caler marcar «Executa» a les propietats).

> ⚠️ **Requisit d'àudio per ESCOLTAR**: cal **PipeWire** o **PulseAudio**
> (a qualsevol escriptori Linux actual). Sense ells l'app funciona igual
> (analitzar, editar, exportar); només avisa que no pot sonar.
>
> ✅ **No cal `libfuse2`**: el runtime de l'AppImage és **estàtic** (ho porta
> tot a dins). Només cal el suport **FUSE del nucli** (estàndard a tot Linux).
> Si mai fallés: `./AutoChords_*.AppImage --appimage-extract-and-run`

---

## Canvis d'aquesta versió

### Afegit
- **Fase D.2 — edició DAW-like al timeline**:
  - **Multi-selecció**: **Ctrl+clic** afegeix/treu un clip de la selecció;
    **Shift+clic** selecciona el rang entre l'àncora i el clip clicat (dins del
    mateix carril). Clic al fons = neteja la selecció.
  - **Eliminació de grup**: `Delete` esborra tota la selecció en **una sola
    operació d'undo**.
  - **Porta-retalls intern**: **`Ctrl+C`** (copiar), **`Ctrl+X`** (retallar) i
    **`Ctrl+V`** (enganxar al cursor). Els acords es guarden **relatius al clip
    més antic**, així l'enganxat preserva l'espaiat intern; l'operació **valida
    abans d'aplicar** (si xoca, no toca res) i és un **únic undo**.
  - **`Ctrl+D` de grup**: duplica tots els clips seleccionats d'una vegada.
  - **Moure el grup**: arrossegar un clip seleccionat mou **tota la selecció**.
  - **Indicador de MODE** al regle: badge fix a la dreta amb `120 BPM · 4/4`
    (mode tempo) o `Lliure` (mode sense BPM). `RulerLayer.mode_label()`.
- **GUI — «Quant a»**: el diàleg **Quant a Auto Chords** ara mostra la
  **versió** de l'app (`app.__version__`), sincronitzada amb `pyproject.toml`
  per un test.
- **Refactor intern**: `timeline.py` **partit** en 4 mòduls (`timeline.py` 1774 →
  **898** línies + `timeline_items.py` + `timeline_layers.py` + `timeline_base.py`),
  preparant la Fase D.2. Els símbols públics es re-exporten via `__all__`.

### Arreglat
- **Línies del grid pintades de negre**: `grid_levels()` retornava els *strings*
  literals `"theme.TL_GRID_*"` i els consumidors feien `QColor(string)` → color
  **invàlid**. Ara retorna els colors **reals** de `theme`.

### Proves
- **228 tests** · OK (1 skip) — +18 respecte de la v0.5.1 (multi-selecció,
  `Ctrl+C/V/X`, `Ctrl+D` i **moure** el grup, indicador de mode i colors del grid).
- **CI multi-SO re-verificat** amb tot el codi de D.2: **Linux AppImage #8**,
  **Windows #14** i **macOS #8** (amb pas de tests) — tots **VERDS**.

---

*Generat automàticament a partir de `CHANGELOG.md`.*

**Autor:** Pëp (pepelocotango@gmail.com) · **Llicència:** GPL-3.0-or-later.

Desenvolupat en col·laboració amb agents i assistents d'IA: **opencode** (amb
models com **DeepSeek**, **Claude**, **Gemini**...), **Claude** (Anthropic),
**Gemini** i **Google AI Studio**, **Devin**, **Chatbox**, **VS Code +
GitHub Copilot** i **Windsurf + SWE**. Gràcies! 💙
