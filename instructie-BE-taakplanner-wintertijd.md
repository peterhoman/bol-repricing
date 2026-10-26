# Instructie voor de BE-chat: taakplanner-taken lopen sinds de wintertijd een uur te vroeg

Geschreven vanuit de NL-chat op 26 oktober 2026 (Peter: "ook voor BE").
Hoort bij `instructie-BE-wintertijd.md` (de cloud-cron). Uitvoeren na
Peters akkoord in de BE-chat; niets in het NL-project aanraken.

## Wat er aan de hand is

Sinds de wintertijd (zondag 25 oktober) draaien de DAGELIJKSE
taakplanner-taken een uur te vroeg. Bij NL gemeten in het lokale log:

| NL-taak | hoort | sinds 25 okt |
|---|---|---|
| ochtend-snelstart (wekelijkse trigger) | 08:15 / weekend 09:45 | goed |
| probe_start / optimize (dagelijks) | 10:00 | 09:00 |
| probe_check (dagelijks) | 11:30 | 10:30 |
| sync (dagelijks) | 13:30 | 12:30 |

Bij BE vermoedelijk hetzelfde: de BE-triggers staan (alleen gelezen, niets
veranderd) op 08:00+01:00, 09:45+01:00, 11:15+01:00 en 13:15+01:00, dus
een uur vóór de bedoelde 09:00/10:45/12:15/14:15. Check in het BE-log op
welke tijden de taken sinds 25 oktober echt draaiden.

**Gevolg:** NL-optimize (nu 09:00) en BE-snelstart (09:00) scrapen tegelijk
bij bol.com, en in het weekend vallen NL-snelstart (09:45) en
BE-optimize (nu 09:45) samen. Twee scrapes tegelijk = rate-limiting (meer
mislukte checks). Geen verkeerde prijzen.

## Oorzaak

`New-ScheduledTaskTrigger -At "10:00"` slaat de starttijd op MET
tijdzone, op deze pc zelfs als wereldtijd: getest levert hij nu
`2026-10-26T09:00:00Z`. Windows houdt zo'n trigger op hetzelfde
wereldtijd-moment vast en schuift dus niet mee met zomer/wintertijd.
(De wekelijkse snelstart-triggers liepen bij NL wél goed; de dagelijkse
niet. Hoe dan ook: overal de tijdzone eraf halen.)

## Oplossing (NL, `taken_aanmaken.ps1`)

Na het maken van de trigger(s), vóór `Register-ScheduledTask`:

```powershell
    foreach ($tr in $trigger) {
        $tr.StartBoundary = ([datetime]$tr.StartBoundary).ToString("yyyy-MM-dd'T'HH:mm:ss")
    }
```

(`$trigger` moet dan een lijst zijn: bij NL `@(New-ScheduledTaskTrigger -Daily -At $t.Tijd)`.)
Getest: zonder dit `2026-10-26T09:00:00Z`, met dit `2026-10-26T10:00:00`.
Een starttijd zonder tijdzone is voor Windows "gewone kloktijd" en volgt
zomer- en wintertijd vanzelf.

En de controle aan het eind van het script laat nu per taak de starttijd
zien, met de uitleg: goed = géén `+01:00`, `+02:00` of `Z` erachter.

## Uitvoeren

Peter draait het script zelf (Claude kan geen taken registreren):
rechtsklik op `taken_aanmaken.ps1` > "Uitvoeren met PowerShell". De
controle onderaan moet tijden zonder tijdzone tonen. Daarna in het log van
de volgende dag nagaan dat de taken weer op de bedoelde tijden draaien.

Vanaf nu hoeft er bij zomer/wintertijd niets meer aan de taakplanner te
gebeuren (wel aan de cloud-cron, zie `instructie-BE-wintertijd.md`).
