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

1. **Importar un fitxer d'àudio.** L'app pot acceptar els formats d'entrada que
   ja reconeix. El format intern de treball continua sent **WAV PCM 16 bits**.
   Si l'entrada no és un WAV compatible, es converteix directament en l'única
   còpia de treball `audio/` del projecte; no es deixa un WAV intermedi extra
   al costat de l'original.
2. **Editar els extrems sobre la forma d'ona.** Amb nanses visibles es pot
   retallar l'inici o el final. Si s'allarga més enllà de l'àudio existent,
   s'afegeix silenci: no s'estira ni s'altera el so.
3. **Previsualitzar i confirmar.** La proposta d'afegir silenci per encaixar
   l'inici o el final en compassos sencers es mostra abans d'aplicar-la i només
   s'executa amb confirmació. Les edicions són desfetes/repetibles; un error no
   pot deixar l'àudio i el mapa musical en estats diferents.
4. **Exportar l'àudio editat.** Una acció separada, «Exporta àudio…», demana
   carpeta, nom i format. L'exportació crea un fitxer nou i no sobreescriu ni
   l'original importat ni el WAV de treball del projecte.

## Abast inicial

- Edició només al principi i al final: retallar àudio existent o afegir silenci.
- Conversió/exportació amb FFmpeg a una selecció curta de formats comuns:
  **WAV, MP3, FLAC, AAC/M4A, OGG i Opus**. Cal verificar quins encoders estan
  disponibles en cada FFmpeg distribuït abans de tancar l'oferta de formats.
- Cap tall, enganxat o duplicació al mig; cap canvi de velocitat o to, fades,
  mescla, normalització ni processament en lot en aquesta primera versió.
- L'original de fora del projecte es conserva intacte. El projecte conté una
  sola còpia editable en WAV; les exportacions són fitxers derivats separats.

## Regles i punts previs a implementar

- Retallar l'inici pot moure el temps zero i l'offset; retallar el final canvia
  la durada. Cal definir com es mantenen coherents els acords, l'estructura, els
  marcadors, el mapa de tempo i la cobertura del projecte.
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
