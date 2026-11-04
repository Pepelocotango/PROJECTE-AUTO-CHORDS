# Marcadors (inici de compàs en viu)

> **Què és:** l'eina de treball per posar la graella d'un tema que no és
> perfectament regular, sense diàlegs ni assistents. Substituïx, en la
> pràctica, l'«Anàlisi guiat» interactiu (v2 per trams i v3 per ancoratges,
> tots dos en **stand by**).

## Com es fa servir

1. **Obre àudio** i prem **Espai**.
2. Cada vegada que comence un compàs, prem **`+`** (el de dalt o el del teclat
   numèric) o el botó **＋ Marker**.
3. Si t'equivoques: **Ctrl+Z** o *Analitza ▸ Esborra l'últim marcador*.

El `+` funciona **també mentre sona** i no et roba la tecla si estàs escrivint
en un camp (nom d'acord, BPM…).

## Què fa exactament

En crear-se, un marcador **talla dos carrils** en eixe instant:

- **BPM/compàs**: comença un clip de tempo nou (mateix BPM; després el pots
  canviar o arrossegar la vora).
- **Estructura**: comença una secció nova (parteix la que hi havia).

A partir d'ací, el marcador **seguix la frontera de tempo** (regla
**§13.6** de `docs/REGLES_DE_LA_APP.md`, decisió de l'operador 21-10-2026):

- si **mous** la frontera, el marcador **hi viatja** (i torna enrere amb el
  desfer);
- si la frontera **desapareix** (eliminar o fusionar el tram), el marcador
  **s'esborra** amb ella;
- el clip d'**estructura** que es va crear en eixe punt la seguix per
  coincidència de temps (±5 ms) fins que l'edites a mà.

Es pinta com una **ratlla groga discontínua** amb banderí, damunt de tot.

## Del marcador al BPM (el pas que ho fa editable)

Els marcadors són a **inicis de compàs**, però el contracte actual no exigix
compassos enters: cada clip ha de contindre **almenys un beat sencer** de la
graella del Snap (QM si el Snap és «Beats QM»; BPM/compàs en la resta de modes).
Amb dos o més marcadors:

1. *Analitza ▸ **BPM a partir dels marcadors…*** o **Ajusta BPMs a partir dels
   marcadors per trams**.
2. L'ajust conserva el BPM de referència sempre que pot; si el clip no encaixa,
   canvia el compàs (`4/4` → `4/8`…) i, només com a últim recurs, acosta el BPM
   sense anar a la meitat ni al doble.
3. L'offset (downbeat) **no es mou**: continua sent el que hi havia; només canvia
   si l'edites explícitament.

El `+` sempre s'encaixa al **beat QM més pròxim**. Si no hi ha beats QM, no crea
el marcador i avisa.

## On es guarden

`marcadors.csv` dins del projecte (una columna `t_s`), i al desfer/refer
(Ctrl+Z) tornen enrere amb la resta de l'edició.

## Per què així

El motor **no pot** endevinar els inicis de compàs d'un tema real (no és una
propietat acústica), i les xarxes neuronals no són viables en este equip
(sense AVX). Per tant: **l'operador declara, el motor encaixa**. Els marcadors
són la declaració mínima (un instant), sense lligar l'usuari a un flux.
