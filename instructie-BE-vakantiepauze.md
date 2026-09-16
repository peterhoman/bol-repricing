# Instructie voor de BE-chat: vakantiepauze voor de verhogingen (25 sept t/m 2 okt)

Geschreven vanuit de NL-chat op 16 september 2026, op verzoek van Peter
("deze instructie ook maken voor de BE chat"). Uitvoeren na Peters akkoord
in de BE-chat; niets in het NL-project aanraken.

## Wat Peter heeft gezegd

- Vakantie van **vrijdag 25 september t/m vrijdag 2 oktober**. Op de 25e
  gaat er niets meer de deur uit.
- In die periode staat een **langere levertijd** ingesteld; de eerste dagen
  komen er daardoor heel weinig orders.
- **De pc thuis gaat uit.** De taakplanner-taken (snelstart, optimize, sync)
  draaien dan niet; alleen de cloud-cron loopt door.
- Vanaf het vakantieadres zet Peter af en toe een nieuw bestand op GitHub
  (via de website, zelfde bestandsnaam).

## Waarom de verhogingen pauzeren

Met een langere levertijd staan we bij bol.com zwakker. Verhogingen tegen
een concurrent (tot vlak onder zijn prijs, of tegen een tragere concurrent)
werken nu omdat het prijsverschil ons levertijdnadeel compenseert. Wordt dat
nadeel groter, dan gaan die koopblokken waarschijnlijk verloren - en erger:
een geheugen/cooldown-mechanisme zou die verliezen aan de PRIJS toeschrijven
en er plafonds van maken die na de vakantie te laag zijn. Een week zonder
verhogingen kost in de stabiele stand weinig (NL: EUR15-30 per cyclus per
dag) en voorkomt een verkeerd beeld waar je daarna weken last van hebt.

Verlagen, bevriezen en de sync lopen gewoon door: die geven geen marge weg
die er niet was, en de dagroute herstelt zichzelf na de vakantie.

## Wat NL gebouwd heeft (16 sept)

In `src/probe_recovery.py`, bovenaan bij de verkoperlijsten:

```python
VAKANTIE_VAN = date(2026, 9, 25)
VAKANTIE_TOT = date(2026, 10, 2)
```

En als EERSTE regels van `phase_optimize`, vóór het laden van de engine, het
geheugen of frozen.json (zodat er ook geen verliezen geregistreerd worden):

```python
    vandaag = date.today()
    if VAKANTIE_VAN <= vandaag <= VAKANTIE_TOT:
        print(f"[VAKANTIE] {vandaag:%d-%m}: verhogingen gepauzeerd van {VAKANTIE_VAN:%d-%m} t/m "
              f"{VAKANTIE_TOT:%d-%m} (langere levertijd). Niets verhoogd, geheugen niet aangeraakt; "
              f"verlagen, bevriezen en sync lopen door.")
        return
```

Plus `"[VAKANTIE]"` toegevoegd aan de prefix-lijst in `scheduled_run.py`,
zodat de regel in `automation_log.json` terechtkomt en een chat op afstand
ziet dat de pauze actief is.

Het venster is inclusief: 25 sept t/m 2 okt pauzeren, 24 sept en 3 okt
draaien normaal. Na 2 oktober gaat het vanzelf weer aan; er hoeft niets
teruggedraaid te worden.

## Test (zonder netwerk)

`date.today()` vervangen door een vaste datum en `RepricingEngine` door een
klasse die een fout gooit zodra hij geladen wordt. Verwacht: op 24-09 en
03-10 wordt de engine geladen (normaal gedrag), op 25-09, 28-09 en 02-10
komt de `[VAKANTIE]`-regel en wordt de engine NIET geladen. NL: alle vijf
goed.

## Wat "pc gaat uit" betekent - ook voor BE

- Vanaf het moment dat de pc uit is, draaien snelstart, optimize en sync
  niet. De pauze in optimize is dan vanzelf van kracht; het datumvenster
  vangt alleen de randdagen (de 25e als de pc nog aanstaat, en de eerste
  dagen na terugkomst als de levertijd nog lang staat).
- De cloud-cron draait door: dagelijkse reset, EUR0,50-stappen omlaag,
  bevroren prijzen vasthouden, bodem- en driftklem. Zonder sync worden
  bevroren artikelen die het koopblok verliezen NIET ontdooid - ze blijven
  een week op hun prijs staan. Geen schade; de eerste sync na terugkomst
  ruimt het op.
- Bij terugkomst: pc aanzetten. Gemiste taken halen zichzelf mogelijk in
  (`-StartWhenAvailable`); de probe-start heeft een 20:30-slot, optimize
  niet. Een inhaal-optimize 's avonds is onschuldig (Channable importeert
  's nachts niet, de prijs gaat 's ochtends live). Wel: de eerste sync na
  terugkomst kan tientallen ontdooiingen geven - dat is opruimen, geen
  verlies van die dag.
- Bestand op GitHub vóór 08:10 (werkdag) / 09:40 (weekend) = de snelstart
  draait erop, maar alleen als de pc aanstaat. Anders pakt de cloud het bij
  de eerstvolgende run.

## Vragen aan Peter in de BE-chat

1. Zelfde venster (25 sept t/m 2 okt)? Bij BE staan de taken op
   09:00/10:45/12:15/14:15, dat maakt voor het venster niet uit.
2. Staat de BE-levertijd ook langer, en gaat de pc daar uit? (Bij NL:
   ja en ja.)
