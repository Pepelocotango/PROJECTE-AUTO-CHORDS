# Guia ràpida: subagents i skills d'aquest projecte

Aquesta carpeta configura OpenCode per treballar de manera eficient en AUTO CHORDS.
Llegeix `AGENTS.md` (arrel) per a les normes del projecte; aquí només s'explica com usar aquests agents.

## Agents disponibles

| Agent | Mode | Invocació | Quan usar-lo |
|---|---|---|---|
| `explorer` | subagent | `@explorer` o automàtic | Cercar símbols, traçar fluxos, localitzar on es crida X. Només lectura. |
| `tester` | subagent | `@tester` | Llançar la suite, interpretar falles, escriure tests de regressió. Només `tests/`. |
| `reviewer` | subagent | `@reviewer` | Revisar un diff contra regles d'or, pyflakes, convencions. Només lectura. |
| `docs` | subagent | `@docs` | Actualitzar CHANGELOG, ROADMAP, docs/, AGENTS.md. Només `.md`/`docs/`. |
| `audio-dsp` | subagent | `@audio-dsp` | Feina intensiva en tempo/graella/metronom/rubato. Domini acotat. |

El **primary** (`build`) és el director: coordina i edita. Els subagents són especialistes.

## Skills disponibles (carrega on-demand)

- `regles-app`: resum operatiu de `docs/REGLES_DE_LA_APP.md`.
- `flux-dades`: model vs cru, què es desa a cada acció.
- `suite-tests`: com executar la suite i higiene.
- `audio-tempo`: invariants del domini tempo/graella/metronom.
- `release-higiene`: checklist pre-commit.

Carrega'ls amb el tool `skill` quan la tasca ho requereixi (no els carreguis tots sempre).

## Flux de treball recomanat

1. **Tasca de codi nova**: `build` llegeix `AGENTS.md` + skill `regles-app`, planifica, edita.
2. **Exploració**: llança `@explorer` (background si vols) per traçar fluxos sense consumir context del primary.
3. **Després d'editar**: llança `@tester` per executar la suite i `@reviewer` per revisar el diff (poden córrer en paral·lel si no toquen els mateixos fitxers).
4. **En acabar**: llança `@docs` per sincronitzar CHANGELOG/AGENTS.md/docs.
5. **Feina de tempo**: delega a `@audio-dsp` (domini acotat).

## Paral·lel segur vs no

- **Segur en paral·lel**: explorer (lectura) + tester (execució); reviewer (lectura) + docs (només .md).
- **No en paral·lel**: dos agents editant el mateix fitxer (p. ex. `app/visor.py`, `app/tempo_map.py`). Serialitza o usa worktrees.
- `subagent_depth: 1` (config): els subagents no poden llançar-ne més. Evita fan-out descontrolat i cost extra.

## Configuració

`.opencode/config.json`:
```json
{
  "subagent_depth": 1,
  "default_agent": "build"
}
```

Si OpenCode no llegeix `.opencode/config.json`, mou-lo a `opencode.json` a l'arrel del projecte.

## Convencions del projecte (recordatori)

- Tot en català (respostes, docs, comentaris, commits).
- Paperera sempre (`gio trash`, mai `rm`).
- No secrets al repo.
- No deixar processos ni temporals en segon pla.
- Tests no deixen res al disc (`_temporals`).
- Suite sempre verda; pyflakes net.

## Model

Amb subscripció Go, els subagents hereten el model del primary (`opencode-go/...`). Si un agent (p. ex. `reviewer` o `docs`) pot anar amb un model més barat, especifica'l al seu frontmatter (`model: opencode-go/...`).

## Notes

- Els agents referencien `AGENTS.md` i les docs; no les dupliquen. Si canvies una regla, actualitza el skill `regles-app`.
- `docs/REGLES_DE_LA_APP.md` és contracte: els agents no el canvien sense consentiment explícit de l'operador.
