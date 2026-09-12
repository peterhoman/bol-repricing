# Instructie voor de BE-chat (Dreamhouse&Garden) — gewonnen prijs verkeerd omgekeerd

Gevonden, gerepareerd en uitgerold in het **NL-project** (Tiptopshop) op 30 juli
2026. Zit vrijwel zeker ook in BE: het is dezelfde codeconstructie, niet iets
NL-specifieks.

Bouw de fix in `bol-repricing-be` met de **BE-formules en BE-URLs**. Alle
bedragen hieronder zijn NL-cijfers (×2,4); BE rekent ×2,6, dus jullie getallen
worden anders. Reken ze zelf na — neem ze niet over.

---

## Deel 1: de uitleg

### Waar het misgaat

Channable rekent de verkoopprijs uit de klantprijs met **twee takken**. In NL:

```
klantprijs >= 4:  prijs = klantprijs * 2,4 + 8
klantprijs <  4:  prijs = (klantprijs + 2) * 2,4 + 8
```

Die tweede tak is de knik voor goedkope artikelen. Zolang je vooruit rekent
(klantprijs → prijs) gaat het goed, want `calculate_normal_price` kent beide
takken.

Het probleem zit in de andere richting. Als we live constateren dat we het
koopblok al hebben, willen we die winnende prijs vastleggen. Dat gebeurde zo:

```python
newly_won[ean] = round((price - 8) / 2.4, 2)
```

Dit keert **alleen de eerste tak** om. De code die de prijs later weer
uitrekent gebruikt wél beide takken. Komt de uitkomst onder 4, dan passen die
twee dus verschillende formules toe — en dat loopt uit elkaar.

### Waarom precies €4,80

Stel de winnende prijs is €17,50.

```
opgeslagen klantprijs = (17,50 - 8) / 2,4 = 3,96
```

3,96 is kleiner dan 4, dus Channable pakt de tweede tak:

```
gepubliceerde prijs = (3,96 + 2) * 2,4 + 8 = 22,30
```

We wonnen op €17,50 en publiceren op €22,30. Het verschil is altijd exact het
extra bedrag uit de knik, maal de vermenigvuldiger:

```
2 * 2,4 = 4,80
```

Bij BE met ×2,6 wordt dat een ander bedrag — controleer welke constante in
jullie `<`-tak staat en welke drempel jullie gebruiken, en bereken het verschil
zelf. Reken het niet vanuit ons cijfer af.

Het bedrag is **niet** afhankelijk van het artikel. Elk artikel waarvan de
opgeslagen klantprijs onder de drempel landt, komt met exact hetzelfde bedrag te
hoog te staan.

### Waarom dit zichzelf in stand houdt

Dit is het venijnige deel, en de reden dat het lang onopgemerkt bleef:

1. We winnen het koopblok op een scherpe prijs (vaak juist op de bodemprijs).
2. Die prijs wordt fout opgeslagen en het artikel komt fors te hoog te staan.
3. Daardoor verliezen we het koopblok direct weer.
4. Het artikel komt de volgende dag terug in de dagelijkse CSV, wordt
   auto-ontdooid, en zakt met €0,50-stappen weer naar beneden.
5. Onderweg winnen we opnieuw → terug naar stap 1.

Het artikel blijft dus eeuwig rondjes draaien, en juist de artikelen die het
scherpst staan (op hun bodem, dus met een klantprijs die onder de drempel
uitkomt) zijn het hardst getroffen.

In NL waren de drie zwaarst getroffen artikelen precies de drie grootste
flippers van de hele set: **21, 17 en 13 koopblok-wisselingen in vier weken**,
tegen een gemiddelde van 3,8 voor de rest.

### Waarom het niet eerder opviel

De audit controleerde of iets onder de bodemprijs stond. Deze fout zet prijzen
juist te **hoog**, dus daar viel hij niet onder. Er was geen enkele controle op
"staat iets boven zijn eigen volle prijs".

In NL kwam hij pas boven water nadat we een bovengrens gingen controleren — de
band `[bodemprijs, volle prijs]` uit `instructie-BE-bevroren-drift.md`. Als
jullie die bandcontrole nog niet hebben, bouw die eerst; dan zie je meteen
hoeveel gevallen BE heeft.

---

## Deel 2: de fix

### Twee plekken, dezelfde fout

Zoek op alle plekken die de formule handmatig omkeren:

```bash
grep -n "8) / 2.6\|8)/2.6" src/*.py
```

