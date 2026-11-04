# Edició bàsica d'àudio — abast i estat

> **Estat: implementada (Fase 6, 2026-11-02).** La importació converteix al
> projecte, els backups inclouen el WAV i els marcadors, es poden retallar o
> ampliar els extrems amb nanses, previsualització i desfer/refer, i
> **«Exporta àudio…»** desa la còpia de treball amb FFmpeg a un fitxer nou.
> Continuen pendents la restauració d'una còpia des de la GUI i la validació
> funcional dels 3 paquets.
>
> **PENDENT EXPLÍCIT (2026-11-04): l'edició automàtica/directa de la WAV per
> completar el pre-roll o el primer compàs no està implementada i no s'ha
> d'implementar en esta fase.** L'edició manual de les nanses que ja existix
> queda congelada: no s'hi han d'introduir canvis que trenquen el flux actual.
> Aquest document descriu l'abast acordat. No canvia les regles canòniques de
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
   de treball continua sent **WAV PCM 16 bits**. Si l'entrada no és compatible,
   es converteix directament en l'única còpia de treball `audio/` del projecte;
   no es deixa un WAV intermedi extra al costat de l'original. **Implementat.**
2. **Editar els extrems sobre la forma d'ona.** Amb nanses visibles es pot
   retallar l'inici o el final. Arrossegar més enllà de l'àudio existent afegeix
   silenci: no s'estira ni s'altera el so. **Implementat** a `TimelineView`.
3. **Previsualitzar mentre s'arrossega.** En deixar anar la nansa, s'aplica el
   canvi a la còpia WAV del projecte com una sola acció que es pot desfer amb
   `Ctrl+Z`. L'app no demana confirmació per a cada gest. L'ajust de les nanses
   a les línies de compàs es pot activar o desactivar. El tall queda al punt
   triat, arrodonit al fotograma més pròxim; no es mou per buscar un pas per
   zero. S'aplica un fade d'entrada/eixida de **4 ms** a cada nova vora entre
   àudio i silenci per evitar clics. **Implementat i cobert amb proves.**
4. **Ajustar compassos si l'usuari ho demana — PENDENT.** La proposta
   d'afegir silenci automàtic per completar el primer compàs o el pre-roll
   queda per a més endavant. No està implementada hui. Quan es faça, haurà de
   mostrar el temps de silenci proposat abans d'aplicar-lo i necessitar
   confirmació explícita; mentrestant, el codi actual no ha de tocar la WAV
   per esta via.
5. **Mantindre l'àudio i la música sincronitzats.** En retallar l'inici,
   s'elimina el que queda abans del tall i l'àudio restant, els acords, les
   seccions, els marcadors i el mapa musical es desplacen junts cap a zero.
   En retallar el final, el model s'ajusta al nou final: s'eliminen els elements
   que queden fora i s'escurcen els que travessen el tall. Un únic `Ctrl+Z`
   restaura àudio i model. En afegir silenci a l'inici, el material existent es
   desplaça amb l'àudio; en afegir-lo al final, el model s'estén fins al nou
   final. Àudio, CSV i marcadors es publiquen junts i una fallada restaura
   l'estat anterior. **Implementat**, inclòs el desfer/refer compartit.
6. **Representar el silenci afegit.** Es crea un tram d'acord `N` (sense acord)
   sobre el silenci nou; la secció existent continua cobrint-lo. Així no
   s'atribueix un acord inventat a un interval sense so musical.
