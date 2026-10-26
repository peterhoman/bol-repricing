# Instructie voor de BE-chat: cron-tijden naar de wintertijd

Geschreven vanuit de NL-chat op 26 oktober 2026, op verzoek van Peter
("ook voor BE"). Uitvoeren na Peters akkoord in de BE-chat; niets in het
NL-project aanraken.

## Waarom

Sinds zondag 25 oktober is het wintertijd. Channable importeert op vaste
momenten in Amsterdamse tijd; die schuiven vanzelf mee. De cron in de
GitHub-workflow staat in **UTC** en schuift NIET mee. Gevolg: alle
cloud-runs vallen nu een uur vroeger ten opzichte van Channables
importmomenten. Geen verkeerde prijzen, wel trager: Channable pakt
structureel een prijs van een uur eerder.

De taakplanner op de pc (snelstart, optimize, sync) draait in lokale tijd
en schuift vanzelf mee; daar hoeft niets.

## Eerst nakijken of BE dezelfde opzet heeft

Open `.github/workflows/<jullie workflow>.yml` en kijk naar de
`cron:`-regels.

- Staan er Amsterdamse tijden als commentaar achter (zoals bij NL:
  `- cron: '5 6 * * *'    # 08:05 Amsterdam`) en kloppen die met
  UTC+2, dan is het dezelfde opzet en geldt deze instructie.
- Staan er geen labels, reken dan na: de BE-runs horen (net als bij NL)
  kort na Channables importslots te vallen. Weet je niet zeker welke
  Amsterdamse tijden bedoeld zijn, vraag het dan eerst aan Peter.

## De regel - LET OP, makkelijk verkeerd om

Amsterdam = UTC + offset. Zomer: offset 2. Winter: offset 1.

- **Naar de wintertijd (nu): elk UTC-uur +1.** Voorbeeld:
  `'5 6'` (= 08:05 zomertijd) wordt `'5 7'` (= 08:05 wintertijd).
- Naar de zomertijd (zondag 28 maart 2027): elk UTC-uur -1.

In de NL-workflow stond eerder als toelichting "in de herfst een uur
terug": dat was verkeerd om. Als die zin bij BE ook in de workflow of
in de HANDOFF staat, corrigeer hem.

## Hoe NL het deed (26 okt)

1. Alle 24 `cron:`-regels: uur +1, minuut gelijk, Amsterdamse labels
   ongewijzigd.
2. Controle in een script: voor elke regel moet gelden
   `(UTC-uur + 1) % 24 == uur in het label` en de minuut gelijk.
   Bij NL: alle 24 goed.
3. Toelichting bovenaan de `schedule:` bijgewerkt (UTC, regel, en de
   datum van de volgende omzetting: 28 maart 2027).
4. Vastgelegd en gepusht direct ná een geslaagde cloud-run (niet vlak
   voor een cron-moment).
5. Daarna gecontroleerd: er komt een run op een tijd die alleen in het
   NIEUWE rooster staat, en niet op een tijd die alleen in het OUDE stond.

Let op: een push van een workflowbestand kan geweigerd worden als de
gebruikte GitHub-sleutel geen rechten op workflows heeft. Dan kan Peter de
wijziging op de GitHub-website doen (bestand openen, potloodje, aanpassen,
"Commit changes").
