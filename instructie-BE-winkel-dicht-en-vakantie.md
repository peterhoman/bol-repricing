# Instructie voor de BE-chat: winkel dicht, vakantie, en wat het systeem dan moet doen

Geschreven vanuit de NL-chat op 23 september 2026, op verzoek van Peter
("geef dit hele verhaal even door aan BE"). Dit vervangt
`instructie-BE-vakantiepauze.md` van 16 september. Uitvoeren na Peters
akkoord in de BE-chat; niets in het NL-project aanraken.

## De situatie (Peter, 23 september)

- **Beide accounts (NL en BE) staan sinds 23 september UIT.** Reden: een
  bestelling bij B-Living is onderweg en komt 24 september binnen; die
  orders worden nog verstuurd. Met de langste levertijd op bol.com (4-8
  dagen) zou een nieuwe bestelling nu een uiterste leverdatum van 3 oktober
  krijgen, en dat is niet haalbaar: Peter komt 2 oktober rond 23:45 thuis.
  Een gemiste leverbelofte = strike + koopblok kwijt.
- **De winkels gaan waarschijnlijk al in het weekend van 26-27 september
  op afstand weer aan**, met 4-8 dagen. Een bestelling van dat weekend
  krijgt dan een uiterste datum rond 6-8 oktober: B-Living levert maandag
  5 oktober, dinsdag versturen. Tip van NL: zondagavond aanzetten in plaats
  van zaterdag geeft een dag extra speling.
- **Vakantie 25 september t/m 2 oktober. De pc thuis gaat UIT.** Alle
  taakplanner-taken (snelstart, optimize, sync) draaien dan niet; alleen de
  cloud-cron loopt.
- **Geen uploads tijdens de vakantie**, bewust: zo blijven alle bevroren
  prijzen staan. Peter meldt zich als NL en BE weer aan staan.
- Eerste verse upload: zaterdag 3 oktober, als de pc weer aanstaat en de
  winkel al een week aan is.

## Waarom dit het systeem raakt - drie gevaren

1. **De sync terwijl de winkel uit staat.** Ons aanbod staat dan niet op
   bol.com. NL heeft het live gecontroleerd: Tiptopshop verdwenen uit het
   prijsoverzicht, koopblok bij Sebic/Bohemian. De sync ziet dan bij ALLE
   bevroren artikelen "koopblok kwijt" en ontdooit ze in één keer -> reset
   naar vol -> in stapjes naar de bodem. Alle vastgehouden prijzen weg.
2. **Optimize terwijl de winkel uit staat.** Verhoogt prijzen zonder dat er
   een koopblok is; na heropening registreert het geheugen/cooldown dat
   als "verlies na verhoging" en zet verkeerde plafonds.
3. **Een export gemaakt terwijl de winkel uit staat.** Die bevat dan ALLE
   artikelen (ook de bevroren), want niets heeft een koopblok. De cloud
   kijkt niet live en zou bij de dagwissel alles ontdooien. Dus: nooit een
   export maken of uploaden zolang de winkel uit staat, en na het aanzetten
   pas uploaden als bol.com de koopblokken opnieuw heeft toegewezen
   (minstens een dag wachten; direct na aanzetten staat nog van alles ten
   onrechte "zonder koopblok").

## Wat NL gebouwd heeft (23 september) - ter overname

**A. Winkel-dicht-venster in `scheduled_run.py`** (de wrapper die de
taakplanner aanroept), boven `run()`:

```python
from datetime import date as _date
WINKEL_DICHT_VAN = _date(2026, 9, 23)
WINKEL_DICHT_TOT = _date(2026, 9, 25)
WINKEL_DICHT_TAKEN = ("probe_start", "sync")   # BE: de eigen taaknamen van optimize en sync
```

In `run()`, direct na `script, args = TASKS[task_name]` en `started = datetime.now()`:

```python
    if task_name in WINKEL_DICHT_TAKEN and WINKEL_DICHT_VAN <= started.date() <= WINKEL_DICHT_TOT:
        regel = (f"[WINKEL DICHT] {task_name} overgeslagen: winkel uit van {WINKEL_DICHT_VAN:%d-%m} t/m "
                 f"{WINKEL_DICHT_TOT:%d-%m} - sync zou alle bevroren artikelen ontdooien, optimize zou "
                 f"verhogen zonder koopblok. Bevroren prijzen blijven staan.")
        entry = {"task": task_name, "started": started.isoformat(timespec="seconds"), "duration_s": 0,
                 "exit_code": 0, "result": "ok", "summary": [regel]}
        LOG_DIR.mkdir(exist_ok=True)
        with open(LOG_DIR / f"automation-{started:%Y-%m}.log", "a", encoding="utf-8") as fh:
            fh.write(f"{chr(10)}{'='*70}{chr(10)}{entry['started']}  {task_name}  exit=0  0s{chr(10)}{'='*70}{chr(10)}{regel}{chr(10)}")
        push_log_entry(entry)
        print(regel)
        return 0
```

Plus `"[WINKEL DICHT]"` in de prefix-lijst van de wrapper. De snelstart
draait door: die verlaagt alleen en bevriest niets. Test: `datetime.now`
vervangen door een vaste datum en `subprocess.run` door iets dat een fout
gooit; verwacht op 23-09 en 25-09 "overgeslagen", op 26-09 "gestart". Bij
NL werkte het meteen: de taak van 23-09 10:00 staat als
`[WINKEL DICHT] probe_start overgeslagen` in `automation_log.json`.

Het venster loopt t/m 25 september omdat de pc daarna toch uit is. Gaat de
pc toch aan terwijl de winkel nog uit staat: einddatum verlengen.

**B. Vakantiepauze in optimize** (uit de instructie van 16 sept, ongewijzigd):
`VAKANTIE_VAN = 25 sept`, `VAKANTIE_TOT = 2 okt`; in het venster print
optimize `[VAKANTIE] ...` en stopt vóór het laden van engine, geheugen en
frozen.json. Bij NL staat dit sinds 16 sept op GitHub.

## Wat er bij de cloud NIET verandert

De cloud-cron draait gewoon door op de laatste geüploade lijst (NL: die van
23 sept 07:55, gemaakt vóór het uitzetten, 0 bevroren erin). Bevroren
prijzen blijven staan, de lijst cyclet dagelijks (reset, EUR0,50-stappen).
Mislukte runs (B-Living 's avonds, GitHub-hik) zijn onschuldig: de volgende
run haalt het in. Peter krijgt de mails, kan er niets mee, hoeft ook niets.

## Bij terugkomst (3 oktober)

Pc aan. Eerste verse upload 's ochtends (winkel is dan al een week aan).
Gemiste taken halen zichzelf mogelijk in (-StartWhenAvailable); onschuldig.
**De eerste sync geeft waarschijnlijk tientallen ontdooiingen: dat is
opruimen van een week zonder sync, geen verlies van die dag.** Daarna
normaal.

## Vragen aan Peter in de BE-chat

1. Zijn de BE-taaknamen voor optimize en sync in `WINKEL_DICHT_TAKEN` goed
   ingevuld?
2. Staat de BE-winkel ook uit t/m 25 sept, en gaat die ook dit weekend
   weer aan? (NL: ja en ja.)
