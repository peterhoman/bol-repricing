# Instructie voor de BE-chat (Dreamhouse&Garden) — big-gap niet vlaggen als het gat onhaalbaar is

Gebouwd, getest en uitgerold in het **NL-project** (Tiptopshop) op 12 augustus 2026.
Zit vrijwel zeker ook in BE: het is dezelfde codeconstructie in `sync_buybox.py`,
niet iets NL-specifieks.

Bouw hem in `bol-repricing-be` met de **BE-formules en BE-URLs**. De bedragen
hieronder zijn NL-cijfers ter illustratie — reken je eigen gevallen na.

## Het probleem

`sync_buybox.py` markeert een artikel voor €10-stappen zodra we €10 of meer
boven de concurrent zitten:

```python
if gap >= 10 and not engine.is_excluded_from_big_steps(ean):
    big_gap_added[ean] = int(gap // 10)
```

Daar ontbreekt een controle: **zit die concurrent überhaupt boven onze
bodemprijs?** Zo niet, dan is het gat nooit te dichten. De €10-stappen brengen
het artikel hooguit tot de bodem — waar het via de normale route sowieso al
komt — en daar houdt het op.

Het gevolg is een rondje dat zichzelf herhaalt:

1. de sync markeert het artikel voor €10-stappen
2. de ochtend-snelstart matcht het, klemt het op de bodem en haalt het uit
   `big_gap` (die doet `big_gap.pop(ean, None)` voor elk verwerkt artikel)
3. de volgende sync ziet hetzelfde gat en markeert het opnieuw

In NL waren dat exact dezelfde 6 EAN's, sync na sync.

## Wat we in NL zagen

| EAN | onze bodemprijs | concurrent | verschil |
|---|---|---|---|
| 3700837161697 | €52,16 | €40,95 | −€11,21 |
| 8716522024258 | €44,27 | €25,00 | −€19,27 |
| 8717266008337 | €108,13 | €49,99 | −€58,14 |
| 8717266008344 | €108,13 | €49,99 | −€58,14 |
| 8717266008375 | €108,13 | €49,99 | −€58,14 |
| 8717266008382 | €108,13 | €49,99 | −€58,14 |

Die laatste vier: de concurrent vraagt minder dan de hélft van onze bodemprijs.
Daar valt niets te winnen zonder verlies te draaien.

**Er ging geen geld verloren** — de bodemprijs hield stand, er is nooit onder
verkocht. Het was ruis in de rapportage die actie suggereerde waar geen actie
mogelijk is.

## De fix

Voeg een haalbaarheidscontrole toe vóór het vlaggen:

```python
floor = engine.calculate_minimum_price(engine.bliving_klantprijzen.get(ean, 0))
haalbaar = competitor_price - floor > 0.005

if gap >= 10 and haalbaar and not engine.is_excluded_from_big_steps(ean):
    big_gap_added[ean] = int(gap // 10)
elif ean in big_gap:
    big_gap_cleared.append(ean)
```

Twee dingen die dit meteen goed doet:

- **Nieuwe onhaalbare gevallen worden niet meer gevlagd.**
- **Bestaande onhaalbare gevallen worden opgeruimd**, want ze vallen nu door
  naar de `elif` en belanden in `big_gap_cleared`. Je hebt dus geen apart
  opruimscript nodig.

Gebruik `> 0.005` als marge, om dezelfde reden als bij de bodemcontrole: kleiner
dan een cent, zodat precies-op-de-bodem niet als haalbaar telt.

## Testen vóór uitrol

De beslislogica is los te testen zonder netwerk. Zes gevallen:

| geval | verwacht |
|---|---|
| concurrent ruim boven bodem, gat ≥ €10 | vlaggen |
| concurrent ONDER bodem, gat ≥ €10 | niets |
| idem, maar stond al in `big_gap` | opruimen |
| concurrent net boven bodem, gat ≥ €10 | vlaggen |
| concurrent precies op de bodem | niets |
| klein gat, concurrent boven bodem | niets |

In NL: alle zes correct.

## Uitrol

De cloud-job draait de versie op **GitHub**, niet de lokale. Upload het
gewijzigde `src/sync_buybox.py` los via de Contents API, niet via
`setup_upload.py` (dat overschrijft ook de statusbestanden met lokale stubs).

Draai daarna een sync-ronde en controleer dat het aantal big-gap artikelen
daalt in plaats van dezelfde lijst opnieuw op te leveren.

## Waarom dit past bij de rest

Dit is dezelfde gedachte als achter `no_competitor.json`: niet blijven proberen
wat structureel niet kan. Daar was de blokkade "geen actieve verkoper", hier is
het "concurrent onder onze bodemprijs". In beide gevallen is stoppen met
proberen de juiste uitkomst, niet een gemiste kans.
