# PLA — Edició lliure amb contracte posterior (regla #4)

> **Decisió de l'operador (17-10-2026)**, formulada per ell mateix: la regla
> d'or **#4** (els clips cobreixen sempre tota la WAV) deixa de ser un **grilló
> a cada edició** i passa a ser un **contracte que es compleix DESPRÉS de cada
> edició**. Les eines d'edició es tornen lliures (com un DAW); si una operació
> deixa un forat, el forat es converteix en **silenci explícit (`N`)** dins la
> mateixa operació.

## 1. Principi

```
   edició lliure  →  normalització al final de la MATEIXA operació  →  model vàlid
```

- **El model no canvia de format** (segueixen sent marques d'acord + seccions
  amb inici/fi). No cal migrar cap CSV.
- **`N` = silenci**. És la peça que fa possible tot això: un forat és una
  tirada de `N` (marca `N` a l'inici del forat + marca de l'acord següent).
- **Els invariants no es toquen**, només el **moment** d'aplicar-los. Per això
  la major part dels tests existents continuen essent vàlids.
- **Mai en silenci**: si una operació no es pot completar, missatge a pantalla
  (`avis_editor`), com ja es fa als enganxaments.

## 2. Resultat esperat (especificació)

| Operació | Comportament ACTUAL | Comportament VOLEM |
|---|---|---|
| **Esborrar un acord** | La marca desapareix → **el clip anterior s'estira** per tapar el forat | El tram es queda **en silenci (`N`)**; els veïns **no es mouen** |
| **Esborrar la selecció** | Ídem per cada clip | Ídem: cada tram esborrat → `N`, veïns intactes |
| **Esborrar-ho TOT** | ✅ Ja arreglat (`e131837`): queda `N` a 0,00 | Igual (referència del que volem a tot arreu) |
| **Moure un clip** (arrossegar) | La marca es mou → l'anterior s'estira i el propi final canvia | **Retallar i enganxar**: l'origen queda `N` i el clip va al destí **sobreescrivint** |
| **Redimensionar** (vores) | Mou la vora = mou la marca veïna | La vora és **lliure**: el clip es fa més llarg/curt i el que queda al costat és `N` |
| **Duplicar** (`Ctrl+D`) | El duplicat va «a mig camí del següent» (sobreescriu el següent clip) | **Igual que enganxar**: el duplicat va després del clip i **sobreescriu** el tram que ocupa |
| **Duplicar arrossegant** (`Ctrl+Shift`) | L'original es queda i la còpia va al destí (pendent: fantasma + semàntica) | **Igual que enganxar** (sobreescriu el destí) |
| **Enganxar** (`Ctrl+V`) | ✅ Ja sobreescriu el tram | Igual (és el model de referència) |
| **Afegir un acord** | Parteix el clip existent al punt | Igual (partir és correcte: el nou clip ocupa fins al següent) |
| **Partir / fusionar** | Mantenen la cobertura | Igual |
| **Reanomenar** | No toca geometria | Igual |
| **Mode fàcil / re-regularitzar** | Reescriu tot el model des de l'anàlisi crua | Igual |
| **Seccions** | Ja tenen inici/fi explícits, però **s'estiren entre elles** en moure's | Vores lliures; el forat que quedi, **`A`** (o el símbol de «sense secció» que decidim) |

**Criteri d'èxit global**: després de qualsevol operació, el model compleix
l'invariant #4 **sense haver-ho hagut de demanar**, i cap operació queda
refusada per la regla (desapareixen els guards de «no pots esborrar l'últim»).

## 3. On es toca (mapa del codi)

L'auditoria (17-10) troba **~36 punts d'assignació del model** a
`app/visor.py` (`self.acords = …` i `self.seccions = …`), que es redueixen a
**aquestes operacions**:

| Operació | Punt de codi (aproximat) |
|---|---|
| Esborrar un acord | `_elimina_acord` / `_elimina_acord_index` |
| Esborrar la selecció | `_elimina_seleccio` (ja normalitza ✓) |
| Moure / redimensionar acord | `_on_chord_time_moved` / `_on_chord_end_moved` |
| Duplicar | `_duplica_acord_index` / `_duplica_seleccio` |
| Enganxar | `_enganxa_seleccio` ✓ (referència) |
| Afegir / partir / fusionar | `_afegeix_acord`, `_parteix_acord`, `_fusiona_acord` |
| Mode fàcil | `regularitza_des_de_cru` |
| Moure / redimensionar secció | `_on_section_changed` / `_on_section_moved` |
| Esborrar / duplicar / afegir secció | `_elimina_seccio*`, `_duplica_seccio*`, `_afegeix_seccio` |
| **Normalització** | `_normalitza_cobertura` (ja existeix ✓ — és el ganxo) |

Punts d'entrada comuns que caldrà respectar: **desfer/refer** (una sola entrada
per operació, ja es fa), **`set_data`** del timeline i **`_desa_i_regenera`**
(desar + regenerar l'ABC).

## 4. Pla per fases (cada fase utilitzable i provada)

**Fase 0 — Terreny (aquesta)**
- [x] Llista d'operacions i punts de codi (secció 3)
- [x] Especificació del resultat esperat (secció 2)
- [ ] Comptar els tests que afirmen la cobertura obligatòria
- [ ] Confirmar amb l'operador el símbol de «sense secció» (per als forats d'estructura)

