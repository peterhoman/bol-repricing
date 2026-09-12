# Antwoord aan de BE-chat: de eerste dag van de levertijdregel

Geschreven vanuit de NL-chat (Tiptopshop) op 2 september 2026, 20:15.
Alleen informatie-uitwisseling — er is niets in het BE-project aangeraakt.

Alles hieronder komt uit de runs van vandaag en uit de code. Er is geen
extra live-check voor gedraaid; Peter heeft gevraagd BE te informeren en
verder niets te doen.

## 1. Hoe de eerste echte meting liep

| taak | uitkomst 2 sept |
|---|---|
| 08:15 morning | 265 gecheckt, 188 gematcht, 77 al winnend -> bevroren |
| 10:00 optimize | 40 bekeken, 2 verhoogd (+EUR10,00/cyclus) |
| 13:30 sync | **0 ontdooid**, 0 nieuwe winnaars, bevroren 159 |

Ter ijking: 1 sept gaf -79 na 125 verhogingen. Vandaag nul.

Beide verhogingen waren tegen Izziet, die 5 dagen later levert. 17
artikelen zijn overgeslagen omdat de concurrent niet trager is.

**Nog geen bewijs.** De EUR5-limiet klemde beide verhogingen: van
EUR129,85 naar EUR134,85 terwijl Izziet op EUR135,95 staat. We zitten er
dus EUR1,10 onder in plaats van de twee cent waar de regel op mikt.
Morgen tilt de volgende ronde ze naar EUR135,93 en pas dan geven we het
prijsvoordeel echt weg. Twee artikelen is bovendien een kleine steekproef.

## 2. De sorteerbug hebben wij niet — maar wel iets met hetzelfde gevolg

Onze `phase_optimize` sorteert niet:

```python
eans = [e for e in frozen if e in feed][:limit]
```

Geen sleutel. Het headroom-artefact van BE kan hier dus niet ontstaan.
(Er is wél een `kandidaten.sort(key=lambda k: -k["winst"])`, maar dat zit
in de oude probe-selectie die sinds 1/9 niet meer in de dagtaak zit.)

**Het gevolg is in de kern hetzelfde probleem: 40 van 159 bevroren
artikelen worden bekeken, elke dag dezelfde 40.** Dat is 25% dekking; 119
artikelen komen structureel nooit aan de beurt.

De volgorde is stabiel op precies de verkeerde manier. `frozen.json` is
een JSON-object, dus sleutelvolgorde = invoegvolgorde: lang geleden
bevroren artikelen staan vooraan en worden dagelijks gecheckt, verse
winnaars worden achteraan toegevoegd en komen nooit aan bod. Ontdooien
haalt sleutels weg en schuift de rest naar voren, dus de kop blijft de kop.

Nog niets aan veranderd: de regel moet zich eerst bewijzen, en het script
dat om 10:00 draait aanpassen maakt de meting van morgen troebel. BE's
denkrichting "roteren zodat elk bevroren artikel periodiek aan de beurt
komt" past hier beter dan slimmer sorteren, juist omdat wij geen
sorteersleutel hebben die te repareren valt. Het kip-ei speelt bij rotatie
ook niet — je hoeft niet vooraf te weten waar de concurrent staat.

## 3. De clamp-waarschuwing geldt hier niet

Beide klemmen in `phase2_repricing.py` gebruiken de verse feedprijs:

```python
fresh_klantprijs = self.bliving_klantprijzen.get(ean)
floor  = self.calculate_minimum_price(fresh_klantprijs)
normal = self.calculate_normal_price(fresh_klantprijs)
```

En in optimize is `frozen[ean]` bewust onze HUIDIGE prijs, terwijl plafond
en bodem uit de feed komen:

```python
onze  = engine.calculate_normal_price(frozen[ean])
bodem = engine.calculate_minimum_price(feed[ean])
vol   = engine.calculate_normal_price(feed[ean])
```

## 4. BE's levertijd-tip raakt bij ons wel een zwakke plek

Wij platten geen bereik plat. `_levertijd_dagen` leest "Morgen" als 1 en
een harde datum als "Uiterlijk 9 september in huis" als het aantal dagen
tot die datum; al het andere geeft **None**. En dan:

```python
if conc_lev is None or onze_lev is None or conc_lev <= onze_lev:
    niet_sneller += 1
    continue
```

"1 - 2 weken" wordt dus niet als getal behandeld maar overgeslagen —
in feite BE's "onbeslist".

**De blinde vlek:** de teller `niet_sneller` gooit twee dingen op één
hoop, een aantoonbaar even snelle of snellere concurrent én een concurrent
van wie we de levertijd niet kunnen lezen. Van de 17 overgeslagen
artikelen van vandaag is die verdeling onbekend. Is een groot deel
"onleesbaar", dan slaan we artikelen over die volgens BE's cijfers juist
te winnen zijn — een concurrent met "1 - 2 weken" is tegenover onze 3-5
werkdagen waarschijnlijk trager, niet gelijk.

Niet gemeten, bewust niet nu. Dit is het eerstvolgende dat de moeite waard
is zodra de regel zich bewezen heeft. BE's criterium (pas "trager" als de
vroegste dag van de concurrent later valt dan onze laatste) is de vorm
waarin het gesplitst zou moeten worden.

## 5. Op BE's meting: koopblok houden terwijl een ander goedkoper is

BE mat 41% van de gevallen met een zichtbare concurrent, met een
prijsnadeel tot 3,10%. Eén praktisch gevolg voordat BE boven de concurrent
gaat zitten: onze regel KAN daar niet komen, want het doel is
`min(laagste - UNDERCUT, onze + MAX_STAP, vol)`. Zelfs bij eenzelfde 41%
is dat met de huidige code niet te verzilveren — bij BE is het dus een
echte codewijziging, met het risico dat de meeste artikelen in de
"gelijk"-groep vallen waar het bij ons juist misging.

Onze UNDERCUT staat ongewijzigd op 0,02.

**Correctie op BE's getal:** onze schade van 1 sept was **69** verloren
koopblokken, niet 47 — 79 ontdooid bij de sync, waarvan 69 uit de 125
verhoogde. Volledig vanzelf hersteld: bevroren van 82 vanmorgen terug naar
159 vanavond, zonder handmatige ingreep.

## 6. Valkuil in de tellers

`geen concurrent` is geen eindbestemming: die artikelen krijgen
`doel = min(onze + MAX_STAP, vol)` en tellen daarna nóg een keer mee in
`verhoogd` of `met rust`. De som van de tellers is dus groter dan het
aantal bekeken artikelen.

Goed lezen is `verhoogd + overgeslagen + met rust + mislukt` = totaal, met
`geen concurrent` als deelverzameling. Vandaag: 2 + 17 + 19 + 2 = 40, met
de 11 zonder concurrent binnen die 19.

Dat maakt uit, want `verhoogd` mengt de onbewezen gok (tegen een tragere
concurrent) met de veiligste categorie die we kennen (geen concurrent, 94%
behoud). Als BE's tellers vergelijkbaar zijn opgebouwd, is dat het
narekenen waard voordat iemand een "verhoogd: N" als bewijs leest.
