# Edició bàsica d'àudio — proposta de producte

> **Estat: planificada; encara no implementada.** Aquest document descriu
> l'abast acordat per començar. No canvia les regles canòniques de
> [`REGLES_DE_LA_APP.md`](REGLES_DE_LA_APP.md).

## Objectiu

AUTO CHORDS ha de servir tant per preparar una cançó per a l'anàlisi musical
com per fer-hi una edició d'àudio molt bàsica. La inspiració d'Audacity és el
flux fàcil d'entendre —importar, veure la forma d'ona, editar, desfer i exportar—
, no reproduir totes les eines d'un editor d'àudio general.

## Flux previst

1. **Importar un fitxer d'àudio.** Sempre s'obri o es crea un projecte; no hi
   haurà un mode d'editor ràpid separat. L'anàlisi musical és opcional: es pot
   usar el projecte només per editar i exportar l'àudio, sense extraure acords.
   L'app pot acceptar els formats d'entrada que ja reconeix. El format intern
   de treball continua sent **WAV PCM 16 bits**. Si l'entrada no és un WAV
   compatible, es converteix directament en l'única còpia de treball `audio/`
   del projecte; no es deixa un WAV intermedi extra al costat de l'original.
2. **Editar els extrems sobre la forma d'ona.** Amb nanses visibles es pot
   retallar l'inici o el final. Arrossegar més enllà de l'àudio existent afegeix
   silenci: no s'estira ni s'altera el so.
3. **Previsualitzar mentre s'arrossega.** En deixar anar la nansa, s'aplica el
   canvi a la còpia WAV del projecte com una sola acció que es pot desfer amb
   `Ctrl+Z`. L'app no demana confirmació per a cada gest. L'ajust de les nanses
   a les línies de compàs es pot activar o desactivar. El tall s'ajusta al punt
   de pas per zero més pròxim per reduir clics; no s'apliquen fades automàtiques.
4. **Ajustar compassos si l'usuari ho demana.** La proposta d'afegir silenci
   automàtic per completar compassos es mostra abans d'aplicar-la i necessita
   confirmació explícita.
5. **Mantindre l'àudio i la música sincronitzats.** En retallar l'inici,
   s'elimina el que queda abans del tall i l'àudio restant, els acords, les
   seccions, els marcadors i el mapa musical es desplacen junts cap a zero.
   En retallar el final, el model s'ajusta al nou final: s'eliminen els elements
   que queden fora i s'escurcen els que travessen el tall. Un únic `Ctrl+Z`
   restaura àudio i model. En afegir silenci a l'inici, el material existent es
   desplaça amb l'àudio; en afegir-lo al final, el model s'estén fins al nou
   final.
6. **Representar el silenci afegit.** Es crea un tram d'acord `N` (sense acord)
   sobre el silenci nou; la secció existent continua cobrint-lo. Així no
   s'atribueix un acord inventat a un interval sense so musical.
7. **Exportar l'àudio editat.** «Exporta àudio…» demana carpeta, nom i format;
   usa una qualitat predeterminada senzilla, sense opcions tècniques de còdec,
   bitrate o freqüència de mostreig. Exporta sempre el WAV sencer a un fitxer
   nou i no sobreescriu ni l'original importat ni el WAV de treball.

## Abast inicial

- Edició només al principi i al final: retallar àudio existent o afegir silenci.
- En editar, previsualització durant l'arrossegament i aplicació en deixar anar;
  una operació equival a un sol `Ctrl+Z`. Només la proposta automàtica de
  silenci per completar compassos demana confirmació.
- L'ajust de les nanses a les línies de compàs és commutable.
- Els talls s'ajusten al pas per zero més pròxim per reduir clics; no s'afegeixen
  fades automàtiques.
- Si s'afegeix silenci, es manté el model sincronitzat: `N` per al tram sense
  acord i la secció existent cobrint-lo.
- Conversió/exportació amb FFmpeg a una selecció curta de formats comuns:
  **WAV, MP3, FLAC, AAC/M4A, OGG i Opus**. Cal verificar quins encoders estan
  disponibles en cada FFmpeg distribuït abans de tancar l'oferta de formats.
- Exportació de tot el WAV editat; exportar només una selecció i ajustar
  opcions tècniques de qualitat queden per a més endavant.
- L'edició d'àudio sempre es fa dins d'un projecte; no hi haurà un mode
  independent. Es pot crear/obrir el projecte i editar/exportar el WAV sense
  executar l'anàlisi musical.
- Cap tall, enganxat o duplicació al mig; cap canvi de velocitat o to, fades,
  mescla, normalització ni processament en lot en aquesta primera versió.
- L'original de fora del projecte es conserva intacte. El projecte conté una
  sola còpia editable en WAV; les exportacions són fitxers derivats separats.

## Regles i punts previs a implementar

- El desplaçament del model en retallar/afegir silenci al principi i la
  representació `N` són decisions de producte acordades, però s'han de validar
  contra la regla de cobertura i §13 abans de codificar-les.
- El punt de tall proper al pas per zero ha de quedar prou pròxim a la posició
  triada i reduir clics sense alterar de manera audible el fragment. Cal validar
  el comportament amb senyals sintètics mono i estèreo.
- El canvi d'àudio i els canvis del model musical han de ser atòmics i desfer-se
  junts. Cal dissenyar com es desa l'historial d'àudio sense duplicar fitxers
  innecessàriament.
- La còpia de treball s'ha d'escriure primer en un temporal, validar-se i només
  després substituir la còpia del projecte. Si falla la conversió o la
  validació, no es modifica el projecte.
- Les regles d'or vigents, inclosa la regla 6 sobre WAVs generades i el §13
  sobre segons, graella i cobertura, continuen manant. Abans d'implementar, cal
  revisar el contracte i demanar aprovació explícita si el comportament proposat
  requereix canviar-lo; no s'ha de canviar el contracte per iniciativa pròpia.

## Inspiració en Audacity

Es pren com a referència la separació clara entre una forma d'ona editable, les
accions de desfer/refer i el diàleg d'exportació amb carpeta, nom i format. AUTO
CHORDS manté el seu enfocament més limitat i musical: una sola còpia WAV de
treball per projecte i edició només als extrems.

Referències oficials:
- [Audacity: Export Audio](https://manual.audacityteam.org/man/file_export_dialog.html)
- [Audacity: Edit Menu](https://manual.audacityteam.org/man/edit_menu.html)
- [Audacity: Audio Tracks](https://manual.audacityteam.org/man/audio_tracks.html)
