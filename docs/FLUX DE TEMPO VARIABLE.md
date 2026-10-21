# Especificació Tècnica: Flux de Tempo Variable Basat en Marcacions Humanes i Re-tempo Dinàmic

> **Objectiu del document:** Definir l'arquitectura, el model matemàtic i el flux d'interacció perquè un agent de codi pugui implementar el sistema de detecció i edició de tempo variable en cançons sense claqueta (rubato, directes o fluctuacions de tempo).
>
> **ESTAT: IMPLEMENTAT el 21-10-2026** (§4.A `tempo_map.mou_frontera_retempo` i
> `canvia_compassos_tram` · §4.B guia del drag lliure · §4.C 4 accions de
> compassos al menú del tram + marcadors lligats a la frontera · §6 els 4 plans
> de prova a `tests/test_tempo_trams.py` i `tests/test_despatx_edicio.py`).
> Suite **1.321 OK** (1 skip). Decisions de l'operador: els marcadors **es mouen**
> amb la frontera i **s'esborren** amb ella; `+1/−1/×2/÷2` afecten **només** eixe
> tram (segons immòbils, els veïns no es toquen). Detall: `CHANGELOG.md` 11b.
>
> **11d — marcadors i «Detecta» (21-10-2026):** `+` parteix el tram amb un
> nombre enter de compassos (`parteix_tram_marcador`): el tram esquerre adopta
> el BPM derivat, la resta fins al pròxim inici —que **no es mou**— ajusta el
> BPM al N enter més pròxim, i si el marcador cau massa a prop de l'inici es
> conserva el BPM vigent (el gest no es bloqueja). «Detecta» sobre un tram fixa
> Δt i només tria N (`retempo_tram_detectat`, sense *ripple*). «Ajusta BPMs a
> partir dels marcadors per trams» refà tot el mapa amb offset = primer
> marcador. Cap frontera heretada bloqueja ni es mou sola
> (`_mapa_valida_sense_moure`, permissiu). La nansa de la frontera té 8 px de
> marge i es pinta al timeline.

---

## 1. Diagnosi del Problema Actual

Actualment, l'aplicació disposa de totes les peces aïllades, però pateix un **bloqueig circular de disseny** quan s'intenta treballar amb tempo variable:

1. **Desacoblament dels marcadors:** `MarcadorsLayer` pinta línies grogues estàtiques amb `Qt.NoButton`. Quan l'usuari intenta moure un tall a l'escena, mou la vora d'un clip inferior, però el marcador groc queda desconnectat al lloc original.
2. **Rigidesa del `_ripple`:** En arrossegar la frontera entre dos trams de tempo, el codi crida `snap_frontera_compas` i `_ripple_des_de`. Això intenta mantenir el BPM congelat i desplaça en bloc tots els trams posteriors en el temps.
3. **Bloqueig del validador de compassos enters:** Quan el tram posterior és empès en el temps sense recalcular-ne el BPM, la seva durada deixa de correspondre a un nombre enter de compassos (per exemple, passa a tenir 3,74 compassos). Immediatament, `valida_i_normalitza_compassos` llença una excepció i el sistema avorta el moviment en sec.
4. **La paradoxa de la detecció acústica:** Un detector acústic de BPM (per FFT o autocorrelació) sobre un segment fixat a mà gairebé mai no donarà una xifra que divideixi el temps en compassos enters exactes.

---

## 2. El Nou Model Mental: «Opció A Refinada»

La jerarquia de dependències s'inverteix:

> **El ratolí mana sobre el temps ($\Delta t$), el nombre de compassos ($N$) es manté invariant, i el BPM és l'esclau matemàtic que s'adapta.**

```
Temps humà (talls/markers)  ──►  Defineix la durada exacta (Δt)
Nombre de compassos (N)     ──►  Definit per l'estructura musical (ex: 4, 8, 16)
BPM del tram                 ──►  Derivat matemàtic pur:  BPM = (N · BeatsPerBar · 60) / Δt
```

