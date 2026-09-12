# Instructie voor de BE-chat (Dreamhouse&Garden) — bevindingen uit de NL-uitvoering

Geschreven door de **NL-chat** (Tiptopshop) op 25 juli 2026, nadat de
`no_competitor.json`-fix uit `instructie-voor-NL-chat.md` daar is ingebouwd
en gedeployed.

Dit document staat bewust in de **NL-projectmap**. Peter geeft het pad door
aan de BE-chat; er wordt niet in elkaars project gewerkt. Zelfde patroon als
andersom.

## Stand van zaken NL

De fix is één-op-één overgenomen en werkt. Resultaat:

- `no_competitor.json` gevuld met **7 EAN's** (BE: 49).
- Droogloop: 7/7 in `adjustments`, 7 op verlaagde prijs, 0 audit-issues.
- Live cloud-run daarna: `No-competitor ... EANs: 7`, audit schoon.
- Alleen `src/phase2_repricing.py` + `no_competitor.json` los geüpload via
  de Contents API — de waarschuwing over `setup_upload.py` is opgevolgd.

Beide projecten werken nu identiek. Hieronder drie dingen die tijdens de
NL-uitvoering naar boven kwamen en die in BE waarschijnlijk óók spelen.

---

## 1. Er is een TWEEDE foutsoort die de fix niet dekt

Van de 9 mislukte checks in NL hadden er maar **7** de fout
`"no product url in search results"`. De andere 2 gaven:

```
"ean not found in JSON-LD"
```

Andere oorzaak: de productpagina bestaat wél en resolvet prima, maar onze
EAN staat niet in de JSON-LD van die pagina. Nagekeken in de browser voor
EAN 8717266317873 (Abbey raamfolie): de pagina komt netjes op, maar toont
`gtin13: 6150541860831`. Bol.com heeft de listing dus samengevoegd onder een
andere GTIN.

**Wat te doen in BE:** tel de foutredenen apart uit. Als er ook
`"ean not found in JSON-LD"`-gevallen tussen die 49 zitten, horen die
**niet** in `no_competitor.json` — die zouden daar een verkeerde aanname
vastleggen (er ís een verkoper, we vinden onze EAN alleen niet terug).
Zet ze op een eigen lijstje en meld het aantal aan Peter; een oplossing
hiervoor bestaat nog nergens.

Dit is ook precies waarom de instructie zo strikt was over "alleen deze
exacte foutmelding" — die strengheid houdt de twee categorieën uit elkaar.

## 2. Meet de speling tussen prijs en bodemprijs — dit is de belangrijkste check

De fix lost het *terugspringen* op. Hij lost niet op dat een artikel te duur
blijft. In NL bleek **3 van de 7 al ÓP de bodemprijs te staan**:

| EAN | prijs na de run | bodemprijs | speling |
|---|---|---|---|
| 8716522092585 | €16,69 | €16,68 | op de bodem |
| 8717266373060 | €23,36 | €23,37 | op de bodem |
| 8717266051630 | €17,46 | €17,46 | op de bodem |
| 8716522085068 | €69,15 | €62,40 | €6,75 |
| 8717774825877 | €193,66 | €160,97 | €32,69 |
| 8717774825792 | €239,48 | €197,24 | €42,24 |
| 8717774821015 | €239,48 | €197,24 | €42,24 |

Voor die eerste drie geldt: ze zakken niet verder, want daaronder draaien we
verlies. Blijft bol.com ze op "Niet te koop" zetten, dan komen ze er nooit
uit en is er geen software-oplossing meer — het is dan een marge-beslissing
voor Peter (inkoopprijs omlaag, of het artikel loslaten).

**Advies:** draai bij die 49 EAN's dezelfde vergelijking en meld Peter
hoeveel ervan al op of vlak boven de bodem zitten. Bij 49 stuks is dat
waarschijnlijk een fors deel. Dat maakt in één oogopslag zichtbaar welke
artikelen kansloos zijn — dat scheelt maanden wachten op iets dat niet gaat
gebeuren, en het is precies het soort proactieve verbetersignaal dat Peter
wil zien in plaats van alleen cijfers.

De vergelijking is simpel (geen live-checks nodig, dus veilig vanuit elke
omgeving):

```python
fresh = engine.bliving_klantprijzen[ean]
huidige_prijs = engine.calculate_normal_price(adjustments[ean])
bodem         = engine.calculate_minimum_price(fresh)
speling       = round(huidige_prijs - bodem, 2)
```

Let op het onderscheid dat op 23 juli al eens misging: `calculate_minimum_price`
hoort op de **echte** B-Living-klantprijs (`bliving_klantprijzen`), niet op de
kunstmatige klantprijs die het script zelf in de XML schrijft.

## 3. `sync_buybox.py` — de bewuste keuze klopt, met één randgeval

De instructie liet dit script bewust ongemoeid, met als argument dat de
ochtendrun sowieso alle kandidaten checkt. Dat klopt — zolang de ochtendrun
ook echt elke dag draait.

Randgeval: draait `sync_buybox.py` op een dag dat `match_prices.py` wordt
overgeslagen, dan loopt `no_competitor.json` die dag achter (geen
toevoegingen, en belangrijker: geen verwijderingen zodra er weer een
verkoper opduikt). Niet dramatisch, wel goed om te weten voordat iemand zich
afvraagt waarom de lijst stilstaat. Wil je het dichttimmeren, dan is dezelfde
add/discard-logica nodig in beide check-loops van dat script.

---

## Klein detail bij het narekenen

Bij het uitzoeken hielp het enorm om de prijsgeschiedenis van één EAN uit de
git-historie van `repricing_current.xml` te trekken — dat maakte het
terugspringen in één blik zichtbaar:

```
20 juli: klantprijs 6.40    22 juli: 7.67    23 juli: 6.40
24 juli 10:27: 6.83         24 juli 20:41: 6.40
```

Zonder die reeks blijft het "hij zakt toch wel?" — mét die reeks is het
meteen duidelijk dat hij elke ochtend terugveert. Bruikbaar bij elke
volgende "waarom beweegt dit artikel niet"-vraag.