**Fase 1 — El ganxo**
- Cridar `_normalitza_cobertura()` al **final de cada operació** que modifica el
  model (encara que el comportament sigui l'actual). Sense canvi visible, però
  amb la xarxa posada. Tests.

**Fase 2 — Esborrar** (el cas més simple i el que més mal ha fet)
- Esborrar un acord (i la selecció): el tram → **`N`**, veïns intactes.
- Treure el guard de «no pots esborrar l'últim» del camí d'un sol clip.
- Tests: esborrar el mig, el primer, l'últim, tots.

**Fase 3 — Moure i redimensionar**
- Moure = **retallar + enganxar** (l'origen → `N`, el destí sobreescrit).
- Vores lliures amb `N` al costat.
- Tests: moure al mig, a sobre d'un altre, al principi, al final.

**Fase 4 — Duplicar**
- `Ctrl+D` i `Ctrl+Shift`+arrossegar amb la mateixa semàntica que enganxar.
- (Si es vol, aquí entra el **fantasma** del gest de duplicar.)

**Fase 5 — Seccions**
- Vores lliures + forats amb el símbol acordat + paritat #11.

**Fase 6 — Consumidors i tancament**
- `acords_a_live.py` (guia del DAW) i partitura: comprovar que els forats `N` no
  els trenquen (el `N` no ha de generar harmonia).
- **Export WAV: normalitza igualment** (xarxa final).
- MCP: eines d'esborrar/duplicar la **selecció**.
- Docs (`ESQUEMA_UI`, info box) i suite sencera verda.

## 5. Riscos i decisions obertes

1. **Solapaments**: si una operació en crea (p. ex. moure un clip a sobre d'un
   altre), decidir qui mana (proposta: **l'últim que has tocat**).
2. **Símbol de «sense secció»** per als forats d'estructura (avui no n'hi ha cap).
3. **Undo**: cada operació ha de continuar sent **una sola entrada** de desfer
   (l'autosave i la normalització no han de crear-ne de noves).
4. **Tests**: identificar els que afirmen la cobertura obligatòria; la resta ha
   de continuar passant sense canvis.
5. **Rendiment**: la normalització extra a cada operació és barata (llistes
   curtes), però cal mesurar-ho en temes grans.

---

## 6. ESPECIFICACIÓ TANCADA (decisions de l'operador, 17-10-2026)

### 6.1 Símbols
- **`"-"` = «sense secció»** (forat explícit d'estructura).
- **`"N"` = «sense acord»** (silenci explícit d'acords).

### 6.2 Regla general: **mana l'últim editat**
Quan una operació deixa clips solapats, el clip **que acabes de tocar o crear**
guanya; el que queda **a sota** es **talla o s'elimina** segons 6.3. **Mai es
refusa l'operació** per la regla #4.

### 6.3 Moviment d'un bloc (1 o més clips consecutius, MATEIXA DURADA)

**Endavant** (el bloc va més tard)
- **Origen**: l'anterior **s'estira** fins a l'**inici del primer clip de la
  selecció** (tapa el forat que deixa el bloc).
- **Destí**: el que queda solapat a sota:
  - **se li talla l'inici** (perd el cap que cau dins del bloc);
  - **s'elimina** si el seu **final** cau dins o més enllà del bloc (no en queda cap tros).

**Endarrere** (el bloc va més d'hora)
- **Origen**: el **posterior s'estira** fins al **final de la selecció**.
- **Destí**: el que queda solapat a sota:
  - **se li talla el final** (perd la cua que cau dins del bloc);
  - **s'elimina** si el seu **inici** cau dins o més enllà del bloc.

### 6.4 Esborrar (1 o més clips) → opció **(a)**
- **L'anterior s'estira** i tapa el forat (mateixa lògica que l'origen d'un
  moviment). **No** es converteix en `N`, excepte si el model queda **sense cap
  clip**: llavors es posa el clip canònic (`N` a 0 / `A` de 0 a la durada).

### 6.5 Conseqüència per al codi
- **L'origen** d'un moviment **ja fa el que volem** (el model de marques estira
  el veí tot sol) → no s'hi ha de fer res.
- **El que cal implementar és el DESTÍ**: preservar la durada del bloc mogut i
  **tallar/eliminar** el que cau a sota. Avui la marca moguda s'estira fins a la
  marca següent i, per tant, **no es preserva la durada**.
- **L'esborrar** ja compleix (el veí s'estira): només cal **treure el guard** que
  refusa l'últim clip i cridar la normalització (ja es fa, `e131837`).
- **`N` i `-`** queden per al cas degenerat i per als forats que cap operació tapi.

### 6.6 Ordre d'implementació revisat
1. **Destí del moviment/redimensionat** (preservar durada + tallar/eliminar) ← el gruix
2. **Esborrar**: treure el guard de l'últim (que els dos camins facin el mateix)
3. **Duplicar/enganxar**: ja sobreescriuen; alinear amb 6.3
4. **Seccions**: mateixa lògica, amb `-` per als forats
5. **Consumidors**: guia Live/partitura · **export que normalitza** · MCP (esborrar/duplicar la selecció)

> **Decisions tancades**: símbol `-` · mana l'últim editat · esborrar = (a)
> l'anterior s'estira · mateixa lògica per a totes les operacions.
