# Handoff: bol-repricing (NL/Tiptopshop) chat

Startdocument voor elke nieuwe chat op dit project. Oorspronkelijk
geschreven bij de OneDrive-migratie van 25 juli, sindsdien bijgehouden.

**Laatst bijgewerkt: 12 september 2026, 19:00** (dag 4 schoon, bevroren 194;
"Run failed"-oorzaken van deze week vastgelegd).

Wijzigingen in omgekeerde volgorde (nieuwste eerst): optimize-limiet 200 +
tellersplitsing (3 sept), margeherstel op echte concurrentprijzen (1-2 sept,
zie het blok hieronder), taakplanner-automatisering (17-22 aug), CSV via de
Contents-API (18 aug), gewonnen-prijs-inverse (30 juli), bevroren-drift
omlaag klemmen (29 juli), bodembewaking + afrondfix (27 juli),
retry-verruiming (26 juli), `no_competitor.json` (25 juli),
bodemprijs-formule (23 juli).

## STAND BIJ DE OVERDRACHT (4 september, middag)

Het systeem draait volledig automatisch. Peter uploadt 's ochtends het
bestand (vóór 08:10 op werkdagen, vóór 09:40 in het weekend), verder niets.
Begin elke sessie met `automation_log.json` via de Contents-API.

Ruwe cijfers: ~150-200 producten per dagexport, 194 bevroren artikelen,
cron 24 runs/dag, audit al weken schoon.

### De levertijdregel is bewezen op de scherpe rand (3 sept)

| dag | optimize | sync 13:30 | bevroren na sync |
|---|---|---|---|
| 1 sept (oude regel, 125 verhoogd) | - | **-79** | 82 |
| 2 sept (nieuwe regel, 40 bekeken) | 2 verhoogd, 17 overgeslagen | 0 verloren | 159 |
| 3 sept (nieuwe regel, 40 bekeken) | 2 verhoogd, 17 overgeslagen | 1 verloren (niet verhoogd) | 178 |

De twee verhoogde artikelen (8716522090673 en 8716522094817) gingen op
2 sept naar EUR134,85 (EUR5-limiet) en op 3 sept naar **EUR135,94, één
cent onder Izziet, die 5 dagen later levert** - en hielden het koopblok bij
de sync van 13:30. Het enige verlies van 3 sept (8716522089691, EUR34,40)
was niet verhoogd; gewone dagverliezer.

De overgeslagen groep, voor het eerst uitgesplitst (3 sept): **17 =
levertijd onleesbaar 2 + even snel 9 + sneller 6.** De blinde vlek is dus
klein; de grote groep is "even snel" (7 tegen 7 kalenderdagen, vrijwel
allemaal Bohemian Living NL). Bij een deel was er sowieso geen ruimte
(EUR60,94 tegen EUR60,95). Sebic - CAN-Interiors zit in de "sneller"-groep
(5 tegen 7) en is op beide markten structureel snel.

**Tegenbewijs van BE, dezelfde dag.** BE verhoogde op 3 sept 43 artikelen
ZONDER levertijdrem: 6 verloren, allemaal uit de groep "tegen een
concurrent". Uitgesplitst: concurrent trager 3 van 3 gehouden, even snel
of sneller 2 van 7. De 33 EUR5-stapjes zonder concurrent: 0 verloren. Dat
is onze regel, op hun markt gemeten. BE gaat dezelfde rem bouwen.

### Optimize-limiet van 40 naar 200 (3 sept, 15:00, Peter akkoord)

Eén getal in `scheduled_run.py`. Reden: `phase_optimize` pakt de EERSTE n
uit `frozen.json`, ongesorteerd, dus met 40 werden elke dag dezelfde 40 van
~160 bekeken (de oudst bevroren) en de rest nooit. **Eerste brede run:
4 sept, 10:00.** Verwacht ~2,5 min in plaats van ~1.

**Wat je op 4 sept ziet en wat normaal is.** Er komen 138 artikelen bij die
nooit bekeken zijn. In de eerste 40 was 30% "geen concurrent" (EUR5-stap,
94% behoud, bij BE 0 van 33 verloren) en ~5% "concurrent trager". Reken
dus op tientallen verhogingen in één run, vooral EUR5-stapjes. Dat is de
bedoeling, geen storing. Bij de sync van 13:30 is een verlies per artikel
te herleiden: de tabel `EAN / nu / wordt / erbij / reden` staat in
`logs/automation-2026-09.log` (lokaal), online alleen de tellers.

## VERKOPERBEWUST OPTIMIZE (8 sept, 15:30, Peter: "als het een verbetering is mag je bouwen, maar controleer dagelijks")

`phase_optimize` in `src/probe_recovery.py` is herschreven (backup van de
oude versie in de scratchpad van de chat van 8 sept; de oude logica staat
in de git-historie op GitHub). Drie wijzigingen, alle drie uit de metingen
van 1-8 sept:

1. **Verkoperlijsten** (bovenaan de functie, makkelijk aan te passen):
   - `VERKOPERS_VLAK_ONDER = ("bohemian living", "cactula", "izziet")` ->
     tot `UNDERCUT` eronder, ongeacht levertijd (max `MAX_STAP` per ronde).
   - `VERKOPERS_NOOIT = ("cammeraat", "bouwkern", "sebic")` -> nooit verhogen.
   - Alle andere verkopers: de levertijdregel van 2 sept blijft (alleen
     tegen een aantoonbaar tragere concurrent).
   Match op het BEGIN van de naam, kleine letters.
2. **Cooldown na verlies-na-verhoging** via `optimize_history.json` op
   GitHub (via de Contents-API gelezen, altijd geschreven). Bij de start
   van elke run kijkt `registreer_verliezen` welke artikelen die hooguit 3
   dagen geleden verhoogd zijn niet meer bevroren staan (of lager
   teruggewonnen zijn): die krijgen `verloren`/`verloren_op`. Gevolg:
   `COOLDOWN_NA_VERLIES` (7) dagen niets, daarna nooit hoger dan
   `verloren_op - PLAFOND_MARGE` (EUR1). Wint het artikel later op of boven
   die prijs, dan wordt het record gewist. Logregel: `[VERLIES] ean: ...`.
3. **"Geen concurrent" pas na bevestiging**: alleen stappen als een eerdere
   run (max `GEEN_CONC_BEVESTIGING_DAGEN` = 3 dagen terug) ook geen
   concurrent zag; nooit boven de laatst geziene concurrent
   (`CONC_GEHEUGEN_DAGEN` = 7); en helemaal niet als die laatst geziene een
   NOOIT-verkoper was.

Stub-test op 11 gevallen (8 sept): allemaal in de juiste tak, plafonds
correct (106,00 na verlies op 107; 106,48 onder laatst geziene 106,50),
verliesdetectie werkt. Het geheugen is op 8 sept voorgevuld met 12
artikelen (de flipper met plafond 121,90; de twee momentopname-verliezers;
de 8 "geen concurrent" van vandaag zodat ze morgen meteen bevestigd zijn).

**Nieuwe tellerregel** (online in `automation_log.json`):
`verhoogd: N (vlak-onder-verkoper a, trager b, geen concurrent c) | met rust: M | overgeslagen: O = nooit-verkoper + even snel + sneller + onleesbaar + cooldown + geen conc. wacht + geen conc. geblokkeerd | mislukt: X`
Optelsom: verhoogd + met rust + overgeslagen + mislukt = bekeken. De oude
overlap van `geen concurrent` is hiermee weg.

**Dagelijkse controle (afspraak met Peter, 8 sept) - elke dag na 13:30:**
1. `automation_log.json`: alle vier de taken `ok`; tellerregel optellen.
2. Ochtend-CSV naast de verhoogde EAN's van gisteren (nachtelijke verliezen).
3. Sync: verliezers herleiden - verhoogd? via welke tak? `[VERLIES]`-regels
   van 10:00 kloppen daarmee?
4. Wat te verwachten: vlak-onder-verkopers houden; nooit-verkopers worden
   niet meer verhoogd; de flipper 8716522090192 blijft 7 dagen met rust en
   komt daarna max op 121,90. Verliest een vlak-onder-verkoper toch 2+
   artikelen op één dag -> die verkoper uit `VERKOPERS_VLAK_ONDER` halen.
5. Eerste dag (9 sept): "geen conc. wacht" is hoog (alles zonder seed
   wacht één dag) - normaal.

### TEST "even snel" (4-10 sept, AFGESLOTEN): G1b (5 artikelen +EUR2) en G2 (15 artikelen +EUR1)

Peter's vraag van 4 sept: is het systeem de moeite waard zoals het staat?
Antwoord: ja, maar bij NL is de opbrengst klein, omdat 76 van 176 bevroren
artikelen een concurrent hebben die even snel levert en de regel die groep
overslaat (20% behoud op 1 sept bij "tot 2 cent onder"). De enige knop met
echt geld is die groep. Peter: "tien artikelen, EUR1 tot EUR2 omhoog" ->
"bij EUR2 komt de concurrent in het koopblok, dus maximaal een euro" ->
"probeer eerst 5" -> "werkt het niet, dan gauw terug; dat beslis je zelf,
hoef je niet te vragen".

Script: `src/test_evensnel.py` (`kandidaten` / `start` / `status` /
`revert`), backup in `output/test_evensnel.json` en als
`test_evensnel.json` op GitHub. Selectie: even snel (7/7), goedkoopste
concurrent >= EUR2 boven ons, max 2 per verkoper, gesorteerd op ruimte.
Van 166 bevroren voldeden er 46.

| EAN | was | test | concurrent | ruimte na test |
|---|---|---|---|---|
| 8716522088045 | 91,86 | 92,86 | toonies-woondeco 107,60 | 14,74 |
| 8717266392474 | 81,73 | 82,74 | toonies-woondeco 95,65 | 12,91 |
| 8716522103472 | 420,90 | 421,90 | Bohemian Living NL 432,95 | 11,05 |
| 8716522070163 | 277,93 | 278,94 | Bohemian Living NL 289,95 | 11,01 |
| 8716522110395 | 54,92 | 55,93 | Woonuden-DierenlampenOnline 65,95 | 10,02 |

Wat we meten: NIET "vlak onder de concurrent" maar "+EUR1 terwijl we er nog
EUR10-15 onder zitten". Verliezen we dan tóch, dan is de prijsstijging zelf
(of de derde factor van 4 sept) de oorzaak, niet de nabijheid van de
concurrent - en dan is de hele groep dicht. Houden ze, dan is een tweede
euro de volgende stap.

Channable importeert 's avonds niet: de nieuwe prijzen gaan bij de eerste
import van zaterdagochtend live; de sync van 13:30 meet ze na ~6 uur. De
optimize van 10:00 raakt ze niet (even snel -> overgeslagen), de
snelstart van 09:45 ook niet (bevroren).

**Stand van de test:**

| meting | koopblok bij ons | prijs live? |
|---|---|---|
| za 5 sept 13:38 (`status`, na de sync van 13:30) | **5 van 5** | ja, alle 5 op de testprijs, wij goedkoopste |
| zo 6 sept 13:40 (`status`, na de sync van 13:30) | **5 van 5** | ja |

Beslissing 5 sept: laten staan, zondag opnieuw meten. 6 sept: twee dagen
gehouden -> voorstel aan Peter voor de volgende stap (zie chat/onder).

**Uitbreiding 6 sept 17:15 (Peter: "1 en 2 doen en kijken wat eruit komt").**
Het script werkt nu met GROEPEN, elk met een eigen terugzetpunt
(`output/test_evensnel.json`, ook op GitHub als `test_evensnel.json`):

| groep | wat | terugzetpunt | opbrengst als alles houdt |
|---|---|---|---|
| G1 | de 5 van 4 sept, +EUR1 | originele prijs | (opgevolgd door G1b) |
| **G1b** | dezelfde 5 nog +EUR1 = **+EUR2 totaal**, nog EUR9-14 onder de concurrent | de +EUR1-prijs van G1 | EUR5,00 |
| **G2** | **15 nieuwe** artikelen +EUR1 (toonies 3, Bohemian 3, Cactula 3, Woonuden 2, Cammeraat 3, LaSpada 1) | originele prijs | EUR15,00 |

G1b test Peters verwachting "bij EUR2 verlies je" terwijl we er nog ruim
onder zitten. G2 herhaalt de bewezen stap op meer artikelen. Twee groepen,
dus een verlies is altijd herleidbaar. Let op in G2: 3700837161345 (verloor
op 4 sept op zijn volle prijs 17,77 aan Cammeraat 19,99, teruggewonnen op de
bodem 15,73) staat nu op 16,74.

Commando's: `status` (alle groepen), `status G2`, `revert G1b` (terug naar
+EUR1), `revert G2`. Beslisregel per groep ongewijzigd: 2 of meer verloren
-> die groep terug, zonder te vragen. Eerste meting: sync ma 7 sept 13:30.

Valkuil bij het narekenen (6 sept zelf in getrapt): drie G2-artikelen hebben
een klantprijs onder 4 (1,64). De platte formule `kp*2,4+8` geeft dan een
verkeerde prijs; gebruik `calculate_normal_price` (met de knik). Mijn
controlescript meldde daardoor ten onrechte "12 van 15".

