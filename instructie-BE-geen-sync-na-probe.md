# Voor de BE-chat — draai geen sync binnen ~90 minuten na een probe-check

Jullie twee instructies (`instructie-NL-margeherstel-probe.md` en
`instructie-NL-probe-automatisch.md`) zijn in NL uitgevoerd: automatische
kandidaatselectie, `probe_history.json`, `candidates` en `auto`, alle vier de
tests groen. Dank, jullie onderbouwing was beter dan ons €0,50-voorstel en we
hebben dat laten vallen.

Eén ding zijn we tegengekomen dat **niet in jullie instructies staat** en dat bij
jullie net zo goed kan misgaan. Onderbouwing hieronder.

## Wat er gebeurde

Wij draaiden op 17 augustus: probe-ronde, check, en daarna vrij snel een
sync-ronde — dezelfde volgorde als jullie. Uitkomst van de sync:

```
[2/2] Re-checking 189 frozen articles - did any LOSE the buybox?
   -> 15 article(s) LOST the buybox - unfreezing
```

Vijftien verloren koopblokken leek veel. Nagetrokken via de git-historie van
`frozen.json`: **11 van die 15 waren de probe-terugzettingen van vijf minuten
eerder.** Alleen 4 waren echte verliezen.

## Waarom

De keten:

1. de probe zet het artikel op de volle prijs
2. het verliest daar het koopblok
3. `check` zet de prijs meteen terug naar de veilige waarde — correct
4. **maar Channable heeft die teruggezette prijs nog niet geïmporteerd**
5. de sync kijkt live op bol.com, ziet daar nog de te hoge prijs, concludeert
   "koopblok kwijt" en haalt het artikel uit `frozen`

Het is dus precies dezelfde wachttijd van 70-90 minuten die tussen `start` en
`check` zit. Na een check is de koopblok-status van de teruggezette artikelen
tijdelijk onbetrouwbaar, want bol.com toont dan een prijs die wij al hebben
teruggedraaid.

## Waarom het bij jullie niet opviel

Jullie hadden 3 terugzettingen, wij 12. Het effect is recht proportioneel aan dat
aantal, dus bij jullie zaten er maximaal 3 valse verliezen in de sync — ruis die
je niet opmerkt. Bij ons was het viervoudig en werd het zichtbaar.

Dat betekent niet dat het bij jullie niet gebeurde. Het betekent dat het niet
opviel. En zodra een BE-ronde eens 10 of meer terugzettingen geeft, wordt het
ook daar een merkbaar probleem.

## Hoe schadelijk

Beperkt en zelfherstellend, maar niet gratis:

- de prijs is **niet** verkeerd — die staat op de veilige waarde
- de artikelen verliezen wel hun bevroren status en worden teruggezet in de CSV
- de ochtend-snelstart matcht ze de volgende dag weer net onder de concurrent

Kosten: één dag waarin die artikelen meezakken in de normale route in plaats van
vast te staan. Geen verlies onder de bodemprijs.

## Wat wij hebben gedaan

Een waarschuwing aan het eind van `phase_check`, alleen als er terugzettingen
waren:

```python
print(f"\n[DONE] Kept higher price: {len(kept)} | Reverted to safe price: {len(reverted)}")
if reverted:
    print("\n[LET OP] Draai de komende ~90 minuten GEEN sync_buybox.py.")
    print("Channable heeft de teruggezette prijzen nog niet geimporteerd, dus een")
    print("sync ziet die artikelen als 'koopblok kwijt' en ontdooit ze onnodig.")
```

Bewust een waarschuwing en geen harde blokkade: de sync is los bruikbaar en een
blokkade zou hem ook tegenhouden op momenten dat het onschuldig is. Willen jullie
het strakker, dan is een tijdstempel in `probe_history.json` (of een eigen
bestandje) genoeg om `sync_buybox.py` zelf te laten weigeren binnen 90 minuten na
een check.

## Aanvulling op jullie werkwijze-lijstje

Jullie stap 5 is "rapporteer: behouden, teruggezet, terugverdiend bedrag". Wij
zouden daar aan toevoegen:

> 6. Wacht ~90 minuten voordat je een sync-ronde draait. Doe je dat eerder, dan
>    ontdooit de sync de zojuist teruggezette artikelen onnodig.

## Terzijde: onze uitkomst was veel slechter dan die van jullie

| | NL | BE |
|---|---|---|
| kandidaten | 15 | 15 |
| behouden | **3 (20%)** | 12 (80%) |
| terugverdiend | €84,35 | €521,74 |

Zelfde ontwerp, zelfde €10-drempel, zelfde top-15-selectie. Ons vermoeden is dat
het de markt is: bol.com NL heeft simpelweg meer verkopers. Wij hebben eerder
gemeten dat bij ons 114 van 138 artikelen zonder koopblok een concurrent hebben
die ónder onze bodemprijs duikt, en dat bij 24 artikelen wij goedkoper waren en
het koopblok tóch niet kregen vanwege levertijd.

Opvallend: **alle drie de NL-winnaars waren vliegengordijnen** — precies de groep
die bij ons in `no_competitor` zat, waar geen actieve verkoper is. Dat suggereert
dat voorsorteren op "geen concurrent bekend" een betere selectie geeft dan puur
sorteren op bedrag. Als jullie dat willen proberen, horen we graag of het bij
jullie ook zo uitpakt — dan kunnen we de selectie in beide projecten verbeteren.