Amb aquest enfocament:
- La frontera del tram cau **sempre al 100%** en una línia de compàs per definició matemàtica.
- No hi ha cap fracció de compàs il·legal.
- Cap validador no pot bloquejar el moviment del ratolí.

---

## 3. Flux de Treball d'Usuari (Passos 1 a 4)

### Pas 0: Entrada de referència (Punt de partida)
- L'usuari indica el compàs base (per defecte `4/4`) i un **BPM orientatiu** a la barra de transport:
  - Ja el coneix i l'escriu (ex: `140`).
  - O bé fa 4 tocs de TAP (`T`).
  - O bé l'app executa una estimació acústica global inicial ràpida.

### Pas 1: Fixar el Compàs 1 (Offset)
- L'usuari col·loca el cursor a l'inici real del primer compàs (downbeat) i prem **Compàs 1 aquí** (o l'assistent ho demana). El tram anterior a aquest punt és zona pre-música (cuenta enrere/anacrusi).

### Pas 2: Marcació en viu (`+`)
- La cançó sona. L'usuari prem `+` a l'inici de cada frase o secció (cada 4, 8 o 16 compassos).
- Cada pulsació crea un punt d'ancoratge en el temps ($t_k$).
- L'app calcula automàticament quants compassos enters ($N$) s'acosten més al BPM de referència en aquest interval:
  $$N = \text{round}\left( \frac{\Delta t \cdot \text{BPM}_{\text{ref}}}{\text{BeatsPerBar} \cdot 60} \right)$$
- S'assigna el BPM matemàtic exacte a l'interval:
  $$\text{BPM}_k = \frac{N \cdot \text{BeatsPerBar} \cdot 60}{\Delta t}$$

### Pas 3: Poliment visual (Re-tempo bidireccional)
- L'usuari atura la reproducció i fa zoom a l'ona.
- Si el marcador ha caigut 40 ms abans del cop real de bombo/bateria, l'usuari agafa la nansa de la frontera i **l'arrossega lliurement damunt del pic de l'ona**.
- En deixar anar:
  - El tram esquerre s'adapta ($\Delta t_1 \rightarrow \text{BPM}_1$).
  - El tram dret s'adapta ($\Delta t_2 \rightarrow \text{BPM}_2$).
  - Els clips posteriors no es desplacen en el temps.

### Pas 4: Correcció mètrica discreta (Si l'oïda es va equivocar de compàs)
- Si un tram no era de 8 compassos sinó de 9 o de 16, l'usuari no mou el temps: selecciona el clip i prem els botons **`+1 compàs`**, **`-1 compàs`**, **`×2`** o **`÷2`**.
- El temps queda quiet i el BPM s'actualitza a l'instant.

---

## 4. Arquitectura i Canvis de Codi Necessaris

### A. Mòdul de càlcul: `app/tempo_map.py`

Cal implementar una funció de **moviment de frontera local** que substitueixi l'antic arrossegament tipus ripple quan s'edita el mapa basat en ancoratges:

```python
def mou_frontera_retempo(trams, idx_frontera, nou_t, durada, offset=0.0):
    """
    Mou la frontera interior entre trams[idx_frontera - 1] i trams[idx_frontera].
    Conserva els compassos enters (N) de tots dos costats i recalcula
    els seus BPMs respectius. Cap altre tram del tema no es mou.
    """
```

*Lògica de la funció:*
1. Identificar $Tram_A$ (esquerra) i $Tram_B$ (dreta).
2. Obtenir el nombre de compassos actual $N_A$ i $N_B$ a partir de la seva durada i BPM previs.
3. Verificar els límits físics: `nou_t` no pot superar `ini_A + durada_minima` ni `fi_B - durada_minima`.
4. Recalcular:
   $$\Delta t_A = \text{nou\_t} - \text{ini}_A \implies \text{BPM}_A = \frac{N_A \cdot \text{bq} \cdot 60}{\Delta t_A}$$
   $$\Delta t_B = \text{fi}_B - \text{nou\_t} \implies \text{BPM}_B = \frac{N_B \cdot \text{bq} \cdot 60}{\Delta t_B}$$
5. Retornar la llista de trams actualitzada i validada.

També caldrà la funció d'ajust discret de compassos:

```python
def canvia_compassos_tram(trams, idx, delta_compassos, durada, offset=0.0):
    """
    Modifica N (ex: +1, -1, x2, /2) mantenint immòbils els segons (ini, fi).
    Recalcula el BPM del tram directament.
    """
```

---

### B. Unificació a la capa gràfica: `app/timeline_layers.py` i `app/timeline.py`

1. **Interactivitat dels marcadors:**
   - La frontera del carril de tempo (`TempoLayer`) i el marcador visual han de respondre de manera unificada.
   - Les nanses de frontera a `TempoLayer` no han de buscar línies de compàs prèvies durant el drag; han de seguir la posició lliure del ratolí (amb suport d'snap a transitoris/ona si es desitja).
2. **Visualització en temps real (drag):**
   - Durant el `mouseMoveEvent`, la línia guia vertical acompanya el ratolí.
   - En el `mouseReleaseEvent`, s'executa `mou_frontera_retempo` i s'aplica el canvi dins del sistema de Desfer/Refer (`editFinished`).

---

### C. Gestor del model: `app/visor.py`

1. Sincronitzar `self.marcadors` amb les fronteres de `self.tempo_trams`:
   - Els marcadors ja no han de ser una llista independent sense connexió. Les fronteres de tempo interiors representen els punts d'ancoratge clau.
2. Afegir els accessos ràpids a la franja Editor o al menú contextual del tram de tempo:
   - Botons o opcions de menú: *Afegir 1 compàs*, *Restar 1 compàs*, *Doblar compassos (×2)*, *Dividir compassos (÷2)*.

---

## 5. Casos Extrems i Regles de Seguretat

| Cas Extrem | Comportament requerit |
| :--- | :--- |
| **Primer tram (abans del Compàs 1)** | Es tracta com a compte enrere / zona pre-música. Admet compàs parcial o tempo lligat al primer compàs útil. |
| **Últim tram (cua de la cançó)** | S'allarga fins a la fi de la WAV. Pot contenir un compàs incomplet a la sortida (fade-out/cua de reverberació) sense invalidar la regla interior. |
| **Col·lisió de fronteres** | El ratolí no pot apropar una frontera a menys d'un límit mínim de seguretat respecte a la frontera veïna (per exemple, $\ge 0.5\text{ s}$). |
| **BPMs extrems** | Si l'arrossegament produeix un tempo absurd ($<30\text{ BPM}$ o $>350\text{ BPM}$), la UI ha d'alertar visualment o limitar el recorregut físic de la nansa. |

---

## 6. Pla de Proves per a l'Agent de Codi

Abans de donar la tasca per finalitzada, l'agent haurà d'afegir i verificar els tests següents a la suite (`tests/`):

1. **Test de retempo bidireccional pur:**
   - Donats dos trams contigus (ex: 8 compassos a 120 BPM = 16 s cadascun, total 32 s).
   - Moure la frontera central de $16\text{ s}$ a $18\text{ s}$.
   - Verificar que el Tram 1 manté 8 compassos i passa a $\approx 106,66\text{ BPM}$.
   - Verificar que el Tram 2 manté 8 compassos i passa a $\approx 137,14\text{ BPM}$.
   - Verificar que cap altre tram no s'ha mogut i que la cobertura total continua sent 32 s exactes.
2. **Test de no-bloqueig del validador:**
   - Comprovar que el mapa resultant de qualsevol moviment de frontera passa `valida_i_normalitza_compassos` sense aixecar cap `ValueError`.
3. **Test de modificació discreta de compassos:**
   - Donat un tram de $8\text{ s}$ amb 4 compassos (120 BPM).
   - Executar `canvia_compassos_tram(+1)` $\rightarrow$ passa a 5 compassos i $\text{BPM} = 150$, mantenint la durada exacta de $8\text{ s}$.
4. **Test de Desfer/Refer:**
   - Verificar que arrossegar una frontera i desfer (`Ctrl+Z`) retorna els BPMs i els segons exactes previs en una sola operació atòmica.