In NL stond hij twee keer, en beide moesten aangepast:

- `src/phase2_repricing.py` — in `match_competitor_prices`, bij het bevriezen
  van een artikel dat we al winnen
- `src/sync_buybox.py` — in dezelfde constructie

Vervang beide door de canonieke inverse die het project al heeft:

```python
newly_won[ean] = self.calculate_klantprijs_for_target_price(price)
```

en in `sync_buybox.py` (daar is de engine een los object):

```python
new_wins[ean] = engine.calculate_klantprijs_for_target_price(price)
```

Die functie kent beide takken en rondt bovendien nooit onder de doelprijs af.
Gebruik hem — schrijf niet opnieuw een eigen omkering, dat is precies hoe deze
bug ontstond. Als je bij de `grep` nog meer plekken vindt, pak die ook mee.

### De bestaande foute waarden repareren

De code is nu goed, maar `frozen.json` bevat nog verkeerd opgeslagen waarden.
Die corrigeren zichzelf niet: een bevroren prijs wordt vastgehouden.

De winnende prijs is exact terug te rekenen, want je weet welke formule de oude
code gebruikte:

```python
winnende_prijs = round(opgeslagen_kp * 2.6 + 8, 2)      # BE-getallen invullen
nieuw_kp = engine.calculate_klantprijs_for_target_price(winnende_prijs)
```

**Belangrijk: onderscheid twee soorten "boven de volle prijs".** Als je de
bandcontrole hebt, vind je twee groepen die er allebei boven staan, met
verschillende oorzaken en verschillende oplossingen:

| opgeslagen klantprijs | oorzaak | wat te doen |
|---|---|---|
| onder de drempel (NL: < 4) | **deze bug** | terugzetten op de winnende prijs |
| op of boven de drempel | inkoopprijs is gedaald | de drift-klem naar de volle prijs |

Zet de bug-gevallen **niet** met de drift-klem naar de volle prijs. Die is hoger
dan de prijs waarop we wonnen, dus dan raak je het koopblok alsnog kwijt. In NL
scheelde dat bijvoorbeeld €17,50 (winnende prijs) tegen €20,00 (volle prijs).

Doe de reparatie als **eenmalig script**, niet als permanente logica in de
engine — de fix voorkomt nieuwe gevallen, dus die heuristiek hoeft niet te
blijven staan. Draai eerst een droogloop en controleer dat elke nieuwe prijs
binnen `[bodemprijs, volle prijs]` valt vóór je uploadt.

### Wat het in NL opleverde

4 bevroren artikelen, alle vier gewonnen op hun bodemprijs:

| EAN | won op | stond op | verschil |
|---|---|---|---|
| 8716522021073 | €17,50 | €22,30 | €4,80 |
| 3700837161345 | €15,73 | €20,53 | €4,80 |
| 8717266342479 | €15,99 | €20,79 | €4,80 |
| 8716522081718 | €14,43 | €19,23 | €4,80 |

Na de reparatie en een live-run: 0 bevroren artikelen buiten de band, 0 onder de
bodemprijs, audit schoon.

## Testen vóór uitrol

1. **Beide takken van de inverse.** Vraag een doelprijs die een klantprijs onder
   de drempel oplevert en controleer dat `calculate_normal_price` van het
   resultaat weer op die doelprijs uitkomt (of maximaal een cent erboven).
   Dit is de test die de bug zou hebben gevangen.
2. **Bandcontrole over alle bevroren artikelen**: geen enkel artikel buiten
   `[bodemprijs, volle prijs]`.
3. **Droogloop van de reparatie**, met de check dat elke nieuwe prijs binnen de
   band valt. Stub `upload_json_to_github` af.
4. **Na uitrol**: een live-run en de bandcontrole opnieuw — moet 0 opleveren.

## Uitrol

De cloud-job draait de versie op **GitHub**, niet de lokale. Upload beide
gewijzigde bestanden los via de Contents API, niet via `setup_upload.py` (dat
overschrijft ook de statusbestanden met lokale stubs).

## Tot slot

De les die breder geldt dan deze bug: er staat één canonieke omkering van de
prijsformule in het project. Elke keer dat iemand hem met de hand opnieuw
opschreef, ging het fout — eerst met de afronding (zie
`instructie-NL-afronding.md`), nu met de `<`-tak. Bij een volgende wijziging aan
de prijslogica is het de moeite waard om te grep'pen op handmatige omkeringen en
ze allemaal door die ene functie te laten lopen.