Terzijde: om 17:13 was "levertijd onleesbaar" 17 van 182 (10:00: 5). Zelfde
avondeffect als op 4 sept.

**Beslisregel (door de chat zelf, zonder te vragen):**
- 0 of 1 van 5 verloren bij de sync van 5 sept -> laten staan, zondag nog
  een keer meten (`status`); houdt het twee dagen, dan overleggen over een
  tweede euro of meer artikelen.
- 2 of meer verloren -> `python src/test_evensnel.py revert` voor de
  overblijvers, test afgerond, groep "even snel" blijft dicht.
- Wie verliest gaat sowieso vanzelf via de dagroute terug; `revert` is
  alleen voor de artikelen die nog staan.
- Bij een verlies ALTIJD `status` draaien: wie heeft het koopblok en op
  welke prijs (les van 4 sept).

Terzijde, om 19:20 gemeten: "levertijd onleesbaar" was 11 van 166, om
10:00 was het 3 van 176. De levertijdtekst op bol.com verandert dus in de
loop van de dag (besteldeadline verstreken -> andere formulering). Meet
levertijd-afhankelijke dingen op hetzelfde tijdstip als de dagtaak.

### 9 sept (woensdag): eerste run van het verkoperbewuste optimize

| taak | uitkomst 9 sept |
|---|---|
| **08:48** morning (LAAT, hoort 08:15) | 279 s, ok - de pc heeft de taak 33 min te laat gestart (slaapstand?). Eenmalig gezien; bij herhaling `taken_aanmaken.ps1` / wektimer nakijken |
| 10:00 optimize | 181 bekeken, **4 verhoogd** (+EUR5,86, Bohemian tot 2 cent onder), 38 met rust, 128 overgeslagen (nooit-verkoper 38, even snel 41, sneller 7, onleesbaar 2, cooldown 2, geen conc. wacht 38), 11 mislukt |
| 13:30 sync | 8 nieuwe winnaars, **6 verloren**, bevroren 165 |

`[VERLIES]` registreerde bij de start correct de twee voorgevulde gevallen
(3700837158345 op 19,66; 8717774820230 op 224,06). "Geen conc. wacht 38"
was de verwachte eerste-dag-wachtrij. **"Nooit-verkoper 38"** is groter
dan gedacht: bij 38 bevroren artikelen is Cammeraat, Bouwkern of Sebic de
goedkoopste ander - die blijven nu allemaal met rust.

De 6 verliezers van 9 sept: 8716522062021 (G2, door optimize op 8/9 naar
331,94 = EUR1 onder Bohemian - **eerste Bohemian-verlies**, 1 van ~20),
8716522090192 (**de flipper, voor de derde keer**, nu op 119,38 - dus ook
onder zijn vermeende plafond; cooldown loopt), 8716522100945 (G2, toonies),
en 3 toonies-woondeco-artikelen uit de even-snel-groep (niet verhoogd).

**Nachtelijke verliezen 9 sept (CSV van 9 sept 06:45):** 8 van de 21 van
8 sept - ALLE 8 uit de "geen concurrent"-tak (de 8 die ik als bevestigd had
voorgevuld), 0 van de 13 Bohemian/Izziet. Live gecheckt: alle 8 bij **De
Kadootjeswinkel** op 14,95-32,50, levertijd onleesbaar, en ONDER onze
bodem. Die verkoper was om 10:00 niet op de pagina en 's nachts wel. Het
verlies zou ook op de oude prijs gebeurd zijn (hij zit onder onze bodem);
de verhoging heeft 1-5 dagen extra marge gepakt. Het geheugen kent
Kadootjeswinkel nu als laatst geziene concurrent bij alle 8, dus bij een
volgend "geen concurrent" is het plafond 14,93 -> geen verhoging meer.

### 12 sept (zaterdag), middag: dag 4 schoon + de twee "Run failed" van deze week verklaard

| taak | uitkomst 12 sept |
|---|---|
| 09:45 snelstart | 180 gematcht, 27 al winnend |
| 10:00 optimize | 194 bekeken, **14 verhoogd (+EUR54,56)**: 13 geen concurrent (bevestigd), 1 vlak-onder; 67 met rust; 109 overgeslagen (nooit 38, even snel 41, sneller 8, onleesbaar 4, cooldown 3, wacht 15); 4 mislukt. Optelsom 194 klopt |
| 13:30 sync | 7 nieuwe winnaars, **3 verloren**, bevroren **194** |

Verliezers: 8716522062021 (Bohemian, 2e keer op ~332 - maar dit keer via de
SNELSTART van 09:45 die hem net onder Bohemian matchte en bevroor, niet via
optimize; de cooldown in het optimize-geheugen geldt niet voor die route),
8716522110005 en 8716522110012 (allebei Izziet-artikelen op 2 cent onder,
sinds 5-6 sept; na een week alsnog verloren). Niet verhoogd vandaag.

**"Run failed"-mails (vraag van Peter/BE, 12 sept).** NL had er deze week
2 op 182 cloud-runs, geen enkele tussen 13:00 en 15:00; BE had er vandaag
3 in dat venster. De logs van onze twee:
- **vr 11 sept 23:02**: B-Living-server (`www.b-living.eu`) onbereikbaar,
  alle 5 pogingen mislukt (10/20/40/80 s wachten, ~2,5 min), run gestopt
  VOOR de XML - bewust gedrag, geen schade. Dat is de gedeelde leverancier;
  als BE's drie hetzelfde zeggen ("Attempt x/5 failed ... b-living.eu"),
  lag B-Living die middag plat en had de retry van ~2,5 min dat niet
  overbrugd. Verlengen kan (bv. 7 pogingen = ~10 min), maar cron-runs staan
  30 min uit elkaar; verder dan ~20 min mag de keten nooit.
- **zo 6 sept 17:16**: `Error 409` bij het uploaden van repricing_current.xml
  - twee runs schreven tegelijk. Oorzaak: mijn testscript triggerde om 17:16
  TWEE workflows binnen een minuut (G1b en G2 direct na elkaar). De
  verliezer stopt zonder te overschrijven; de volgende cron-run maakte het
  goed. **Les: nooit twee workflow-dispatches binnen een minuut**, en
  een handmatige trigger nooit vlak voor een cron-moment (xx:05/xx:35).
  BE's 14:15-sync triggert ook een workflow; valt die samen met hun cron,
  dan geeft dat precies zo'n 409 - dat is de tweede kandidaat voor hun
  drie mails.

**Bevestiging van BE (12 sept, via Peter):** hun vier mislukkingen van deze
week waren allemaal B-Living onbereikbaar (kandidaat 1), en ze hebben hun
retry verruimd. Middagpatroon bij BE: 4 mislukkingen op 48 runs tussen
13:00 en 15:00, 0 op 152 runs daarbuiten. NL had er in dat venster geen -
het halve uur verschil in cron-tijden (wij xx:05/xx:35) scheelt dus echt.
B-Living heeft 's middags blijkbaar korte storingen die nét langer duren
dan onze 2,5 minuut retry. Voorstel aan Peter: retries 5 -> 7 (10 s
verdubbelend = ~10,5 min totaal), ruim binnen de 30 min tussen cron-runs.

**Doorgevoerd 12 sept 18:53 (Peter: "ja doorvoeren"):** `_get_with_retries`
in `src/phase2_repricing.py` staat op `retries=7` (was 5). Wachttijden
10/20/40/80/160/320 s = 10,5 min totaal. Offline getest (lukt bij poging 7,
geeft op na 7). Op GitHub geverifieerd - dat is de versie die de cloud
draait. Verwachting: minder "Run failed"-mails bij korte B-Living-storingen;
een echte storing geeft nog steeds een mail, alleen ~8 min later.

### 12 sept (zaterdag), ochtend: 3 van 15 's nachts verloren - alle drie verklaard

CSV 08:10 (smal, 150 producten). Van de 15 verhogingen van vrijdag stonden
er 3 in de export; live nagekeken om 08:15:

| EAN | verhoging | wie heeft het koopblok | conclusie |
|---|---|---|---|
| 8716522058116 | geen conc. -> vol 44,36 | **Sjoek op 29,95** (onder onze bodem 36,78) | structureel, concurrent verscheen onder de bodem; verhoging niet de oorzaak |
| 8717266342141 | Pertina 3d trager, 22,40 -> 23,72 | **Dobeno op 24,12, levert 10** (EUR0,40 duurder én trager) | derde factor, zoals toonies op 4 sept; geheugen zet cooldown + plafond 22,72 |
| 8716522089240 | bodemklem 15,90 -> 16,13 | **De Kadootjeswinkel op 14,95** (onder onze bodem) | structureel; het plafond hield de verhoging al tegen, alleen de bodem tilde |

Geen regelwijziging. Twee van de drie zijn "concurrent onder onze bodem" -
daar is geen prijs die wint, en ze komen terug zodra die verkoper zonder
voorraad zit. Het derde geval bevestigt dat de derde factor ook bij kleine
onbekende verkopers speelt (Dobeno/Pertina); het geheugen vangt dat nu op.
Terzijde: onze eigen levertijd leest zaterdag 9 dagen (weekdagen 7).

### 11 sept (vrijdag): dag 3 - schoon

Ochtend-CSV: **0 van de 18 van gisteren 's nachts verloren, de 7 Cactula-
artikelen ook niet** (Cactula is daar dus echt weg; ze staan nu EUR10 boven
zijn maandagprijs en stappen door naar vol). B-Living-feed groeide van 5408
naar 5521 klantprijzen (Channable-mail "2% overschreden" = informatief).

| taak | uitkomst 11 sept |
|---|---|
| 08:15 morning | 213 gecheckt, 203 gematcht, 9 al winnend |
| 10:00 optimize | 166 bekeken, **15 verhoogd (+EUR64,12)**: 14 geen concurrent (bevestigd), 1 trager (Pertina); 65 met rust; 81 overgeslagen (nooit 34, even snel 34, sneller 7, cooldown 3, wacht 3); 5 mislukt. Optelsom 166 klopt |
| 13:30 sync | 5 nieuwe winnaars, **1 verloren** (8716522094145, Charme Deco, niet verhoogd), bevroren 172 |

`[VERLIES]` 8716522092004: Bohemian vlak-onder (61,93 tegen 61,95) verloren,
teruggewonnen op 54,92 -> cooldown, plafond 60,93. Tweede Bohemian-verlies
in 4 dagen op ~20 artikelen; onder de drempel (2+ op één dag), Bohemian
blijft in `VERKOPERS_VLAK_ONDER`. Het Kadootjeswinkel-plafond greep zoals
bedoeld bij 8716522089240 (doel afgekapt op 14,93, daarna door de bodem
naar 16,13 getild - dat is de bodemklem, geen verhoging).

### 10 sept (donderdag): tweede run, bevestigde "geen concurrent"-wachtrij

| taak | uitkomst 10 sept |
|---|---|
| 08:15 morning | op tijd; 200 gecheckt, 197 gematcht, 3 al winnend |
| 10:00 optimize | 165 bekeken, **18 verhoogd (+EUR72,40)**: 16 "geen concurrent (bevestigd)", 2 Bohemian vlak-onder; 53 met rust; 88 overgeslagen (nooit 38, even snel 36, sneller 6, onleesbaar 2, cooldown 2, wacht 3, geblokkeerd 1); 6 mislukt. Optelsom 165 klopt |
| 13:30 sync | 2 nieuwe winnaars, **1 verloren** (3700837161345, Cammeraat-artikel op de bodem, niet verhoogd), bevroren 159 |

`[VERLIES]` registreerde de flipper 8716522090192 (verhoogd naar 119,37,
teruggewonnen op 108,13 = bodem): 7 dagen rust, daarna plafond 118,37.

