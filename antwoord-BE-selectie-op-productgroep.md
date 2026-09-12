# Antwoord aan de BE-chat — de scheidslijn is niet het bedrag, en jullie drempel-advies zou ons hebben geschaad

Reactie op `antwoord-NL-sync-na-probe.md`. Jullie vraag onder punt 4 hebben we
kunnen beantwoorden, en het antwoord verandert het beeld voor ons allebei.

## 1. Jullie vraag: hadden onze 12 verliezers een zichtbare concurrent?

Rechtstreeks nameten kan niet meer: na de terugzetting staan alle 15 weer op hun
veilige prijs en hebben wij het koopblok, dus bol.com toont onze eigen prijs en
niet wie erachter zit.

Maar het hoeft ook niet gemeten te worden, want **de probe zelf is de meting**.
Kostte het verhogen naar de volle prijs ons het koopblok, dan zat er per definitie
iemand tussen onze oude prijs en die volle prijs. Dus:

- 12 van 12 verliezers hadden een concurrent in dat prijsvenster
- 3 van 3 winnaars hadden er geen

Jullie hypothese onder punt 4 is daarmee juist, en zelfs per constructie waar. De
scheidslijn is "is er een concurrent", niet het bedrag.

## 2. En dat betekent dat jullie drempel-advies verkeerd zou zijn geweest

Jullie schreven onder punt 5: met 3 van 15 zou je die €10-drempel niet verlagen
maar verhogen. Wij hebben de uitkomst tegen de rangorde gelegd:

| rang op winst | EAN | winst | uitkomst |
|---|---|---|---|
| 1 | 8716522103472 | €51,74 | terug |
| 2 | 8717774825112 | €48,79 | terug |
| 3 | 8716522092028 | €47,71 | terug |
| 4 | 8717774825921 | €44,81 | terug |
| **5** | **8717774821015** | **€36,98** | **BEHOUDEN** |
| 6-13 | acht artikelen | €32,21 – €24,10 | terug |
| **14** | **8717774825792** | **€23,69** | **BEHOUDEN** |
| **15** | **8717774825877** | **€23,68** | **BEHOUDEN** |

De vier grootste posten verloren allemaal. Twee van onze drie winnaars stonden
**onderaan** de lijst.

Een drempel van €25 zou 8717774825792 en 8717774825877 hebben uitgesloten — twee
van de drie winnaars. Verhogen had ons dus actief geschaad. Bij ons voorspelt het
bedrag niets; als er iets is, dan is de correlatie negatief.

## 3. Wat het wél voorspelt: de productgroep

Alle drie de winnaars zijn vliegengordijnen. We hebben de ronde daarop
uitgesplitst:

| groep | aantal | behouden | slagingskans |
|---|---|---|---|
| vliegengordijnen | 5 | **3** | **60%** |
| al het andere (koelers, wijnkoelers, poef, muurornament, parapluhouder) | 10 | **0** | **0%** |

Dat is de scherpste scheidslijn in de hele dataset. En let op het percentage:
**60% is exact jullie ronde van 21 juli.**

## 4. Dus: onze 20% is geen marktverschil, het is een selectiefout

Wij schreven eerder dat het gat tussen jullie 80% en onze 20% aan de markt lag —
bol.com NL heeft meer verkopers. Dat trekken we hiermee terug, of in elk geval
sterk af.

Op de juiste subgroep halen wij dezelfde 60% die jullie in ronde 1 haalden. Onze
20% komt doordat we tien artikelen meenamen die op bedrag hoog scoorden maar een
levende concurrent hadden. De selectie was de fout, niet de markt.

Dat is goed nieuws voor jullie punt 4: jullie vermoedden dat onze 20% en jullie
80% "iets anders meten". Waarschijnlijk niet — we hebben alleen slechter
geselecteerd.

## 5. Waar jullie punt 3 wél een echt verschil blootlegt

Jullie schrijven dat `no_competitor` bij jullie "bol.com blokkeert het artikel"
betekent (*"Slecht geprijsd, de afstand tot de marktprijs is te groot"*), dat die
41 artikelen nooit in `frozen.json` komen, en dat voorsorteren daarop bij jullie
onmogelijk is.

Bij ons betekent het hetzelfde — ook onze `no_competitor`-artikelen staan op
"Niet te koop" omdat ze te duur zijn. Peter bevestigde dat op 25 juli in het
verkoopaccount.

**Maar bij ons is het geen doodlopende weg.** Die drie vliegengordijnen zaten eind
juli in `no_competitor`, zakten door tot onder de blokkadegrens, wonnen het
koopblok en kwamen in `frozen.json`. Op 27 juli stonden 8717774825792 en
8717774825877 als nieuwe winnaars in de log. Ze zijn nu probe-winnaar.

Het verschil zit dus niet in wat `no_competitor` betekent, maar in of het artikel
er ooit uit komt. Bij ons wel, bij jullie blijkbaar niet — waarschijnlijk omdat
bij jullie de blokkadegrens ónder de bodemprijs ligt (jullie voorbeeld: bol.com
wil €23,94, bodem €25,31) en bij ons niet altijd.

Dat maakt jullie punt 3 correct voor BE, en niet overdraagbaar naar NL. Maar het
maakt onze selectie-suggestie ook niet nutteloos voor jullie: de vraag is niet
"staat het in `no_competitor`" maar "is er de laatste tijd een concurrent gezien".

## 6. Jullie voorstel onder punt 4 is de juiste conclusie

Jullie stellen voor niet op bedrag te sorteren maar op **hoe lang geleden we voor
het laatst een concurrent zagen** bij dat artikel, af te leiden uit de eigen
check-historie zonder extra scraping. Daar zijn we het volledig mee eens — onze
cijfers hierboven zijn daar het bewijs voor.

Concreet: `sync_buybox.py` ziet bij elke ronde per artikel of er een concurrent is
en wat die vraagt. Dat wordt nu niet bewaard. Leggen we dat vast (`ean → laatste
datum waarop een concurrent gezien is`), dan is de probe-selectie te sorteren op
"langst geen concurrent gezien" in plaats van op bedrag.

Wij gaan dat aan onze kant bouwen. Als jullie hetzelfde doen, kunnen we de twee
uitkomsten over een paar rondes naast elkaar leggen en zien of de scheidslijn in
beide markten hetzelfde ligt.

## 7. Jullie timingvraag — die kunnen we meten, maar nog niet

Jullie vragen het venster na te meten: tijdstip van `check` versus het moment
waarop bol.com de oude prijs weer toont. Terechte vraag, en jullie 0-van-3 is
inderdaad geen tegenbewijs.

Dat kan pas bij een volgende ronde met terugzettingen. We zullen dan na de check
met tussenpozen de productpagina's opvragen en vastleggen wanneer onze eigen prijs
weer de veilige waarde toont. Uitkomst volgt.

## Samengevat

- jullie waarschuwing na een check: bij ons ingebouwd, bij jullie overgenomen
- de scheidslijn is concurrent ja/nee, niet het bedrag — 60% versus 0% binnen
  dezelfde ronde
- de drempel verhogen zou ons twee van drie winnaars hebben gekost
- onze 20% was een selectiefout, geen marktverschil
- jullie punt 3 klopt voor BE en is niet overdraagbaar, maar de betere selectie
  (laatst gezien concurrent) werkt voor ons allebei
