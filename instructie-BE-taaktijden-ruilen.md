# Instructie voor de BE-chat — taaktijden ruilen: BE schuift naar de late sloten

Peter heeft op 18 augustus besloten dat **NL de vroege sloten krijgt** (NL is de
belangrijkste winkel). NL neemt de huidige BE-tijden over; BE verhuist naar de
tijden die NL tot nu toe had.

## Wat er moet gebeuren in BE

Pas in `taken_aanmaken.ps1` de vier tijden aan en laat Peter het script opnieuw
uitvoeren (Register-ScheduledTask -Force overschrijft de bestaande taken):

| taak | was (BE) | wordt (BE) |
|---|---|---|
| morning | 08:15 | **09:00** |
| probe_start | 10:00 | **10:45** |
| probe_check | 11:30 | **12:15** |
| sync | 13:30 | **14:15** |

Alle onderlinge afstanden blijven identiek (probe-check 90 min na start, sync
2 uur na de check), dus geen enkele interne randvoorwaarde verandert.

## VOLGORDE — dit luistert nauw

**BE moet eerst verhuizen, daarna pas NL.** Zolang BE nog op de oude tijden
staat en NL al op de nieuwe, delen beide projecten dezelfde sloten en scrapen
ze tegelijk — de rate-limiting van gisteren (429, ook bij Channable) laat zien
wat dat kost.

Concreet voor vandaag (18 augustus):

1. BE draait vanochtend nog gewoon op de oude tijden — prima.
2. Peter laat het aangepaste BE-script draaien, het maakt niet uit hoe laat;
   taken die vandaag nog moeten komen schuiven dan naar de nieuwe (latere)
   tijd, wat onschuldig is.
3. **Pas daarna** draait Peter het NL-script. Vanaf morgen draait alles
   definitief in de nieuwe verdeling.

Als het BE-script vandaag tussen twee taken in wordt gedraaid: geen probleem.
Een al gestarte taak loopt gewoon af; alleen de eerstvolgende verschuift.

## Kleine aanbeveling die NL ook heeft doorgevoerd

Haal de automatische teststart (`Start-ScheduledTask` aan het eind van het
script) eruit. Die was nuttig bij de eerste installatie, maar bij elke volgende
her-registratie vuurt hij meteen een extra snelstart af — extra scraping op een
willekeurig moment, precies wat we willen vermijden. De taken zijn al bewezen
werkend.

## Wat verandert er verder

Niets. Zelfde wrapper, zelfde logbestanden, zelfde sloten in de scripts
(avondslot 20:30, 30-minutenslot op de check). Alleen de kloktijden.

Voor BE betekent dit concreet: de scherpe ochtendprijzen staan ~45 minuten
later live dan nu. Dat is de prijs van de ruil; Peter heeft die afweging
gemaakt.
