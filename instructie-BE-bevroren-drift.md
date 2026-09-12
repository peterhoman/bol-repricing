# Instructie voor de BE-chat (Dreamhouse&Garden) — bevroren prijs ook OMLAAG klemmen

Gebouwd, getest en uitgerold in het **NL-project** (Tiptopshop, repo
`peterhoman/bol-repricing`) op 29 juli 2026. Peter wil hem ook in BE, zodat
beide projecten identiek werken.

Bouw hem in `bol-repricing-be` met de **BE-formules en BE-URLs** — neem geen
NL-getallen over. BE rekent ×2,6 waar NL ×2,4 rekent, dus alle bedragen
hieronder zijn NL-cijfers ter illustratie.

Dit bouwt voort op `clamp_frozen_to_floor` uit `instructie-NL-bodemcontrole.md`,
die in BE al staat.

## Het probleem

`clamp_frozen_to_floor` corrigeert een bevroren artikel alleen **omhoog**, voor
het geval de inkoopprijs is gestegen. Er is niets dat het omgekeerde opvangt.

Een bevroren artikel (koopblok gewonnen) wordt op zijn winnende klantprijs
vastgehouden en nooit opnieuw beoordeeld. Verlaagt de leverancier daarna de
inkoopprijs, dan blijft het artikel op zijn oude, nu te hoge prijs staan. Het is
dan duurder dan zijn **eigen actuele volle prijs** — de prijs die we voor dat
artikel zouden vragen als het vandaag nieuw binnenkwam.

Dat is geen extra marge. Het is een restant van een oude kostprijs.

## Gemeten in NL op 29 juli (meet dit ook in BE)

Over 58 momentopnames van `frozen.json` uit de git-historie (1-28 juli):

| Meting | Uitkomst |
|---|---|
| Bevroren artikelen die boven hun eigen volle prijs stonden | **10 van 155** |
| Gemiddeld te duur | **€2,66** (samen €26,57) |
| Waarvan notoire flipper (≥5 koopblok-wisselingen) | **8 van de 10** |

En het verschil in flipgedrag was groot:

| groep | ≥5 wisselingen | gemiddeld aantal wisselingen |
|---|---|---|
| te duur (10) | 80% | **12,9** |
| normaal (144) | 33% | **3,8** |

Ruim drie keer zoveel. Klein aantal, dus geen hard bewijs, maar het mechanisme
verklaart het precies: te duur staan → koopblok verliezen → de volgende dag
auto-ontdooid → terugzakken → winnen → bevriezen → opnieuw.

Eén leverancierswijziging op een hele folie-serie raakte in NL vier artikelen
tegelijk. Kijk dus of BE ook zulke clusters heeft — dat maakt de meting
overtuigender voor Peter dan losse gevallen.

## Wat te bouwen

### Nieuwe methode, naast `clamp_frozen_to_floor`

Naam: `clamp_frozen_to_normal_price(self, frozen: dict) -> list`

```python
lowered = []
for ean, held_klantprijs in list(frozen.items()):
    fresh_klantprijs = self.bliving_klantprijzen.get(ean)
    if fresh_klantprijs is None:
        continue
    normal_price = self.calculate_normal_price(fresh_klantprijs)
    held_price = self.calculate_normal_price(held_klantprijs)
    if held_price > normal_price + 0.005:
        frozen[ean] = fresh_klantprijs
        lowered.append((ean, held_price, normal_price))
        print(...)
return lowered
```

**Let op dit detail — het is de enige valkuil.** Zet `frozen[ean]` op de
**verse klantprijs zelf**, niet op
`calculate_klantprijs_for_target_price(normal_price)`. De verse klantprijs ís
per definitie de waarde die de volle prijs oplevert, dus dit is exact en
idempotent. Ga je via de omgekeerde berekening, dan rondt die (terecht) een cent
naar boven af, staat het artikel de volgende run wéér boven zijn volle prijs, en
corrigeert hij zichzelf elke run opnieuw. Oneindig heen en weer.

Gebruik `+ 0.005` als marge, om dezelfde reden als bij de bodemcontrole: kleiner
dan een cent, anders glipt precies-een-cent-erboven er doorheen.

### Aanroepen op dezelfde twee plekken als de bodemcontrole

In de stateless cloud-run:

```python
frozen_changed = self.clamp_frozen_to_floor(frozen)
frozen_changed += self.clamp_frozen_to_normal_price(frozen)
if frozen_changed:
    self.upload_json_to_github(frozen, "frozen.json")
```

In de ochtend-snelstart:

```python
frozen_lifted = self.clamp_frozen_to_floor(frozen)
frozen_lifted += self.clamp_frozen_to_normal_price(frozen)
```

De bestaande gesplitste upload (`if newly_won or frozen_lifted:`) blijft zoals
hij is en werkt hier meteen goed.

De twee klemmen bijten elkaar niet: de volle prijs ligt altijd boven de
bodemprijs, dus samen houden ze een bevroren prijs binnen de band
`[bodemprijs, volle prijs]`.

## Testen vóór uitrol

Stub `upload_json_to_github` af met een lambda die `True` teruggeeft.

1. **Echte data**: draai de methode op de huidige `frozen.json` en meld het
   aantal aan Peter. In NL waren dat er 10.
2. **Idempotent**: draai hem meteen nog een keer. De tweede ronde moet **0**
   verlagen. Dit is de test die de valkuil hierboven afvangt.
3. **Band**: controleer dat na beide klemmen geen enkel bevroren artikel buiten
   `[bodemprijs, volle prijs]` valt.
4. **Beide klemmen samen**: zet één artikel kunstmatig veel te hoog en één veel
   te laag, en controleer dat de eerste naar de volle prijs gaat, de tweede naar
   de bodem, en dat geen enkele andere winnaar wordt aangeraakt.

In NL: 10 verlaagd, tweede ronde 0, 0 buiten de band, beide kunstmatige
gevallen correct, 0 onterecht aangeraakt.

## Uitrol

De cloud-job draait de versie die op **GitHub** staat, niet de lokale. Upload het
engine-bestand dus los via de Contents API — niet via `setup_upload.py`, dat
overschrijft ook de statusbestanden met lokale stubs.

Live-run in NL na uitrol: alle 10 gecorrigeerd (€21,32 → €19,04, €20,53 → €17,77
enzovoort), audit schoon.

## Wat dit bewust NIET doet

Een bevroren winnaar die netjes binnen de band staat wordt niet aangeraakt, ook
niet als hij ruim boven zijn bodem zit. Dat is een winnaar die marge maakt.
Alleen prijzen buiten de band worden teruggezet.
