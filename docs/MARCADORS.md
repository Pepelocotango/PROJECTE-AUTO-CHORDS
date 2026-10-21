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

I **res més**: a partir d'ací el marcador és **independent**. Si mous, fusiones
o esborres eixos clips, el marcador es queda on el vas posar (es pinta com una
**ratlla groga discontínua** amb banderí, damunt de tot).

## Del marcador al BPM (el pas que ho fa editable)

Els marcadors són a **inicis de compàs**, així que la distància entre dos ha de
ser un **nombre enter de compassos**. Amb dos o més marcadors:

1. *Analitza ▸ **BPM a partir dels marcadors…***
2. S'obri la llista de BPM compatibles (tots fan que els talls siguen compassos
   sencers). L'ambigüitat del doble/meitat és real (10 s poden ser 4 compassos a
   96 o 6 a 144), així que **triues tu**; el primer de la llista és el més a prop
   del BPM de la barra.
3. En aplicar-lo, cada interval passa a tindre **exactament `k` compassos** al
   BPM d'eixe interval → **totes les fronteres cauen en línia de compàs** i els
   clips de tempo/compàs **tornen a ser editables** (canviar BPM, moure vores,
   suprimir, fusionar…). L'offset passa a ser el primer marcador.

Sense este pas, els talls dels marcadors no són línies de compàs (el BPM de la
barra encara no és el bo) i l'editor estricte els rebutja amb «La frontera … no
cau en una línia de compàs». **Els marcadors no es toquen**: seguixen on eren.

## On es guarden

`marcadors.csv` dins del projecte (una columna `t_s`), i al desfer/refer
(Ctrl+Z) tornen enrere amb la resta de l'edició.

## Per què així

El motor **no pot** endevinar els inicis de compàs d'un tema real (no és una
propietat acústica), i les xarxes neuronals no són viables en este equip
(sense AVX). Per tant: **l'operador declara, el motor encaixa**. Els marcadors
són la declaració mínima (un instant), sense lligar l'usuari a un flux.
