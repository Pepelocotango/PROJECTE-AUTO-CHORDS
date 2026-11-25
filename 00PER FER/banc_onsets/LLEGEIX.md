# Banc sintètic d'atacs · Fase 0.A · generador v1

**Aquest paquet NO executa cap detector.** No importa `app.tempo` (ho comprova una
autoprova). Només genera senyals amb referència analítica i inclou l'anotador virtual.

## Contingut

| Fitxer | Funció |
|---|---|
| `banc_onsets/generador.py` | Condicions v1, síntesi, referències, escriptura de WAV, CLI |
| `banc_onsets/anotador_virtual.py` | Criteri humà revisat (3 x RMS de la finestra de 20 ms més silenciosa dels 100 ms previs; sostingut ≥1 ms; 5 % del pic només diagnòstic) |
| `banc_onsets/autotest_generador.py` | 11 autoproves del propi generador |
| `banc_onsets/informe_anotador_virtual.py` | Predicció del biaix `t10 - t_anotat` per condició |

Dependències: `numpy`, `scipy`. Python 3.10+.

## Ús (des de l'arrel del paquet)

```
python3 -m banc_onsets.autotest_generador
python3 -m banc_onsets.generador --conjunt dev --sortida /ruta/dev_v1          # 87 condicions x 30 llavors
python3 -m banc_onsets.generador --conjunt dev --sortida /ruta/dev --grups A,N --reps 5
python3 -m banc_onsets.informe_anotador_virtual --reps 30
```

Sortida del generador: `parametres_v1.json`, `casos.jsonl` (un cas per línia, amb
llavor, `t0`, A, B, referències, esperat per punt d'entrada, criteri) i els WAV per
`grup/condició/sNNNNN.wav`.

**Validació bloquejada:** `--conjunt val` exigeix `--permet-validacio` i
`--hash-congelat` igual al hash actual dels paràmetres.

Hash actual dels paràmetres (informatiu; el congela l'operador):
`995f198c891bf9436eab9e48278b485472b60e5ce3ae1884f4f7eedd35a87099`

## Decisions d'aquest build que l'operador ha de confirmar abans de congelar

1. **SNR «net» = 60 dB.** SNR = pic de |x| del senyal net de l'objectiu a [t0, t0+80 ms] / RMS del soroll.
2. **C3:** A = 20 ms abans del 10 %, de manera que l'esdeveniment previ queda fora de [A,B) i només actua de màscara.
3. **Grup D:** s'ometen combinacions sense energia (bombo/passaalt, acord/passaalt).
4. **Opcionals fora de l'especificació congelada** (5 condicions, exclosos per defecte, `--opcionals`): *flam* (10/15/30 ms) i la frontera del marge (+29/+31 ms).
5. **E amb `detecta_onsets` a A = 10 %:** marcat «frontera» (informatiu).
6. **Anotador, «20 ms previs»:** `fix` (finestra abans de la zona de cerca) per defecte; `lliscant` disponible.
7. **Estèreo:** `un_canal` = L amb R en silenci; `estereo_correlat` = R = 0,9 L.
8. **F1b** (conversió per ffmpeg a l'app) no hi és: aquí només hi ha els fitxers.
9. **G:** fade-in 0,6 s, DC 0,02, clipping amb pic 1,4 retallat a 1,0.
10. Durada 0,9 s, `t0 = 0,300 s + U[0, 10 ms)`, llavors dev 1..reps, val 10001+.
