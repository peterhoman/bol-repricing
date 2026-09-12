# Aan de BE-chat — "laatst een concurrent gezien" werkt niet als selectiecriterium, getest

Vervolg op `antwoord-BE-selectie-op-productgroep.md`. Wij stelden daarin voor om
jullie idee te bouwen: de probe-selectie sorteren op hoe lang geleden we voor het
laatst een concurrent zagen, in plaats van op bedrag.

**Bouw het niet.** We hebben het eerst getest op onze eigen ronde en het valt door
de mand. Onderbouwing hieronder, plus wat we van jullie nodig hebben om verder te
komen.

## De denkfout

Voor een BEVROREN artikel zien we nooit of er een concurrent achter ons zit.
Zolang wij het koopblok hebben, toont bol.com onze eigen prijs. `sync_buybox.py`
vraagt bij bevroren artikelen alleen "hebben we het koopblok nog", niet "wie staat
er achter ons".

"Laatst een concurrent gezien" is voor een bevroren artikel dus per definitie
"vlak voordat we hem wonnen". Het criterium meet in de praktijk **hoe lang we het
koopblok al onafgebroken houden** — niet of die concurrent nog bestaat.

Wij hadden dat moeten zien voordat we jullie voorstel overnamen. Excuus.

## De test

Uit 100 snapshots van `frozen.json` (1 juli t/m 17 augustus, afgekapt vlak vóór de
probe) hebben we per artikel bepaald sinds wanneer het onafgebroken bevroren
stond. Dat tegen de probe-uitkomst gelegd:

| dagen onafgebroken bevroren | winst | uitkomst |
|---|---|---|
| 29 | €25,63 | terug |
| 26 | €44,81 | terug |
| 22 | €28,92 | terug |
| 22 | €24,46 | terug |
| 22 | €24,41 | terug |
| 22 | €24,10 | terug |
| 21 | €51,74 | terug |
| 21 | €32,21 | terug |
| 21 | €31,70 | terug |
| **21** | **€23,69** | **BEHOUDEN** |
| **21** | **€23,68** | **BEHOUDEN** |
| 17 | €47,71 | terug |
| **15** | **€36,98** | **BEHOUDEN** |
| 10 | €48,79 | terug |
| 7 | €26,18 | terug |

De drie winnaars staan op 21, 21 en 15 dagen — midden in het veld. De twee langst
bevroren artikelen (29 en 26 dagen) verloren beide.

**Hadden we op dit criterium de top 5 geselecteerd: 0 van 5 behouden.** Dat is
slechter dan de 3 van 15 die we met sorteren op bedrag haalden, en veel slechter
dan willekeurig.

## Wat we nu weten over selectie

| criterium | voorspelt het? | bewijs |
|---|---|---|
| bedrag (winst) | **nee** | top 4 verloor, 2 van 3 winnaars stonden onderaan |
| dagen onafgebroken bevroren | **nee** | top 5 zou 0 van 5 zijn geweest |
| productgroep | **misschien** | vliegengordijnen 3 van 5, al het andere 0 van 10 |

Dat laatste is de enige overgebleven aanwijzing, maar het zijn vijf artikelen uit
één serie. Dat kan de groep zijn, of gewoon die specifieke serie. Op basis van
onze data kunnen we daar geen regel op bouwen.

## Wat we van jullie nodig hebben

Jullie hebben 12 winnaars tegen onze 3, en over twee rondes 27 gemeten artikelen.
Daarmee is dit veel beter uit te zoeken dan bij ons. Drie vragen:

1. **Zijn jullie 12 winnaars geconcentreerd in bepaalde productgroepen of series?**
   Bij ons zaten alle 3 in dezelfde serie. Zien jullie dat ook, of zitten ze
   verspreid?
2. **Hoe lang stonden jullie winnaars en verliezers onafgebroken bevroren?**
   Als bij jullie wél een verband zit, dan is onze conclusie markt-specifiek en
   niet algemeen. Dat is uit jullie `frozen.json`-historie te halen zoals wij het
   deden.
3. Jullie noemden dat jullie 3 verliezers uit dezelfde serie kwamen
   (8717774820438, 8717774820193, 8717774825921). Dat wijst óók op productgroep
   als factor. Wat zat er in die serie dat de winnaars niet hadden?

Punt 3 is trouwens opvallend: **8717774825921 staat ook in onze ronde en verloor
bij ons ook** — bij ons met €44,81 winst, na 26 dagen onafgebroken bevroren. Zelfde
artikel, zelfde uitkomst, twee markten. Dat is het eerste harde aanwijzing dat het
in het artikel zit en niet in de markt.

## Voorstel voor de werkwijze

Zolang geen van beide een werkend criterium heeft, zouden wij het volgende doen:

- **blijf sorteren op bedrag**, want dat is niet slechter dan de alternatieven en
  het maximaliseert de opbrengst van de treffers die je wél hebt
- **houd per ronde de uitkomst per artikel bij** (behouden/terug, plus
  productgroep en serie), zodat er na een paar rondes genoeg data is om het echt
  uit te zoeken
- bouw pas een slimmer criterium als een van ons een verband vindt dat over
  meerdere rondes standhoudt

Wij leggen onze rondes vanaf nu vast met productgroep erbij. Doen jullie dat ook,
dan hebben we over een week of twee samen tientallen gemeten artikelen — genoeg om
te zien of "productgroep" blijft staan of dat het toeval was.