7. **Exportar l'àudio editat.** «Exporta àudio…» obri el **diàleg natiu de
   desar**; l'usuari tria carpeta, nom i perfil: **WAV** 16 bits (mostreig
   original, 44,1 o 48 kHz), 24 bits i 32 bits float; **MP3** 128/192/320 kbps;
   **FLAC** 16 bits; **AAC/M4A** 256 kbps; **OGG Vorbis** q6; **Opus** 160 kbps.
   Només s'ofereixen els perfils que el `ffmpeg` del paquet pot escriure de
   debò (es consulta `-encoders` en temps d'execució). Exporta sempre el WAV
   sencer a un fitxer nou, de manera atòmica, i no sobreescriu el WAV de
   treball. Si tries un fitxer existent (inclòs l'original importat), el
   diàleg natiu demana confirmació abans de substituir-lo.
   **Implementat (2026-11-02).**

## Abast inicial

- Edició només al principi i al final: retallar àudio existent o afegir silenci.
- En editar, previsualització durant l'arrossegament i aplicació en deixar anar;
  una operació equival a un sol `Ctrl+Z`. Només la proposta automàtica de
  silenci per completar compassos demana confirmació.
- L'historial comú de desfer/refer conserva les 10 últimes accions totals,
  incloent-hi les del model musical i les d'àudio, perquè sempre es desfacen
  juntes; en superar el límit, s'avisa que l'acció més antiga ja no es pot
  recuperar.
- L'ajust de les nanses a les línies de compàs és commutable.
- El commutador de snap existent del timeline s'aplica també a les nanses.
- Els talls es fan al punt triat (fotograma més pròxim). Cada nova vora entre
  àudio i silenci rep un fade automàtic de 4 ms, inspirat en el comportament
  predeterminat d'Ableton Live per a les vores dels clips.
- El crossfade és entre dos clips amb àudio; queda ajornat perquè la primera
  versió només edita els extrems d'un WAV, sense talls ni unions interns.
- Si s'afegeix silenci, es manté el model sincronitzat: `N` per al tram sense
  acord i la secció existent cobrint-lo.
- Conversió/exportació amb FFmpeg a una selecció curta de formats comuns:
  **WAV, MP3, FLAC, AAC/M4A, OGG i Opus**, amb perfils senzills. La
  disponibilitat de cada còdec es detecta en temps d'execució (`-encoders`),
  així que la UI només ofereix el que el paquet de cada SO porta de debò.
- Exportació de tot el WAV editat; exportar només una selecció i ajustar
  opcions tècniques de qualitat queden per a més endavant.
- L'edició d'àudio sempre es fa dins d'un projecte; no hi haurà un mode
  independent. Es pot crear/obrir el projecte i editar/exportar el WAV sense
  executar l'anàlisi musical.
- Cap tall, enganxat o duplicació al mig; cap canvi de velocitat o to, fade
  ajustable, mescla, normalització ni processament en lot en aquesta primera
  versió. Només s'hi apliquen els fades automàtics de 4 ms descrits abans.
- L'original de fora del projecte es conserva intacte. El projecte conté una
  sola còpia editable en WAV; les exportacions són fitxers derivats separats.

## Contracte i validacions pendents

- El contracte per a la transformació conjunta de l'àudio i el model ja està
  aprovat i documentat al §13.9 de
  [`REGLES_DE_LA_APP.md`](REGLES_DE_LA_APP.md). La regla de cobertura continua
  sent obligatòria en tots els tres carrils.
- El tall ha de correspondre al fotograma més pròxim a la posició triada; cal
  validar amb senyals mono i estèreo que els fades de 4 ms eviten clics sense
  alterar de manera audible el fragment.
- El canvi d'àudio i els canvis del model musical es desen junts i es desfan
  junts. L'historial conserva snapshots temporals només dels estats necessaris
  per a les 10 accions recuperables.
- Les còpies de seguretat versionades ja inclouen el WAV de treball i es
  publiquen quan la còpia temporal està completa. La signatura de canvi del WAV
  usa mida i data de modificació per evitar llegir-lo sencer a cada autosave.
  Les proves cobreixen la còpia dels marcadors i les operacions d'àudio. Això
  pot augmentar l'espai ocupat; la rotació existent limita el nombre de còpies.
- La conversió d'entrada s'escriu primer en un temporal dins `audio/`, es
  valida i només després es publica com a WAV de treball. La conversió i la
  còpia del WAV als backups tenen proves. Les transformacions als dos extrems,
  cobertura, offset, desfer/refer mixt i una fallada de publicació tenen proves
  de regressió. L'**exportació d'àudio** també té proves (perfils, detecció
  d'encoders, atomicitat i protecció de la còpia de treball).
  Encara falta la **restauració d'una còpia des de la GUI** i les proves
  visuals de previsualització. La regla 6 i la resta del §13 continuen vigents.

## Pendent explícit — edició automàtica de la WAV des del mapa

> **No implementat. No modificar el flux actual d'edició manual.**

- Cas: l'offset (compàs 1) cau massa a prop de l'inici perquè el primer clip
  puga ser un compàs sencer amb el BPM/compàs adequat.
- Comportament actual: `Compàs 1 aquí` parteix el mapa i recalcula el pre-roll
  amb el millor compàs admissible; si no n'hi ha cap, **no afegix silenci** ni
  modifica la WAV per completar-lo.
- Proposta futura: oferir un diàleg amb el silenci necessari i, només amb
  confirmació, inserir-lo amb l'eina d'edició existent i desplaçar de manera
  atòmica tots els elements musicals.
- Abans d'implementar-ho cal resoldre: conservació de rubato, tipus de
  marcador, desplaçament dels beats QM, persistència exacta de l'offset i un
  únic desfer.
- **Restricció:** no s'ha de trencar res del flux actual de retall/afegit manual
  de silenci, desfer/refer, backups ni exportació.

## Inspiració en Audacity

Es pren com a referència la separació clara entre una forma d'ona editable, les
accions de desfer/refer i el diàleg d'exportació amb carpeta, nom i format. AUTO
CHORDS manté el seu enfocament més limitat i musical: una sola còpia WAV de
treball per projecte i edició només als extrems.

Referències oficials:
- [Audacity: Export Audio](https://manual.audacityteam.org/man/file_export_dialog.html)
- [Audacity: Edit Menu](https://manual.audacityteam.org/man/edit_menu.html)
- [Audacity: Audio Tracks](https://manual.audacityteam.org/man/audio_tracks.html)
- [Ableton Live 12: Audio Clip Fades and Crossfades](https://www.ableton.com/en/live-manual/12/arrangement-view/#fades-and-crossfades)
- [Audacity: Crossfade Clips](https://manual.audacityteam.org/man/crossfade_clips.html)