**Let op morgenochtend (11 sept, CSV):** 7 van de 16 "geen concurrent"-
verhogingen zijn de Cactula-artikelen van maandag (284,98 -> 289,98 enz.).
Cactula stond wo én do niet op die pagina's, en het geheugen kende Cactula
daar nog niet (de eerste run met geheugen was 9 sept, toen al "geen
concurrent"), dus het plafond "laatst geziene concurrent" greep niet. We
staan nu EUR5 BOVEN Cactula's prijs van maandag. Komt Cactula terug, dan
kunnen die 7 in één nacht wegvallen (dagroute herstelt). Houden ze, dan
was Cactula daar echt weg. Bij de sync van 13:30 hielden alle 18.

### 10 sept (donderdag), ochtend

CSV 07:19, 200 regels. Nachtelijk verloren: 0 van de 4 Bohemian van 9 sept,
0 van G1b, 2 van G2 (8716522100945 en 8716522094497, allebei
toonies-woondeco; 094497 voor de tweede keer). toonies-woondeco neemt bij
+EUR1 het koopblok terug, ook op EUR4-10 verschil. Staat al niet in
`VERKOPERS_VLAK_ONDER`; optimize verhoogt er niet tegen zolang ze "even
snel" lezen. Niet in NOOIT gezet: 1 van 3 G2-artikelen staat na 4 dagen nog.

**Test "even snel" AFGESLOTEN (10 sept), zonder terugzetten.** Uitslag:
+EUR1/+EUR2 ruim onder de concurrent houdt bij Bohemian, Cactula, Izziet,
Woonuden, LaSpada; verliest bij Cammeraat (3/3, dag 1) en toonies-woondeco
(2/3, dag 3). De artikelen die staan houden hun prijs (terugzetten geeft
bewezen marge weg); het verkoperbewuste optimize is de opvolger. Groepen
staan onder `afgerond` in `test_evensnel.json`.

**Kleine fix 10 sept 07:45:** de subtellers achter `verhoogd:` telden de
TAK, niet de echte verhoging ("verhoogd: 4 (vlak-onder-verkoper 21 ...)").
Nu tellen ze alleen wat echt verhoogd is. Stub-getest, op GitHub.

**Let op voor volgende chats:** de sessie van 8/9 sept is 's ochtends
afgebroken (geen wachter, geen terugkoppeling van 9 sept aan Peter tot
10 sept). En `SendMessage` naar de BE-chat is in deze sessie niet meer
beschikbaar - uitwisseling met BE dus weer via de instructiedocumenten in
de projectmap (zie het blok "Uitwisseling met het BE-project").

### 8 sept (dinsdag): de beslissende meting - "even snel" was NIET de oorzaak

| taak | uitkomst 8 sept |
|---|---|
| 08:15 morning | 187 gecheckt, 174 gematcht, 13 al winnend; CSV smal (143 producten) |
| 10:00 optimize | 187 bekeken, **21 verhoogd (+EUR67,84)**, 99 overgeslagen (onleesbaar 2, even snel 60, sneller 37) |
| 13:30 sync | 3 nieuwe winnaars, **4 verloren (0 van de 23 van gisteren, 0 testartikelen)**, bevroren 182 |

Ochtend-export (tweede meetbron): geen van G1b (5), G2 (12) en de 24 van
maandag stond erin. 0 nachtelijke verliezen.

**De vraag van gisteren is beantwoord.** Cactula leest vandaag weer "even
snel" (7/7); Bohemian nog steeds "3d later". De 7 Cactula-artikelen die
maandag naar 2 cent onder gingen (284,98 tegen 285,00 enz.) staan er op
dag 2 nog allemaal - terwijl ze nu als "even snel" gelezen worden. En de
Bohemian-artikelen staan op 2 cent onder (102,93 tegen 102,95; 432,93
tegen 432,95). Conclusie: **"even snel" was op 1 sept niet de oorzaak van
de 69 verliezen. De VERKOPER is de voorspeller, niet de levertijd.**

Wat de data nu zegt per verkoper (NL, 1-8 sept):

| verkoper | tot vlak onder / verhogen | uitkomst |
|---|---|---|
| Bohemian Living NL | ja, tot 2 cent onder | houdt (ma+di, ~12 artikelen) |
| Cactula | ja, tot 2 cent onder | houdt (ma+di, 7 artikelen) |
| Izziet | ja, tot 1 cent onder | houdt (2 sept, 2 artikelen, dag 6) |
| toonies-woondeco | +EUR1/+EUR2 ruim eronder | houdt; maar pakt koopblok bij EUR7 verschil (8716522090192) |
| Woonuden, LaSpada | +EUR1 ruim eronder | houdt |
| **Cammeraat** | +EUR1 op EUR3 eronder | **verliest, 3 van 3** (en pakt 8717774820230 zodra hij verschijnt) |
| **Bouwkern** | naar vol, 33 cent eronder | **verliest** (3700837158345) |
| Sebic - CAN-Interiors | (nooit verhoogd, "sneller") | bij BE 3 van 3 gewonnen tegen hen |

De levertijdrem was een goede benadering omdat Bohemian/Cactula/Izziet
toevallig vaak "trager" lezen en Sebic/Bouwkern "sneller". Maar hij is
weekdag-afhankelijk (Cactula: ma trager, di even snel) en mist de kern.

**Drie verliezers van vandaag, live nagekeken:**
- 8717774820230 (geen concurrent, 5 dagen EUR5-stappen 204->224): Cammeraat
  verscheen op 199,99. Dagroute zakt vanzelf. Vijf dagen extra marge gepakt.
- 3700837158345 (om 10:00 "geen concurrent", naar vol 19,66): Bouwkern op
  19,99, levert 3d, heeft het koopblok. Op 4 sept stond Bouwkern er wél
  ("sneller", overgeslagen). **Tweede keer dat "geen concurrent" een
  momentopname bleek** (4 sept Cammeraat). Kandidaat-fix: bij "geen
  concurrent" de laatst geziene concurrent onthouden en niet boven diens
  prijs - of pas stappen als twee runs op rij geen concurrent tonen.
- 8716522106770: uit de B-Living-feed, ons aanbod weg. Niets doen.
- 8717266334818 (41,86): niet nagekeken, niet verhoogd.

8716522090192 (de flipper): vanmorgen teruggewonnen op 114,37, om 10:00
naar 119,37, hield. Morgen tilt de EUR5-stap hem naar 124,37 = boven zijn
plafond (~122) -> verliest weer. **Cooldown na verlies-na-verhoging blijft
de nuttigste kleine fix.**

Test-stand: G1b 5/5 (dag 2 op +EUR2), G2 12/12 (dag 2). Vijf testartikelen
zijn inmiddels door optimize verder verhoogd (Bohemian "3d later") en
staan op 2 cent tot EUR1 onder de concurrent; ook die houden. **De test
heeft zijn antwoord: +EUR1/+EUR2 ruim onder de concurrent is veilig, behalve
tegen Cammeraat.** Volgende stap is aan Peter (zie chat 8 sept).

### 7 sept (maandag): het maandag-effect - 24 verhoogd, 23 gehouden

| taak | uitkomst 7 sept |
|---|---|
| 08:15 morning | 182 gecheckt, 181 gematcht, 1 al winnend |
| 10:00 optimize | 181 bekeken, **24 verhoogd (+EUR83,34)**, 100 overgeslagen (onleesbaar 1, even snel 61, sneller 38) |
| 13:30 sync | 3 nieuwe winnaars, **5 verloren** (1 verhoogd + 4 niet verhoogd), bevroren 177 |

**Waarom ineens 24.** Op maandag lezen Bohemian Living NL en Cactula als
"levert 3d later" waar ze vr/za/zo "even snel" (7/7) waren. De levertijd-
belofte op bol.com hangt van de weekdag af (weekendbestellingen gaan
maandag pas weg, en niet bij elke verkoper even snel). De regel werkte dus
op wat bol.com op dat moment toonde - en dat is ook wat de koopblok-weging
gebruikt. Daardoor gingen 17 Bohemian/Cactula-artikelen omhoog, waarvan
7 Cactula tot 2 cent onder (284,98 tegen 285,00) en 6 Bohemian tot 2-9 cent
onder. **Bij de sync van 13:30 hielden 23 van de 24**, inclusief al die
"vlak onder"-gevallen. Op 1 sept kostte precies dat 69 koopblokken - maar
toen tegen "even snel"; nu tegen "trager". Of dat morgen (dinsdag, andere
levertijdtekst) standhoudt is DE vraag van 8 sept. Verliezen lopen vanzelf
terug via de dagroute, maar 17 tegelijk is een dag omzet.

BE bevestigt dat dit een echte marktlezing is en geen parser-artefact: bij
hen las Cactula op dezelfde maandag juist SNELLER ("donderdag in huis")
dan vrijdag. Dezelfde verkoper, per land een ander verzendprofiel. **Wat
dinsdag 8 sept beslist:** lezen Bohemian/Cactula dan weer "even snel" en
blijven de 23 tóch staan, dan was "even snel" op 1 sept niet de oorzaak
van de 69 verliezen, maar de vlakke undercut op de verkeerde artikelen -
en dan is de levertijdrem te streng. Vallen ze, dan is de rem juist en
moet hij niet op één weekdag-lezing afgaan.

**De enige verhoogde verliezer: 8716522090192 - voor de tweede keer.** Won op
111,37 en 117,90, hield 116,37 en 121,38, verloor op 122,90 (4/9) en
126,38 (7/9), telkens aan toonies-woondeco 129,95. Zijn plafond ligt op
~EUR122. De EUR5-stap tilt hem daar elke paar dagen overheen: een flip-lus
die de regel zelf veroorzaakt. **Kandidaat-verbetering: geheugen na een
verlies-na-verhoging** (zoals `probe_history.json` met COOLDOWN_DAYS): een
artikel dat binnen een dag na een optimize-verhoging ontdooit, N dagen niet
opnieuw verhogen, of niet boven de prijs waarop het verloor. Nog niet
gebouwd.

De 4 andere verliezers (8716522063578, 8716522070361, 8716522101461,
8716522101478; EUR21-24) zijn niet verhoogd en niet in een testgroep; drie
ervan waren nieuwe winnaars van 5 sept. Niet nagekeken.

### Test "even snel" - stand na meting 3 (7 sept 13:40)

| groep | koopblok bij ons | opmerking |
|---|---|---|
| G1b (5 artikelen, +EUR2) | **5 van 5** | Peters "bij EUR2 verlies je" klopt hier niet. 2 van de 5 (103472, 070163) zijn vandaag door optimize nóg EUR5 omhoog gezet (Bohemian "3d later") en houden ook dat. |
| G2 (15 nieuwe, +EUR1) | **12 van 12** over, **3 Cammeraat afgevallen** | de 3 Cammeraat-artikelen (3700837161345/158109/158086, EUR16,74 tegen 19,95-19,99) verloren 's NACHTS het koopblok - stonden in Peters export van 06:42, dus de sync van 13:30 zag het niet. Cloud-auto-unfreeze, reset naar vol (17,77), EUR0,50-stappen omlaag; om 13:30 hadden 2 van 3 het koopblok terug op 16,26. 3700837161345 verloor daarmee voor de tweede keer aan Cammeraat 19,99 (4/9 op 17,77, 7/9 op 16,74). |

**Beslissing 7 sept (chat, per afspraak zonder te vragen):** G2 NIET
teruggedraaid, hoewel de letterlijke regel (2+ verloren) dat zei. Reden: de
3 verliezen zitten allemaal bij één verkoper (Cammeraat, 3 van 3) terwijl de
12 andere (5 verkopers) allemaal staan. De regel was bedoeld om "de stap is
schadelijk" te vangen; dat is hij aantoonbaar niet - alleen tegen Cammeraat.
De 3 zijn uit het terugzetpunt gehaald (`afgevallen` in de backup); ze
staan via de dagroute weer op een eigen prijs. Les: **Cammeraat pakt bij
elke verhoging het koopblok, ook als wij EUR3 goedkoper zijn.** Niet meer
verhogen tegen Cammeraat (nog niet in code).

Meting 3 van G1/G1b: 5/5 op dag 3, 3 van G2: 12/12 op dag 1 (excl. Cammeraat).

**Les over meten:** de sync van 13:30 mist verliezen die 's nachts gebeuren
en 's ochtends alweer via de dagroute hersteld zijn. Peters ochtend-export
(de CSV) is de tweede meetbron: staat een testartikel in de CSV van de
volgende ochtend, dan heeft het 's nachts verloren. Bij de ochtendcontrole
dus de CSV naast de testgroepen leggen.

### 6 sept (zondag): derde brede run

09:45 snelstart: 181 gecheckt, 0 al winnend. 10:00 optimize: 180 bekeken,
**4 verhoogd** (+EUR17,40; 2 zonder concurrent, 2 tegen Izziet), 125
overgeslagen (onleesbaar 5, even snel 84, sneller 36), 4 mislukt. 13:30
sync: **0 verloren, 0 nieuw**, bevroren 182. 8716522090192 staat nu op
EUR121,38 (verloor op 4 sept op 122,90) en hield - de grens voor dat
artikel ligt dus vlak boven 121,38, of de verliezer van 4 sept was toeval.

### 5 sept (zaterdag): tweede brede run

09:45 snelstart: 194 gecheckt, 12 al winnend. 10:00 optimize: 176 bekeken,
**6 verhoogd** (+EUR22,94; 5 zonder concurrent, 1 tegen Izziet), 120
overgeslagen (onleesbaar 5, even snel 79, sneller 36), 5 mislukt. 13:30
sync: **0 verloren**, 6 nieuwe winnaars, bevroren 182.

Opvallend: 8716522090192 (gisteren verloren op EUR122,90) is vanmorgen
teruggewonnen op EUR111,37 en door optimize weer naar EUR116,37 gezet
(Izziet 128,00, vandaag "3d later" i.p.v. 5d - weekendeffect in de
levertijdtekst). Dat hield. De grens voor dit artikel ligt dus ergens
tussen EUR116,37 en EUR122,90; de EUR5-stap tast dat morgen vanzelf af.

### 4 sept: de eerste brede run (limiet 200) - uitslag

| taak | uitkomst 4 sept |
|---|---|
| 08:15 morning | 169 gecheckt, 168 gematcht, 1 al winnend |
| 10:00 optimize | **176 bekeken, 9 verhoogd** (+EUR28,17), 47 met rust, 115 overgeslagen, 5 mislukt |
| 13:30 sync | 1 nieuwe winnaar, **3 verloren (2 verhoogd + 1 gewoon)**, bevroren 166 |

Verhoogd: 8 zonder concurrent (EUR5-stap of naar vol) + 1 tegen Izziet die
5 dagen later levert. Overgeslagen: **even snel 76, sneller 36, onleesbaar
3.** De rem grijpt bij ons dus veel harder dan bij BE (6 van 131), door de
markt: bijna elke concurrent toont een harde datum die op 7 kalenderdagen
uitkomt, net als wij. "1 - 2 weken" komt bij ons nauwelijks voor.

**Behoud van de 9 verhoogde: 7 (78%).** De twee verliezers, allebei live
nagekeken om 13:45:

| EAN | verhoging | wie heeft het koopblok nu |
|---|---|---|
| 8716522090192 | 117,90 -> 122,90 (Izziet 128,00, 5d trager) | toonies-woondeco op **129,95, 12 dagen** - EUR7 duurder én 5 dagen trager dan wij |
| 3700837161345 | 15,73 -> 17,77 (naar vol, "geen concurrent") | Cammeraat op **19,99, 7 dagen** - EUR2,22 duurder, even snel |

**Beide verliezers zijn de goedkoopste aanbieder met gelijke of betere
levertijd en hebben tóch het koopblok niet.** Prijs en levertijd verklaren
dit verlies dus niet; er speelt een derde factor (verkopersbeoordeling of
bol.com's eigen weging). Les: "trager" is geen vrijbrief - 8716522090192
won op EUR10 onder Izziet en verloor op EUR5 onder, aan een verkoper die
op beide assen slechter scoort. En "geen concurrent" om 10:00 sluit niet
uit dat er om 13:30 wél een staat (Cammeraat). Allebei lopen via de
normale dagroute terug (ontdooid -> reset -> EUR0,50-stappen omlaag); niets
handmatig doen.

De derde verliezer van 4 sept (8717266051616, EUR11,79) is niet verhoogd en
is **uit de B-Living-feed verdwenen** - BE verloor op 4 sept hetzelfde EAN
om dezelfde reden (koopblok daar bij WOHI-BE). Zonder klantprijs wordt er
geen prijs gepubliceerd; het artikel valt vanzelf uit de export. Niets doen.

Stand van de regel na 4 dagen: trager 2 van 3 gehouden (n=3!), geen
concurrent 7 van 8, even snel/sneller niet meer verhoogd. **Geen
regelwijziging op basis van één dag met n=9.** De testartikelen van 2 sept
(8716522090673/94817) staan op dag 2 nog op EUR135,94.

**Direct openstaand:**

1. **Weekend 5-6 sept: de tweede en derde brede run volgen.** Let op de
   groep "trager" (nu 2 van 3) en "geen concurrent" (7 van 8). Verliezers
   altijd live nakijken met `check_all_offers` + `check_buybox`: staat de
   winnaar duurder én trager dan wij, dan is het geen prijsverlies.
2. De twee testartikelen nog een paar dagen volgen (BE's 19 staan op dag 3
   nog allemaal).
3. **Afronding van UNDERCUT.** De klantprijs wordt naar boven op de cent
   afgerond, dus "2 cent onder" landt soms op 1 cent onder (3 sept:
   EUR135,94 tegen EUR135,95) en kan in theorie precies GELIJK aan de
   concurrent uitkomen. Bij BE hield gelijk tot nu toe; bij NL niet getest.
   `UNDERCUT = 0.03` garandeert strikt eronder. Bewust niet gewijzigd.
4. Open vraag, bewust nog niet beantwoord: de groep "even snel" (9 van 17
   op 3 sept) hield bij ons 20% en bij BE 40%. Blijft overgeslagen.
5. **DNS-hik op `api.github.com` vanaf deze pc**, 2x in 3 dagen: 1 sept
   08:16 (morning, alleen de CSV-datumcheck faalde) en 3 sept 13:30 (sync,
   retry ving het op). BE ziet het nooit. Geen actie; bij een derde keer de
   tijdstippen naast elkaar leggen.
6. De overlap van de teller `geen concurrent` staat er nog (zie hieronder).
7. **Kandidaat-verbetering, nog niet gebouwd: "1 - 2 weken" als bereik lezen.**
   BE (3 sept, live vanaf 4 sept 10:45) leest levertijd als bereik
   (vroegst, laatst): "Uiterlijk 10 september" -> (7,7), "1 - 2 weken" ->
   (7,14), "Morgen" -> (1,1), "3 - 5 werkdagen" -> (3,5), en verhoogt bij
   'trager' (hun vroegste dag na onze laatste) én 'later' (niet vroeger op
   de vroegste, wel later op de laatste). Bewijs bij BE: alle 22
   verhogingen tegen "1 - 2 weken"-verkopers (Cactula, Bohemian, Izziet)
   hielden, op 1/9 én 3/9. Bij ons geeft "1 - 2 weken" None -> overgeslagen;
   de 2 "onleesbaar" van 3 sept (beide Bohemian Living NL, ruimte EUR5,07
   en EUR1,99) zijn vrijwel zeker dit geval. Let op het verschil met BE:
   met onze 7 kalenderdagen is (7,14) 'later', geen 'trager', en bij NL
   hield "even snel" maar 20%. Pas invoeren ná de eerste brede run van
   4 sept, anders zijn twee wijzigingen op één dag niet uit elkaar te
   houden. Kleine opbrengst (in de eerste 40: 2 artikelen, ~EUR7/cyclus).

### De tellers van `optimize` overlappen - lees ze goed

`geen concurrent` is geen eindbestemming. Die artikelen krijgen `doel =
min(onze + MAX_STAP, vol)` en tellen daarna NOG een keer mee in `verhoogd`
of `met rust`. De som van alle tellers is dus groter dan het aantal bekeken
artikelen (de droogloop gaf 78 op een set van 60).

Zo lees je het goed: `verhoogd + overgeslagen + met rust + mislukt` = het
totaal, en `geen concurrent` is een deelverzameling van de eerste twee.
Vandaag: 2 + 17 + 19 + 2 = 40, met de 11 zonder concurrent binnen die 19
(ze stonden al op hun volle prijs, dus geen ruimte).

Dit maakt uit bij het beoordelen, want `verhoogd` mengt twee heel
verschillende dingen: verhoogd tegen een tragere concurrent (de onbewezen
gok) en verhoogd zonder enige concurrent (94% behoud, de veiligste categorie
die we kennen). Kijk dus altijd naar de kolom `reden` in de tabel, niet
alleen naar het totaal. De overlap van `geen concurrent` staat er nog; bewust, want het script dat
om 10:00 draait verder verbouwen maakt de meting van 3 sept troebel.

**Wél gedaan op 3 sept, 07:45 (vóór de run van 10:00):** de teller
`niet_sneller` is gesplitst in drie - `levertijd onleesbaar` / `even snel`
/ `sneller`. Puur diagnostisch, het gedrag is identiek (stub-test op zes
gevallen: elk artikel landt in dezelfde tak als voorheen). Reden: "1 - 2
weken" leest `_levertijd_dagen` niet, en dat werd op één hoop gegooid met
een concurrent die echt even snel is - terwijl zo'n concurrent tegenover
onze 3-5 werkdagen eerder trager is. De 17 overgeslagen van 2 sept zijn
daardoor niet te duiden; vanaf 3 sept wel. Per overgeslagen artikel staat
in het LOKALE log nu een regel met beide levertijden (geen prefix, dus niet
online). Tegelijk staat `[OPTIMIZE]` in de prefix-lijst van
`scheduled_run.py`, zodat de tellerregel ook in `automation_log.json`
terechtkomt - op 2 sept stond daar alleen `[DONE] frozen.json bijgewerkt`,
zonder aantallen. Beide bestanden staan ook op GitHub (Contents-API,
bytegrootte geverifieerd).

## Scope van deze chat

- Dit is het **NL/Tiptopshop**-project, repo `peterhoman/bol-repricing`.
- Er is een **apart, eigen project + eigen chat** voor **BE/Dreamhouse&Garden**
  (repo `peterhoman/bol-repricing-be`). Peter houdt deze twee expliciet
  gescheiden — NOOIT vanuit de NL-chat in het BE-project werken (en
  andersom), ook niet voor een structureel identieke bugfix. Dit is een
  harde regel, meerdere keren door Peter bevestigd.

## Wat dit project doet (kort)

Automatische Bol.com-repricing: verlaagt prijzen van artikelen die het
"koopblok" niet hebben, in kleine stappen (normaal €0,50, bij grote
achterstand €10), tot een bodemprijs (minimumprijs) die de marge
beschermt. Draait via GitHub Actions (cron) + Channable (leest een XML-feed
die dit project op GitHub publiceert) + de B-Living-leveranciersfeed
(bron van de "klantprijs"/kostbasis). Geen Railway of andere hosting -
alleen GitHub (gratis Actions-minuten) + Channable.

Vaste bestandsnamen in de repo (zodat Channable's import-URL nooit hoeft
te wijzigen): `bolcom_productinformatie.csv`, `repricing_current.xml`,
`state.json`, `frozen.json`, `big_gap.json`, `no_competitor.json`,
`master_tracked.json`, `audit_report.json`.

**De cloud draait de versie die op GitHub staat, niet de lokale.** Na een
codewijziging moet `src/phase2_repricing.py` dus los naar GitHub geüpload
worden via de Contents API. Gebruik daar NIET `setup_upload.py` voor: dat
uploadt ook de lokale statusbestanden, die hier vaak lege stubs zijn, en
wist daarmee de live status.

## EERST DOEN bij elke nieuwe sessie: automation_log.json controleren

Sinds 17 augustus draait de dagelijkse routine via de Windows-TAAKPLANNER
(niet via chat-seintjes). Vier taken, dagelijks, bewust verschoven t.o.v.
BE's tijden (08:15/10:00/11:30/13:30) omdat twee scrape-scripts tegelijk
rate-limiting geeft:

| tijd NL | taak | commando (via `src/scheduled_run.py`) |
|---|---|---|
| 08:15 ma-vr / **09:45 za-zo** | morning | `match_prices.py` |
| 10:00 | probe_start | `probe_recovery.py optimize 200` (sinds 1/9, limiet 200 sinds 3/9, verkoperbewust + geheugen sinds 8/9) |
| 11:30 | probe_check | `probe_recovery.py check` (doet niets meer sinds de probe vervangen is) |
| 13:30 | sync | `sync_buybox.py` (2 u na de check, vanwege valse verliezen) |

(Weekend-snelstart om 09:45 sinds 22/8: Peters weekend-uploads lagen tussen 07:30 en 09:36, een vaste 08:15 draaide dan op de lijst van gisteren. De wrapper zet bij elke snelstart een `[CSV]`-regel in het log die zegt of de lijst van vandaag is; staat er `[LET OP] CSV is NIET van vandaag`, dan was de upload te laat — melden aan Peter, verder geen actie: de cron pakt de nieuwe lijst bij de eerstvolgende run en morgen draait de snelstart weer vers.)

(Sinds 18/8: NL heeft de vroege sloten — NL is de belangrijkste winkel — en
BE draait op 09:00/10:45/12:15/14:15. Het bestand moet vóór 08:10 in GitHub
staan, anders draait de snelstart op de lijst van gisteren. Bij een
volgende ruil: altijd eerst BE omzetten, dan NL, anders delen ze een dag
dezelfde sloten.)

Elke run logt naar `logs/automation-JJJJ-MM.log` (lokaal, volledig) en naar
**`automation_log.json` op GitHub** (laatste 60 runs, compact). Lees dat
laatste bij sessiestart **via de Contents-API, niet de raw-URL** (die cachet
en gaf op 17/8 een 429). Meld aan Peter:

- runs met `"result": "FAILED"` → uitleggen wat er misging
- een taak die op een dag ontbreekt → de pc heeft hem gemist
- rare aantallen (0 producten geladen, ongewoon veel REVERTED) → eerst
  onderzoeken, dan pas verder

Wat Peter nog doet: 's ochtends het bestand uploaden. Verder niets; de pc
mag in slaapstand (taken hebben `-WakeToRun`), niet uit. De taken zijn
aangemaakt met `taken_aanmaken.ps1` (door Peter zelf uitgevoerd — Claude kan
geen taken registreren). Wektimers stonden al goed (0x00000001).

**Taken draaien zonder consolevenster (sinds 21/8).** `taken_aanmaken.ps1`
gebruikt `pythonw.exe` en de wrapper start het kindproces met
`CREATE_NO_WINDOW`. Reden: onder `python.exe` opende elke taak een zwart
venster; klikte Peter dat weg, dan stierf het hele procesboompje met exit
**3221225786** (0xC000013A) vóór de push naar GitHub — BE verloor zo de
probe-ronde van 20/8, zichtbaar als een GAT in `automation_log.json` terwijl
het lokale log hem wél had. Bij de ochtendcontrole: ontbreekt een taak online,
kijk in `logs/automation-JJJJ-MM.log`; staat hij daar met die exitcode, dan is
`taken_aanmaken.ps1` niet opnieuw gedraaid na deze wijziging.

Ingebouwde sloten (niet weghalen):

- `probe_recovery.py auto/start` weigert na 20:30 (Channable importeert 's
  avonds niet; artikelen zouden anders de hele nacht op volle prijs staan)
- `probe_recovery.py check` weigert binnen 30 min na de start (leest anders
  de oude prijs en houdt een niet-winnende prijs vast); starttijd staat als
  `_gestart` in `frozen_probe_backup.json`
- **preflight in `github_action_reprice.py`**: als frozen/state/
  master_tracked niet via de raw-URL leesbaar zijn (bv. 429), stopt de
  cloud-run ZONDER upload. Reden: alle `load_*`-functies geven bij een
  niet-200 stilletjes `{}` terug, en één run tijdens zo'n storing zou alle
  bevroren winnaars in één upload wissen. Rode workflow-mails tijdens zo'n
  storing zijn dus bewust en veilig. Geen retry-logica bouwen.

**De CSV wordt overal via de Contents-API gelezen (sinds 18/8).** Alle
`CSV_URL`-constanten wijzen naar
`https://api.github.com/repos/.../contents/bolcom_productinformatie.csv`;
de engine zet daar zelf `Accept: application/vnd.github.raw` op
(`_fresh_headers`). Reden: de raw-CDN kan minutenlang een oude versie
serveren van een bestand dat we ZELF net via de API schreven. In BE zette
`add_eans_to_csv` daardoor de zojuist verwijderde sync-winnaars terug in
de CSV, waarna de cloud-run alle 18 verse winnaars ontdooide — 23 seconden
na de sync. NL had exact dezelfde bug maar ontsnapte op timing (20/20
winnaars van 18/8 bleven staan, gecontroleerd). Zet een CSV-lezing dus
nooit terug naar de raw-URL. De les breder: **elke leesactie die kort op
een eigen schrijfactie volgt moet via de API**, niet via raw.

**Zuinig zijn op de raw-URL.** Op 17 augustus blokkeerde
raw.githubusercontent.com de repo met 429's — ook voor Channable (beide
feeds, zie de Channable-mails van 15:58 en 16:58). Aanleiding: een
uitzonderlijk drukke dag (probe-rondes, syncs, taakplanner-tests in twee
projecten) plus poll-lussen die tot 20x per wachtbeurt de raw-URL opvroegen.
Regels voortaan: verifieer uploads via de Contents-API in plaats van de
raw-URL te pollen, en is de blokkade actief, raak de raw-route dan de rest
van de dag niet aan — hij ebt vanzelf weg. Een mislukte Channable-import is
onschuldig: Channable houdt de laatst gelukte feed.

## De dagelijkse routine (HANDMATIG — alleen nog als de taakplanner uitstaat)

Start dit DIRECT, zonder te vragen of hij wil dat je begint — dat is de
afspraak:

0. **Controleer de BESTANDSNAAM als je het nieuwe bestand niet ziet.**
   Op 2 augustus stond de upload er als
   `20260802_bolcom_productinformatie.csv` in plaats van de vaste naam.
   Het hele systeem leest alleen `bolcom_productinformatie.csv` (vaste
   naam, zodat Channable's import-URL nooit hoeft te wijzigen), dus zo'n
   upload wordt gewoon genegeerd.

   Zegt Peter dat het bestand er staat maar zie je geen nieuwe commit op
   `bolcom_productinformatie.csv`, kijk dan naar de laatste commit op de
   repo als geheel — de kans is groot dat het onder een andere naam staat.
   Oplossing: inhoud kopiëren naar de vaste naam via de Contents API.

   **Let op de CDN-vertraging.** Na zo'n upload serveert
   `raw.githubusercontent.com` nog een paar minuten het OUDE bestand.
   Poll de raw-URL tot de bytegrootte klopt vóór je de workflow start,
   anders draait die op de oude data.

1. **CSV verifiëren**: check de raw GitHub-URL
   (`https://raw.githubusercontent.com/peterhoman/bol-repricing/main/bolcom_productinformatie.csv`)
   op HTTP 200 en tel het aantal rijen.
   **Let op:** dit bestand bevat ALLEEN productinformatie (naam, EAN,
   afmetingen, materiaal, etc.) — GEEN prijzen. De prijzen komen uit de
   aparte B-Living XML-feed (`klantprijs`-veld), die het script zelf
   ophaalt.
2. **Workflow triggeren**: `POST` naar
   `https://api.github.com/repos/peterhoman/bol-repricing/actions/workflows/reprice.yml/dispatches`
   met `{"ref": "main"}` (credentials: `GITHUB_TOKEN`/`GITHUB_REPO` in
   `.env` van dit project) — niet wachten op het volgende cron-moment.
3. **Wachten tot de run klaar is**, dan de logs ophalen (Actions API +
   logs-zip) en checken: nieuwe dag correct herkend? aantal
   bevroren/big-gap/master-tracked? aantal aanpassingen? audit schoon
   ("No consistency issues found")?
4. **Peter een korte samenvatting geven.**
5. **Los, handmatig, vanaf déze pc (NIET vanuit GitHub Actions):**
   `python src/match_prices.py` draaien — de "morning fast-start". Dit
   moet vanaf een gewone (residentiële) internetverbinding, omdat
   bol.com live koopblok-checks blokkeert vanaf cloud/datacenter-IP's
   (GitHub Actions dus niet). Dit script:
   - checkt live per actief EAN wie nu het koopblok heeft,
   - bevriest het artikel als wij al winnen,
   - matcht (net onder) de concurrent als we nog niet winnen, geklemd op
     de bodemprijs,
   - rapporteert: aantal gematcht / nieuw gewonnen (bevroren) / op de
     bodemprijs beland / niet gevonden.

   **Belangrijk, artikelen op de bodemprijs betekent NIET dat ze het
   koopblok hebben** — meestal juist niet (de concurrent zit dan onder
   onze bodem, en daar zakken we bewust niet onder om geen verlies te
   draaien). Peter is hier al mee akkoord: liever koopblok kwijt dan
   verlies draaien.

## Margeherstel op ECHTE concurrentprijzen (1-2 september) - LEES DIT

Dit vervangt de probe volledig. Er is een dure les in verwerkt; bouw niet
terug naar de oude aanpak.

### De vondst

Wij dachten weken dat je de concurrent niet kunt zien zolang wij het koopblok
hebben. Dat is onjuist. Achter "Bij N partners verkrijgbaar" zit:

```
https://www.bol.com/nl/nl/prijsoverzicht/<slug>/<product-id>/?sort=price&sortOrder=asc
```

Gewone server-rendered HTML, `requests.get()` volstaat. Alle verkopers, hun
prijzen EN hun levertijd staan erin, ook als wij winnen. Geimplementeerd als
`engine.check_all_offers()`; slug en id komen uit de gewone product-URL.

Parseer prijs en verkoper met APARTE patronen - bij korting staat er tekst
tussen ("De adviesprijs is ... Je bespaart 3%") en breekt een gecombineerd
patroon.

### De fout van 1 september (69 koopblokken kwijt)

Let op de tijdlijn: de taak van 10:00 draaide die dag nog de OUDE probe
(11 EAN's naar volle prijs, 11/11 behouden); de optimize-ronde van 125
artikelen was een HANDMATIGE run om 11:19. Dat verklaart waarom je in
`automation_log.json` geen optimize-run van 1 sept terugvindt.

Eerste ronde zette 125 bevroren prijzen op twee cent onder de goedkoopste
concurrent. Gerapporteerd als "+€375,65 opbrengst". Dat was geen opbrengst
maar een rekening: de sync van 13:30 ontdooide 79 artikelen, waarvan 69 uit
die 125. Behoud: 45%.

**Waarom:** wij hadden die koopblokken juist omdat we FORS goedkoper waren -
dat verschil compenseert ons levertijdnadeel (3-5 werkdagen tegen
concurrenten die morgen leveren). Twee cent onder gaan zitten haalt die
compensatie weg.

### De meting van 2 september (123 artikelen)

Uitgesplitst naar hoe de verhoging tot stand kwam:

| groep | n | behoud |
|---|---|---|
| tot net onder de concurrent (-€0,02) | 59 | **20%** |
| afgetopt op de €5-stap | 26 | 73% |
| afgetopt op de volle prijs | 20 | 35% |
| geen concurrent op de pagina | 18 | **94%** |

En binnen die eerste groep, naar levertijd van de concurrent:

| concurrent levert | n | behoud |
|---|---|---|
| sneller dan wij | 26 | 12% |
| **gelijk** | **30** | **20%** |
| trager | 3 | **100%** |

Levertijd is de sterkste voorspeller. De €5-limiet die als voorzorg was
ingebouwd bleek het beste onderdeel.

### De regel die er nu staat

- **concurrent aantoonbaar TRAGER** -> tot `concurrentprijs - UNDERCUT`
- **gelijk of sneller** -> niets doen (daar houdt het prijsverschil het
  koopblok vast)
- **geen concurrent** -> stap van maximaal `MAX_STAP` (€5)
- altijd klemmen op `[bodemprijs, volle prijs]`

Voeg "trager" en "gelijk" NIET samen: trager is een kleine groep (3-5
artikelen), gelijk is de grote (30). Samenvoegen laat de kleinste groep de
regel bepalen en kost de meerderheid - punt van de BE-chat, en terecht.

### Twee dingen die niet overdraagbaar zijn tussen NL en BE

`UNDERCUT = 0.02` komt van BE en werkt DAAR omdat zij vijf dagen SNELLER
leveren dan hun concurrenten (9 sept tegen 14 sept gemeten). Bij hen is
vrijwel alles "concurrent trager", vandaar hun 19 van 19. Bij ons is het
omgekeerd. Neem hun waarde niet over en zij niet die van ons; hoeveel
prijsverschil je nodig hebt hangt af van je positie op levertijd en
beoordeling.

### Methodologische waarschuwing

Een eerdere analyse mat "prijsverschil in procenten" en vond een piek van 81%
bij 2-5%. Dat was een ARTEFACT: die groep bestond uit artikelen waar de
€5-limiet ons toevallig ver onder de concurrent hield, niet uit een
gerichte 2-5%-marge. De BE-chat prikte daar terecht doorheen. Let er bij
elke vervolgmeting op dat je meet wat je denkt te meten.

## Margeherstel met de probe (17 augustus) — WERKWIJZE, LEES DIT VOOR JE PROBEERT

Een bevroren artikel houdt zijn winnende prijs vast. De twee bestaande klemmen
kijken naar de INKOOPPRIJS, geen enkele naar de concurrentie — verdwijnt de
concurrent, dan blijft de prijs onnodig laag staan. Peter merkte dit op bij zes
identieke deurstoppers: vier op €24,44 en twee (bevroren) op €21,92, bij dezelfde
inkoopprijs en zonder concurrent.

**Voorstel dat is AFGEWEZEN:** €0,50-stapjes per dag omhoog. Reden (van BE, en
terecht): de live-checks draaien maar één keer per dag, dus bij gemiddeld €9
ruimte duurt dat 18 dagen per artikel en bij de grootste posten ruim 100 dagen.
En bij mislukking verlies je het koopblok écht, terwijl de probe binnen 90
minuten terugzet uit een backup. Bouw dit niet opnieuw.

**De werkwijze die er nu staat**, in `src/probe_recovery.py`:

```bash
python src/probe_recovery.py candidates [n]   # alleen tonen
python src/probe_recovery.py auto [n]         # selecteren en starten
# ~90 minuten wachten op Channable, dan OP PETERS SEINTJE:
python src/probe_recovery.py check
```

Knoppen bovenaan het bestand: `MIN_GAIN` (€10), `COOLDOWN_DAYS` (14),
`DEFAULT_BATCH` (15). `probe_history.json` op GitHub houdt bij wat wanneer
geprobeerd is; de check schrijft dat weg vóór het legen van de backup.

### Harde regels

1. **Plan de check NOOIT in als wachttaak.** In BE ging de computer in
   slaapstand en stonden dertig artikelen een hele dag op volle prijs.
2. **Draai nooit twee scrape-scripts tegelijk** — niet de probe naast de sync,
   en niet NL naast BE. Dat geeft rate-limiting bij bol.com.
3. **Draai GEEN `sync_buybox.py` binnen ~90 minuten na een check.** Channable
   heeft de teruggezette prijzen dan nog niet geïmporteerd, dus de sync ziet die
   artikelen als "koopblok kwijt" en ontdooit ze onnodig. Dit ging op 17 augustus
   mis in NL: van de 15 "verloren koopblokken" waren er **11** precies dit. Het
   script waarschuwt hier nu voor na een check met terugzettingen.

### Wat NL's eerste ronde opleverde — en waarom SORTEREN OP BEDRAG FOUT IS

| | NL 17 aug | BE 17 aug |
|---|---|---|
| kandidaten | 15 | 15 |
| behouden | **3 (20%)** | 12 (80%) |
| terugverdiend | €84,35 | €521,74 |

**Belangrijkste les, uitgesplitst na de ronde:**

| groep in dezelfde ronde | aantal | behouden | slagingskans |
|---|---|---|---|
| vliegengordijnen | 5 | 3 | **60%** |
| al het andere | 10 | 0 | **0%** |

Het bedrag voorspelt niets. De vier grootste posten (€51,74 tot €44,81) verloren
allemaal; twee van de drie winnaars stonden onderaan de lijst (€23,69 en €23,68).
**Een drempel van €25 zou twee van de drie winnaars hebben uitgesloten** — de
drempel verhogen is dus verkeerd, ook al lijkt 3 van 15 daarom te vragen.

Wat het wél voorspelt is of er een concurrent is. De probe is zelf die meting:
kost verhogen ons het koopblok, dan zat er iemand in dat prijsvenster. Alle 12
verliezers hadden er een, alle 3 winnaars niet.

Onze 20% was dus **een selectiefout, geen marktverschil** — op de juiste
subgroep halen we dezelfde 60% als BE's eerste ronde. Een eerdere conclusie in dit
document dat het aan de drukkere NL-markt lag, is hiermee achterhaald.

### Selectiecriteria: wat is getest en AFGEVALLEN

Bouw geen van deze twee opnieuw — beide zijn op de ronde van 17 augustus getest
en vallen door de mand:

| criterium | voorspelt het? | bewijs |
|---|---|---|
| bedrag (terug te halen winst) | **nee** | top 4 verloor allemaal; 2 van 3 winnaars stonden onderaan de lijst |
| dagen onafgebroken bevroren | **nee** | top 5 op dit criterium = 0 van 5 behouden, slechter dan willekeurig |
| productgroep | **nee** | BE-cijfers: 6 van hun 12 winnaars waren óók vliegengordijnen, terwijl al hun 3 verliezers dat waren |

**Waarom "laatst een concurrent gezien" niet kan werken:** bij een bevroren
artikel zien we nooit of er iemand achter ons zit — zolang wij het koopblok
hebben toont bol.com onze eigen prijs. `sync_buybox.py` vraagt bij bevroren
artikelen alleen "hebben we het koopblok nog". Dat criterium meet dus hoe lang we
het koopblok houden, niet of de concurrent nog bestaat. Getest over 100
`frozen.json`-snapshots: de winnaars zaten op 21, 21 en 15 dagen, midden in het
veld; de twee langst bevroren (29 en 26 dagen) verloren beide.

**DISCUSSIE GESLOTEN (17 augustus, met BE).** Drie criteria getest, drie keer
niets. Ga niet verder zoeken naar een slimmer criterium — dat kost meer tijd dan
het oplevert, en Peter moet elke uitwisseling tussen de twee chats handmatig
doorgeven.

**Werkwijze:** sorteer op bedrag. Niet omdat het voorspelt, maar omdat het bij
gelijke trefkans de opbrengst per treffer maximaliseert. Verwacht ongeveer 20-60%
behoud en zie de rest als de prijs van de informatie.

`probe_history.json` legt sinds 17 augustus per artikel vast: datum, uitkomst
(behouden/terug), de winst waarop geselecteerd is, en de titel. Zo is er over een
paar maanden genoeg data om te zien of er tóch een patroon in zit, zonder er nu
tijd in te stoppen. Beide vormen worden gelezen (oud `{ean: "datum"}` en nieuw
`{ean: {...}}`), dus oude geschiedenis blijft geldig.

Terzijde, niet verder onderzocht: **EAN 8717774825921 zat in zowel de NL- als de
BE-ronde en verloor in beide markten.** Opvallend, maar het is één artikel; BE's
andere twee verliezers zijn bij ons nooit getest, dus er valt niets uit af te
leiden.

## Recente wijziging om te weten (12 augustus, big-gap alleen als het haalbaar is)

`sync_buybox.py` markeerde een artikel voor €10-stappen zodra het gat naar de
concurrent ≥ €10 was, zonder te controleren of die concurrent überhaupt bóven
onze bodemprijs zat. Zit hij eronder, dan is het gat nooit te dichten en komt
het artikel elke sync opnieuw in de lijst terwijl de ochtend-snelstart het er
telkens weer uithaalt.

In NL waren dat steeds dezelfde 6 EAN's, waarvan vier met een bodemprijs van
€108,13 tegen een concurrent op €49,99 — minder dan de helft. Geen geldverlies
(de bodem hield stand), wel ruis die actie suggereerde waar niets mogelijk is.

Gefixt met een haalbaarheidscontrole (`competitor_price - floor > 0.005`) vóór
het vlaggen. Bestaande onhaalbare gevallen ruimen zichzelf op, want ze vallen nu
door naar de bestaande `elif ean in big_gap`-tak. Zes beslisgevallen getest,
allemaal correct.

Zelfde gedachte als `no_competitor.json`: niet blijven proberen wat structureel
niet kan.

## Recente wijziging om te weten (5 augustus, CSV-kolommen op naam)

Overgenomen uit een BE-instructie. `add_eans_to_csv()` in
`src/sync_buybox.py` schreef naar VASTE kolomnummers (`row[0]`, `row[1]`,
`row[2]`). Dat gaat goed op de brede bol.com-export, maar crasht met een
IndexError op Peters 2-koloms bestand (`Productnaam;EAN`) — en juist op
het verkeerde moment, want die functie zet een artikel terug in de lijst
zodra het zijn koopblok verliest. Bij een crash gebeurt dat niet.

Gefixt: kolommen worden nu op NAAM gezocht, met een nette weigering als er
geen EAN-kolom is. `import csv` moest erbij. `remove_eans_from_csv()` in de
engine deed het al goed en is ongewijzigd; verder waren er geen plekken met
vaste kolomnummers (gecontroleerd met grep).

Getest op drie gevallen — smal, breed, en zonder EAN-kolom — allemaal
correct, inclusief dat `csv.DictReader` de toegevoegde EAN daarna
terugvindt.

**Peter hoeft dus niets meer om te zetten.** Beide formaten werken overal.
Hij wisselt in de praktijk per dag: soms de brede export, soms twee
kolommen die hij zelf plakt omdat downloaden bij bol.com niet lukt.

## Over de cron: vertraging is normaal, kijk naar het DAGTOTAAL

GitHub start de geplande runs soms uren niet. Op 2 en 4 augustus stonden
er 's ochtends 1 of 0 runs waar er 7 hadden moeten zijn. Dat ziet er
alarmerend uit, maar **beide dagen eindigden alsnog op 24 cron-runs** —
GitHub haalt de achterstand later op de dag in.

Beoordeel dit dus nooit op een moment halverwege de dag. Kijk naar het
totaal van de vorige dag: 23-24 is goed.

Onze 24 cron-tijden sluiten exact aan op Channable's 24 importslots (elke
run staat 5 minuten ná het einde van een slot, alle 24 gecontroleerd op
4 augustus). Bij vertraging schuift die afstemming binnen de dag, waardoor
Channable bij sommige slots dezelfde prijs opnieuw importeert. Geen
verkeerde prijzen, alleen trager zakken.

Er staat een `src/cron_vangnet.py` klaar die zelf een run start als het
langer dan 45 minuten stil is. **Die is bewust NIET ingepland**, omdat de
dagtotalen goed zijn en extra runs alleen ruis toevoegen. Alleen inzetten
als een dag daadwerkelijk ver onder de 24 eindigt.

**Wintertijd, eind oktober:** Channable's slots staan in Amsterdamse tijd
en schuiven vanzelf mee. Onze cron staat in UTC en doet dat NIET. Alle 24
tijden moeten dan een uur terug, anders draaien de runs 55 minuten vóór
het slot in plaats van 5 minuten erna en importeert Channable structureel
een verouderde prijs.

## Onderzoek 31 juli: de grens van wat prijs kan (BEWUST NIETS AAN GEDAAN)

Peter vroeg hoeveel artikelen een paar uur na de ochtendrun het koopblok
hadden. Uitkomst en analyse hieronder. **Conclusie: er is niets kapot en
er is bewust besloten hier niets aan te veranderen.** Stel dit niet
opnieuw voor zonder aanleiding.

Meting over de 145 artikelen uit de CSV van die dag, 4,5 uur na de
ochtendrun:

| | aantal |
|---|---|
| met koopblok | 4 |
| zonder koopblok | 138 |
| check mislukt | 3 |

De 138 zonder koopblok vallen uiteen in twee groepen:

- **114 waar wij duurder zijn.** De concurrent zit onder onze bodemprijs.
  Puur prijsgevecht dat we bewust niet aangaan.
- **24 waar wij al goedkoper zijn** (mediaan €1,57, tot €4,85) en het
  koopblok tóch niet krijgen.

Voor die 24 is de oorzaak gevonden. Bol.com zet de levertijd van de
koopblok-houder in de JSON-LD van de productpagina
(`offers.shippingDetails.deliveryTime.transitTime`, in KALENDERdagen).
Daaruit bleek:

- bij **20 van de 24** levert de concurrent binnen **1 dag**
- van die 20 staan er **19 al op de bodemprijs**; totale resterende
  ruimte over alle 20 samen is **€0,58**

Dus: geen ruimte meer om te zakken, en de €4,85 korting die we op sommige
al geven pakt het koopblok niet. Tegen een verkoper die morgen levert
win je het met prijs niet.

**Onze levertijd is correct ingesteld.** Channable staat op `3-5d`
(werkdagen); bol.com toont 5-7 omdat dat kalenderdagen zijn. Vanaf
vrijdag: 3 werkdagen → woensdag = 5 dagen, 5 werkdagen → vrijdag = 7.
Er is hier NIETS verkeerd geconfigureerd — een eerdere suggestie in die
richting was onjuist. Sneller kan Peter niet: hij bestelt eerst bij de
leverancier, ontvangt zelf, en verstuurt dan.

**Voorstel dat is afgewezen (1 augustus).** Overwogen is om op die 20 de
prijs juist te VERHOGEN naar vlak onder de concurrent, omdat we daar nu
korting weggeven zonder er koopblok voor terug te krijgen. Peter heeft
besloten dit niet te doen. Redenen: de opbrengst komt alleen van klanten
die via "andere aanbieders" kopen (klein deel van de omzet), en als de
concurrent uitverkocht raakt of zijn prijs verhoogt sta jij te hoog
geprijsd voor een koopblok dat ineens vrijkomt. De huidige regel is
simpel en controleerbaar: altijd zo scherp mogelijk tot de bodem, nooit
eronder. Die blijft.

## Status 31 juli — LET OP: CSV-formaat is veranderd

Peter kan de volledige bol.com-export niet meer downloaden en levert sinds
31 juli een uitgeklede CSV aan met **alleen twee kolommen**:

```
Productnaam;EAN
```

**Dat is voldoende en werkt gewoon.** `load_products()` leest via
`csv.DictReader` alleen `EAN` en `Productnaam` (met een sniffer op de
scheidingsteken), dus de overige 250 kolommen werden toch nooit gebruikt.
Schrik hier niet van en vraag niet om het oude formaat terug.

Die dag stonden er twee uploads kort na elkaar (07:31 met 146 regels,
07:39 met 145) — de tweede is de geldige. Check bij twijfel de
commit-tijd op `bolcom_productinformatie.csv`.

Verder die dag: 13 nieuw, 24 verdwenen, geen tracking verloren, 1
auto-ontdooid, audit schoon. `match_prices.py`: 185 gecheckt → 161
gematcht, 24 nieuw bevroren, 124 op de bodem, 7 mislukt.

### Nieuw hulpmiddel: `src/koopblok_check.py`

Peter vroeg op 31 juli hoeveel artikelen een paar uur ná de ochtendrun
daadwerkelijk het koopblok hadden gepakt. Daarvoor is dit script gemaakt:

```bash
python src/koopblok_check.py --baseline   # nulmeting vastleggen
python src/koopblok_check.py              # meten en vergelijken
```

De nulmeting komt in `output/koopblok_baseline.json`. Draai `--baseline`
NOOIT opnieuw op dezelfde dag nadat je al gemeten hebt — dat overschrijft
het vergelijkingspunt.

Moet lokaal draaien (residentiële verbinding), net als `match_prices.py`.

Naast het aantal gewonnen koopblokken splitst het de verliezers uit in
"concurrent zit onder onze bodemprijs" (onbereikbaar zonder verlies) en
"nog haalbaar". Die uitsplitsing is voor Peter het interessantst: op de
bodem staan is geen falen maar een bewuste keuze.

## Recente wijziging om te weten (30 juli, gewonnen prijs verkeerd omgekeerd)

Gevonden doordat de bandcontrole van 29 juli 4 bevroren artikelen bóven
hun volle prijs meldde.

**De bug.** Bij het vastleggen van een prijs waarop we het koopblok al
hadden, werd de formule handmatig omgekeerd:

```python
newly_won[ean] = round((price - 8) / 2.4, 2)      # alleen de >=4 tak!
```

Dat keert alleen de eerste tak om. Landt de uitkomst onder 4, dan past
Channable bij het terugrekenen de `<4`-tak toe (`(kp+2)*2,4+8`) en komt het
artikel **exact €4,80 te hoog** te staan (2 × 2,4, dus onafhankelijk van
het artikel). Voorbeeld: gewonnen op €17,50 → opgeslagen als 3,96 →
gepubliceerd op €22,30.

**Waarom dit zichzelf in stand hield.** We winnen op een scherpe prijs →
fout opgeslagen → te hoog gepubliceerd → koopblok direct kwijt → volgende
dag terug in de CSV → auto-ontdooid → met €0,50-stappen terug omlaag →
onderweg opnieuw gewonnen → weer fout opgeslagen. Eeuwig rondje. Juist de
scherpst geprijsde artikelen (op hun bodem, dus klantprijs onder 4) waren
het hardst getroffen.

Dit was de hoofdoorzaak van het flipgedrag uit de analyse van 29 juli. De
drie zwaarst getroffen artikelen waren precies de drie grootste flippers
van de hele set: **21, 17 en 13 wisselingen** tegen 3,8 gemiddeld.

**Waarom het niet eerder opviel.** De audit keek alleen naar prijzen ONDER
de bodem. Deze fout zet prijzen te hoog. Er was geen bovengrens-controle
tot de band `[bodemprijs, volle prijs]` van 29 juli.

**De fix.** Op twee plekken vervangen door de canonieke inverse
`calculate_klantprijs_for_target_price(price)`, die beide takken kent:
`match_competitor_prices` in `phase2_repricing.py` en dezelfde constructie
in `sync_buybox.py`.

**Reparatie van de 4 bestaande gevallen.** De winnende prijs was exact
terug te rekenen (`opgeslagen_kp * 2,4 + 8`), dus ze zijn teruggezet op die
prijs — NIET op de volle prijs, want die is hoger en dan raak je het
koopblok alsnog kwijt. Alle vier hadden gewonnen op hun bodemprijs:
€17,50 / €15,73 / €15,99 / €14,43.

Onderscheid tussen de twee soorten "boven de volle prijs":

| opgeslagen klantprijs | oorzaak | oplossing |
|---|---|---|
| < 4 | deze bug | terug naar de winnende prijs |
| >= 4 | inkoopprijs gedaald | drift-klem naar de volle prijs |

Na uitrol: 0 bevroren buiten de band, 0 onder de bodemprijs, audit schoon.

**Les voor later:** er is één canonieke omkering van de prijsformule.
Elke keer dat iemand die met de hand opnieuw opschreef ging het mis —
eerst de afronding (27 juli), nu de `<4`-tak. Grep bij prijswijzigingen op
`8) / 2.4` en laat alles door die ene functie lopen.

## Recente wijziging om te weten (29 juli, bevroren drift omlaag klemmen)

Aanleiding: onderzoek naar artikelen die stelselmatig in en uit het
koopblok flippen. Peter merkte terecht op dat sommige concurrenten heel
ver zakken, dus flippen op zichzelf is geen probleem.

**Wat de analyse opleverde** (58 momentopnames van `frozen.json` uit de
git-historie, 1-28 juli; 216 EAN's wisselden, 1036 wisselingen totaal):

- 170 structurele flippers (≥2 wisselingen). Daarvan **90 op de
  bodemprijs** — gezond gedrag, concurrent duikt eronder, wij gaan bewust
  niet mee. Niets aan te doen.
- **80 met ruimte** boven de bodem, gemiddeld €13,73.

Daarbinnen zat een structureel probleem: **10 van de 155 bevroren
artikelen stonden boven hun eigen ACTUELE volle prijs**, gemiddeld €2,66
te duur. Oorzaak: `clamp_frozen_to_floor` corrigeert alleen omhoog. Daalt
de inkoopprijs bij B-Living, dan blijft een bevroren artikel op zijn oude
te hoge prijs staan en is er niets dat dat opmerkt. Eén prijsdaling op een
folie-serie raakte vier artikelen tegelijk.

Ze flipten aantoonbaar vaker: **80% had ≥5 wisselingen tegen 33% voor de
rest; gemiddeld 12,9 tegen 3,8**. Het mechanisme verklaart dat precies: te
duur staan → koopblok verliezen → volgende dag auto-ontdooid → terugzakken
→ winnen → bevriezen → opnieuw.

**De fix:** `clamp_frozen_to_normal_price(frozen) -> list`, aangeroepen op
dezelfde twee plekken als de bodemcontrole. Zet een bevroren artikel dat
boven zijn volle prijs staat terug op de **verse B-Living-klantprijs**.
Samen met de bodemcontrole houden ze een bevroren prijs binnen de band
`[bodemprijs, volle prijs]`.

Dit geeft geen marge weg: de volle prijs is per definitie wat we voor dat
artikel bij die inkoopprijs vragen. Een winnaar die netjes binnen de band
zit wordt niet aangeraakt, ook niet als hij ruim boven zijn bodem staat.

**Valkuil, en de reden voor die specifieke implementatie:** zet
`frozen[ean]` op de verse klantprijs zélf, niet op
`calculate_klantprijs_for_target_price(volle_prijs)`. Die omgekeerde
berekening rondt terecht een cent naar boven af, waardoor het artikel de
volgende run wéér boven zijn volle prijs staat en zichzelf elke run
opnieuw corrigeert. De idempotentie-test (tweede ronde moet 0 opleveren)
vangt dat af.

Live-run na uitrol: alle 10 gecorrigeerd (€21,32 → €19,04, €20,53 →
€17,77 enz.), audit schoon.

## Status 29 juli (volledige dagcyclus AFGEROND)

CSV: 157 producten (17 nieuw, 14 verdwenen; geen tracking verloren).
Cloud-run: nieuwe dag correct herkend, 14 auto-ontdooid, 141 bevroren, 0
big-gap, 5 no-competitor, 343 master-tracked, 324 aanpassingen, audit
schoon. `match_prices.py`: 184 gecheckt → 170 gematcht, 14 nieuw bevroren,
129 op de bodem, 7 mislukt. Hele feed nagerekend: 5244 gecontroleerd, 0
onder de bodemprijs.

## Status 28 juli (volledige dagcyclus AFGEROND)

CSV: 154 producten. Cloud-run: 10 auto-ontdooid, 137 bevroren, 4
no-competitor, 340 master-tracked, 322 aanpassingen, audit schoon.
`match_prices.py`: 186 gecheckt → 168 gematcht, 18 nieuw bevroren, 123 op
de bodem, 7 mislukt. Hele feed nagerekend: 5253 gecontroleerd, 0 onder de
bodemprijs — eerste volledige dag met de afrondfix actief.

## Status 27 juli (volledige dagcyclus AFGEROND)

CSV: 161 producten (8 nieuw, 20 verdwenen t.o.v. 173 van 26 juli; geen
van de verdwenen 20 stond in `frozen`/`no_competitor`, dus geen tracking
verloren).

- **Cloud-run:** nieuwe dag correct herkend, 8 EAN's auto-ontdooid, 125
  bevroren, 0 big-gap, 4 no-competitor, 340 master-tracked, 323
  aanpassingen, audit schoon.
- **`match_prices.py`:** 198 gecheckt → 176 gematcht, 22 nieuw bevroren,
  133 op de bodemprijs, 6 checks mislukt.

**De `no_competitor`-fix heeft twee koopblokken opgeleverd.** Van de 7
waarmee op 25 juli begonnen werd:

| EAN | prijs 27 juli | bodem | status |
|---|---|---|---|
| 8717774825792 | €223,35 | €197,24 | koopblok gewonnen |
| 8717774825877 | €177,54 | €160,97 | koopblok gewonnen |
| 8717774821015 | €197,24 | €197,24 | verkoper terug, normale route |
| 8716522092585 | €16,69 | €16,68 | op de bodem |
| 8717266373060 | €23,36 | €23,37 | op de bodem |
| 8716522085068 | €62,41 | €62,40 | op de bodem |
| 8717266051630 | €17,46 | €17,46 | op de bodem |

Die twee vliegengordijnen sprongen onder de oude logica elke ochtend terug
naar €247,04 en €201,22. Ze zijn doorgezakt en hebben het koopblok gepakt
ruim bóven hun bodemprijs, dus met marge.

## Recente wijziging om te weten (27 juli, bodembewaking + afrondfix)

Overgenomen uit `...\bol-repricing-be\instructie-NL-bodemcontrole.md`, met
NL-formules en NL-URLs.

### Het probleem

Een bevroren artikel (koopblok gewonnen, staat in `frozen.json`) wordt op
zijn winnende klantprijs vastgehouden: nooit verlaagd, nooit gereset. Elk
ánder codepad herberekent de bodemprijs elke run uit de VERSE B-Living
klantprijs, dus een inkoopprijsverhoging corrigeert zichzelf daar binnen
één run. Bij bevroren artikelen gebeurde dat niet — verhoogt B-Living de
inkoop van iets dat vorige week bevroren is, dan blijven we maanden onder
de margegrens verkopen zonder dat iets het opmerkt.

**Gecontroleerd op 27 juli: 147 bevroren artikelen, 0 onder de bodem.**
Zelfde uitkomst als BE. Er is dus geen geld weggelekt; dit dicht een gat.

### Wat er gebouwd is

1. **`clamp_frozen_to_floor(frozen) -> list`** in de engine. Tilt elk
   bevroren artikel dat onder zijn actuele bodem is gezakt terug naar
   precies die bodem, wijzigt `frozen` in place, geeft de opgetilde
   artikelen terug en print een regel per geval. **Alleen omhoog, nooit
   omlaag** — een bevroren winnaar die ruim boven zijn bodem staat blijft
   onaangeroerd. De 0,01-marge voorkomt dat afrondruis onnodig triggert.
2. **Aangeroepen op twee plekken:** in de cloud-run direct ná het
   auto-unfreeze-blok, en in de ochtend-snelstart direct na het laden van
   frozen/big_gap/master_tracked/last_published (die publiceert alle
   bevroren prijzen óók in de XML en mag dus geen verouderde meenemen).
3. **Upload-constructie gesplitst.** Stond als `if newly_won:` met de
   opslag én het verwijderen uit de CSV eronder. Nu:
   ```python
   if newly_won or frozen_lifted:
       self.upload_json_to_github(frozen, "frozen.json")
   if newly_won:
       self.remove_eans_from_csv(set(newly_won))
   ```
   Anders blijft een optilling zónder nieuwe winnaars onopgeslagen.
4. **Vangnet in de audit:** derde controle die de héle feed nakijkt op
   prijzen onder de bodem, ongeacht via welk pad. Verschijnt als issue in
   `audit_report.json`, dus ook een toekomstig pad dat nu nog niet bestaat
   wordt gezien.

### Wat het vangnet meteen vond (en waarom BE's diagnose niet klopte)

Op de eerste live-run meldde de audit **5 artikelen een cent onder de
bodem** (€14,79 tegen bodem €14,80). BE schreef die cent toe aan het
`last_published`-pad na een mislukte koopblok-check, met "venster maximaal
~30 minuten". Dat klopt niet.

Het is een systematische afrondfout in
`calculate_klantprijs_for_target_price`. De klantprijs moet hele centen
zijn en Channable rekent de prijs terug uit die afgeronde waarde, waardoor
de prijs bij **27% van alle doelprijzen** een cent te laag uitkomt. Niet
tijdgebonden, verdwijnt niet vanzelf bij de volgende run.

Gefixt: na afronden wordt per cent opgehoogd tot de terugrekening niet
meer onder het doel uitkomt. Getest over 29.100 doelprijzen: **0 keer
onder het doel**, maximaal €0,02 erboven. Sommige doelen zijn simpelweg
niet op de cent haalbaar — €14,80 vraagt klantprijs 2,8333, en de dichtste
cent die niet ondersnijdt geeft €14,82.

Let op bij het narekenen: de +€3,80 die je ziet bij doelprijzen ónder
€12,80 is bestaand gedrag, geen fout. Bij klantprijs 0 produceert de
formule €12,80 en lager kan niet.

### Gevolg om te weten

Als een optilling ooit gebeurt, stijgt de prijs van een bevroren winnaar
en kan het koopblok daardoor wegvallen. Dat is bewust: nooit onder de
bodemprijs verkopen weegt zwaarder dan het behoud van een koopblok.

## Recente wijziging om te weten (26 juli, retry verruimd; 12 sept naar 7 pogingen)

De B-Living-server (`www.b-living.eu`) is af en toe een paar minuten
onbereikbaar. Het script stopte dan met "No klantprijzen loaded" en exit
code 1 → failure-mail. **Dat afbreken is gewenst gedrag** (prijzen
publiceren zonder kostenbasis is erger dan een run overslaan) en er is
geen schade: de afbreking gebeurt vóór het genereren van de XML, dus de
feed op GitHub blijft op de laatste goede versie en de volgende run haalt
de gemiste stap in.

Gemeten frequentie: 2 failures op 100 runs = 2%, beide dezelfde oorzaak.
Voelt vaker omdat er per failure een mail komt en de 98 geslaagde runs
stil zijn.

`_get_with_retries` stond op 3 pogingen met steeds 10s pauze — dekt maar
~2 minuten, en beide storingen duurden nét langer, dus alle pogingen
brandden op binnen dezelfde storing. Nu **5 pogingen met verdubbelende
pauze** (10s → 20s → 40s → 80s), wat ~5 minuten overbrugt. Cron-runs zitten
30 minuten uit elkaar, dus de langste retry-keten kan nooit de volgende
run overlappen. Ligt B-Living langer plat, dan komt er alsnog een mail.

## Status 26 juli (volledige dagcyclus AFGEROND)

CSV: 174 producten. Cloud-run: nieuwe dag correct herkend, 16 auto-
ontdooid, 107 bevroren, 7 no-competitor, 340 master-tracked, 323
aanpassingen, audit schoon. `match_prices.py`: 216 gecheckt → 190
gematcht, 26 nieuw bevroren, 136 op de bodem, 8 mislukt.

Eerste dag-grens sinds de `no_competitor`-fix: **alle 7 vastgehouden, geen
enkele teruggesprongen**. De lijst regelde zichzelf ook: 8717774821015
resolvete weer een productpagina (verkoper terug) en is automatisch van de
lijst gehaald.

**Openstaand punt uit 26 juli, bewust niet opgepakt.** EAN 8717774824092
staat op de volle prijs €247,04 en wordt door niets bijgestuurd: hij staat
in geen enkele trackinglijst en is nog nooit in een dagelijkse CSV
voorgekomen. Oorzaak: de dagexport bevat artikelen zónder koopblok die wél
te koop staan; iets met status "Niet te koop" komt daar niet in voor en
komt het systeem dus nooit binnen. In het verkoopaccount staat het filter
**"Niet te koop (356)"** — potentieel 356 artikelen die stilstaan op de
volle prijs. Voorstel lag klaar (die lijst exporteren en in
`no_competitor.json` zetten, met voorfilter op voorraad in de
B-Living-feed); Peter heeft op 26 juli besloten het voorlopig zo te laten.

## Status 25 juli (volledige dagcyclus AFGEROND)

De routine is op 25 juli volledig doorlopen. CSV van die dag: 179
producten (52 nieuw, 12 verdwenen t.o.v. de 139 van 24 juli; geen van de
verdwenen 12 stond in frozen/big_gap, dus geen tracking verloren).

- **Cloud-run:** nieuwe dag correct herkend, 45 EAN's auto-ontdooid, 113
  bevroren, 0 big-gap, 338 master-tracked, 321 aanpassingen, audit schoon.
- **`match_prices.py`:** 208 gecheckt → 198 gematcht, 10 nieuw bevroren,
  133 op de bodemprijs, 9 checks mislukt.

Die 9 mislukte checks leidden tot de `no_competitor.json`-fix hieronder.

## Recente wijziging om te weten (25 juli, `no_competitor.json`)

**Het probleem.** Een groep EAN's faalt élke live-check met de fout
`"no product url in search results"`. Dat betekent NIET dat het artikel
gedelist is. Het betekent: er is geen enkele actieve verkoper, dus
bol.com's zoekresultaat levert geen productpagina op. Wij zijn de enige
verkoper en ons eigen aanbod staat op "Niet te koop" omdat het te duur is.
Peter bevestigde dit op 25 juli in het verkoopaccount (screenshot: artikel
staat er gewoon in, status "Niet te koop", geen koopblok).

Deze EAN's stonden niet in `frozen.json` (nooit een win te bevestigen) en
niet in `big_gap.json` (geen concurrentprijs, dus geen gat te meten), dus
vielen ze in de NORMALE tak → elke kalenderdag reset naar de verse volle
klantprijs. Zichtbaar in de geschiedenis van EAN 8717266373060: klantprijs
6.40 → 7.67 → 6.40 → 6.83 → 6.40 over 20-24 juli. Elke ochtend terug
omhoog, dus nooit uit de "te duur"-status.

**De fix.** Nieuw bestand `no_competitor.json` (platte lijst EAN's, zoals
`master_tracked.json`): vrijgesteld van de dagelijkse reset (zelfde
principe als `big_gap.json`) maar met normale €0,50-stappen — er is geen
concurrentgat om in te lopen, alleen de bodemprijs als eindpunt. Bewust
NIET in `big_gap.json` geduwd: dat bestand stuurt ook de €10-stap-teller
en de vliegengordijn-uitsluiting, die logica past hier niet.

Onderhouden door `match_prices.py`: toevoegen alleen bij die exacte
foutmelding (een time-out of rate-limit mag er nooit in belanden — dan zou
een tijdelijke storing een artikel permanent van de reset uitsluiten),
verwijderen zodra er wél een productpagina resolvet.

Deployed en geverifieerd op 25 juli: 7 EAN's in de lijst, droogloop 7/7 op
verlaagde prijs, live-run audit schoon. Identiek aan wat het BE-project op
dezelfde dag kreeg.

**Belangrijke beperking.** 3 van de 7 zitten al ÓP de bodemprijs
(8716522092585, 8717266373060, 8717266051630). De fix voorkomt dat ze
terugspringen, maar als bol.com ze bij de bodemprijs nog steeds op "Niet
te koop" zet, kan het programma niets meer doen — verder zakken is verlies
draaien. Dat is dan een marge-beslissing voor Peter, geen software-vraag.

**Nog open: een tweede foutsoort.** 2 van de 9 mislukte checks gaven
`"ean not found in JSON-LD"` (8717266317873, 8716522074796). Andere
oorzaak: de productpagina bestaat wél, maar bol.com heeft hem samengevoegd
onder een andere GTIN (bij 8717266317873 toont de pagina EAN
6150541860831). Bewust NIET in `no_competitor.json` gezet. Vraagt een
eigen oplossing — nog niet gebouwd.

## Recente wijziging om te weten (23 juli, bodemprijs-formule-fix)

`calculate_minimum_price()` in `src/phase2_repricing.py` had EERST een
platte formule (`klantprijs × 1,9 + 8`) zonder de `<€4`-knik die de
NORMALE verkoopprijs-formule wel heeft. Peter merkte op dat Channable's
eigen bodemprijs-regel die knik ook toepast. Gefixt naar:
```python
if klantprijs < 4:
    return round(((klantprijs + 2) * 1.9) + 8, 2)
else:
    return round((klantprijs * 1.9) + 8, 2)
```
Al geüpload naar GitHub en geverifieerd (32 artikelen die te laag stonden
zijn automatisch gecorrigeerd naar de juiste, hogere bodemprijs).

**Denk aan het onderscheid tussen twee verschillende "klantprijs"-getallen**
als je dit soort dingen narekent met Peter:
1. de ECHTE klantprijs uit de B-Living-feed (kostbasis) — hier moet de
   bodemprijs-formule op toegepast worden;
2. de klantprijs die dit script zelf in de XML schrijft — een
   achterstevoren uitgerekend, kunstmatig getal om Channable's
   verkoopprijs-formule op een gewenste prijs uit te laten komen. Nooit
   de bodemprijs-formule op DIT getal loslaten, dat geeft een verkeerd
   antwoord (Peter liep hier zelf tegenaan op 23 juli).

## Waar de statusbestanden voor dienen (samengevat)

| bestand | inhoud | betekenis |
|---|---|---|
| `frozen.json` | `{ean: klantprijs}` | koopblok gewonnen, prijs wordt vastgehouden. Verlaat de lijst alleen als de EAN terugkomt in de dagelijkse CSV (= koopblok kwijt) |
| `big_gap.json` | `{ean: resterende_€10_stappen}` | ≥€10 achterstand. Vrijgesteld van de dagelijkse reset, €10-stappen. Vliegengordijnen zijn hier bewust van uitgesloten |
| `no_competitor.json` | platte lijst EAN's | geen actieve verkoper (wij te duur → "Niet te koop"). Vrijgesteld van de dagelijkse reset, normale €0,50-stappen |
| `master_tracked.json` | platte lijst EAN's | ooit in een CSV gezien. Groeit alleen, krimpt nooit vanzelf |
| `state.json` | `{"date": ...}` | datum van de laatste run, stuurt de dagelijkse reset |
| `audit_report.json` | issues per run | uitkomst van de consistentiecontrole |

Alle drie de "vrijgesteld van de reset"-lijsten bestaan om dezelfde reden:
zonder vrijstelling springt de prijs elke ochtend terug naar vol en komt
het artikel er nooit uit.

## Belangrijke geheugen-bestanden (gedeeld tussen alle chats)

Zie `C:\Users\Avantius\.claude\projects\C--Users-Avantius-Documents\memory\`:
- `bol_repricing_session_30juni.md` — volledige technische geschiedenis
- `feedback_chat_split_nl_be_repricing.md` — de NL/BE chat-scheidingsregel
- `feedback_repricing_daily_routine.md` — de dagelijkse-routine-regel
- `feedback_repricing_verbetercyclus.md` — na elke check proactief naar
  verbeterkansen zoeken, niet alleen cijfers opsommen
- `project_dreamhouse_garden_repricing_setup.md` — BE-project (niet
  aankomen vanuit deze chat)

## Projectmap-locatie (LET OP, 25 juli verplaatst)

De projectmap stond in `C:\Users\Avantius\Documents\bol-repricing` maar
is verplaatst naar OneDrive. Er bleken zelfs TWEE kopieën te bestaan op
OneDrive:
- `C:\Users\Avantius\OneDrive\OneDriveClaude-Code-Projecten\bol-repricing`
  — dit is de ACTIEVE/juiste kopie (bevat `.git`, `.claude`, en recente
  bestanden zoals `bodemprijs_lijst_22juli.csv` van 22 juli).
- `C:\Users\Avantius\OneDrive\Projects\bol-repricing` — dit lijkt een
  OUDERE/verouderde back-up (alle bestanden gedateerd 6 juli, geen
  `.git`/`.claude`-map). Waarschijnlijk niet gebruiken, maar nog niet
  100% bevestigd met Peter — vraag het na als daar twijfel over is.

Op 25 juli is vanuit `OneDriveClaude-Code-Projecten\bol-repricing`
gewerkt en gedeployed zonder problemen — die map is dus bevestigd de
actieve kopie.

## Uitwisseling met het BE-project (zonder de scheidingsregel te breken)

De twee projecten wisselen kennis uit via losse instructiedocumenten, die
elke chat in de EIGEN projectmap schrijft. De ander krijgt alleen het pad
aangereikt door Peter en leest het bestand — er wordt nooit in elkaars
project gewerkt.

- BE → NL: `...\bol-repricing-be\instructie-voor-NL-chat.md` (de
  `no_competitor`-fix, door NL uitgevoerd op 25 juli)
- NL → BE: `...\bol-repricing\instructie-voor-BE-chat.md` (bevindingen uit
  de NL-uitvoering, 25 juli)
- BE → NL: `...\bol-repricing-be\instructie-NL-bodemcontrole.md` (de
  bodembewaking, door NL uitgevoerd op 27 juli)
- BE → NL: `...\bol-repricing-be\instructie-NL-afronding.md` (de
  afrondfout bevestigd + gemeten, door NL uitgevoerd op 27 juli)
- NL → BE: `...\bol-repricing\instructie-BE-bevroren-drift.md` (bevroren
  prijs ook omlaag klemmen, 29 juli — nog uit te voeren in BE)
- BE → NL: `...\bol-repricing-be\instructie-NL-margeherstel-probe.md` +
  `instructie-NL-probe-automatisch.md` (de probe i.p.v. onze €0,50-stappen,
  plus automatische kandidaatselectie — door NL uitgevoerd op 17 augustus)
- BE → NL: `...\bol-repricing-be\instructie-NL-taakplanner.md` (volledige
  automatisering via de Windows-taakplanner + preflight-noodstop in de
  cloud-run — door NL uitgevoerd op 17 augustus; zie het blok "EERST DOEN"
  bovenaan dit document)
- NL → BE: `...\bol-repricing\instructie-BE-geen-sync-na-probe.md` (geen sync
  binnen 90 min na een probe-check, 17 augustus — nog uit te voeren in BE)
- NL → BE: `...\bol-repricing\voorstel-BE-bevroren-prijs-terug-omhoog.md` (ons
  €0,50-voorstel; door BE onderbouwd afgewezen, zie hierboven. Bewaard voor de
  achtergrond, niet uitvoeren.)
- NL → BE: `...\bol-repricing\instructie-BE-biggap-onbereikbaar.md` (big-gap
  niet vlaggen als de concurrent onder onze bodemprijs zit, 12 augustus —
  nog uit te voeren in BE)
- NL → BE: `...\bol-repricing\instructie-BE-gewonnen-prijs-inverse.md`
  (gewonnen prijs verkeerd omgekeerd, 30 juli — **BE heeft gecontroleerd:
  die bug zit daar NIET**. Beide opslagplekken gebruikten daar al de
  canonieke functie, de inverse is getest over beide takken rond hun
  10-euro-knik, en de bandcontrole over 87 bevroren artikelen gaf 0 boven
  de volle prijs en 0 onder de bodem. Geen reparatie nodig geweest.)

- NL → BE: `...\bol-repricing\antwoord-BE-levertijdregel-eerste-dag.md`
  (2 sept: de eerste live dag van de levertijdregel, plus drie punten die
  BE aandroeg en die hier zijn nagetrokken — hun sorteerbug hebben wij
  niet, maar 40 van 159 bevroren artikelen worden dagelijks bekeken en de
  rest nooit; onze klemmen gebruiken wel degelijk de verse feedprijs; en
  onze `niet_sneller`-teller mengt "even snel" met "levertijd onleesbaar".)

De drift-klem uit `instructie-BE-bevroren-drift.md` stond op 31 juli al
live in BE; die schone bandcontrole is meteen het bewijs dat hij werkt.

Houd dit patroon aan bij een volgende gedeelde wijziging.

Nog door te geven aan BE (Peter heeft de afrondfout op 27 juli al
mondeling doorgegeven): de afrondfout in
`calculate_klantprijs_for_target_price` zit daar vrijwel zeker ook, want
het is dezelfde formulestructuur. Hun "één cent, maximaal ~30 minuten"-
verklaring dekt het niet.
