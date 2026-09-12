# Voorstel voor de BE-chat (Dreamhouse&Garden) — bevroren prijs weer omhoog als de concurrent weg is

Dit is een **voorstel**, geen uitgevoerde instructie. In NL is het probleem gemeten
en het ontwerp uitgedacht, maar nog niet gebouwd. Peter wil dat BE meekijkt en
hetzelfde doet, zodat beide projecten gelijk blijven lopen.

Meet het eerst in BE met de eigen cijfers — de aantallen hieronder zijn NL.

## Wat Peter opmerkte

Zes identieke artikelen (Strik Deurstopper fluweel, zelfde inkoopprijs €6,85)
stonden op bol.com op verschillende prijzen: vier op €24,44 en twee op €21,92.
Bij alle zes hadden wij het koopblok en was er geen concurrent te zien.

De twee lage stonden in `frozen.json`. Die twee zijn tijdens een prijzenstrijd
gezakt naar €21,92, hebben daar het koopblok gepakt en zijn bevroren. De vier
andere zijn nooit bevroren geraakt en volgen dus elke ochtend de normale route,
die op de volle prijs begint.

Peters punt: **tegen de bodemprijs verkopen doe je uit nood, daar valt niets te
verdienen.** Blijft die prijs staan terwijl de concurrent verdwenen is, dan geef
je marge weg voor niets.

## Het gat in de logica

Er zitten al twee correcties op een bevroren prijs, maar die kijken allebei naar
de INKOOPPRIJS, niet naar de concurrentie:

| bestaande correctie | wanneer |
|---|---|
| `clamp_frozen_to_floor` | inkoop gestegen, we zakken onder de bodem → omhoog |
| `clamp_frozen_to_normal_price` | inkoop gedaald, we staan boven de volle prijs → omlaag |

Verdwijnt de concurrent, dan gebeurt er niets. Een bevroren prijs blijft staan
waar hij stond, voor altijd.

## Gemeten in NL (17 augustus)

| meting | uitkomst |
|---|---|
| bevroren artikelen | 189 |
| daarvan onder hun volle prijs | 176 |
| daarvan: wij hebben het koopblok, niemand biedt onder ons | **174** |
| concurrent zit onder onze volle prijs (niet verhogen) | 1 |
| check mislukt | 1 |

Op te halen: gemiddeld **€9,30 per verkocht stuk**, samen **€1.617,65** over alle
174. Grootste post €51,74 (van €434,34 naar €486,08).

## Wat je NIET kunt meten — lees dit vóór je begint

Als wij het koopblok hebben, toont de productpagina **onze eigen prijs**. Je ziet
dus niet of er een concurrent net achter ons zit. Die €1.617 is een
**bovengrens, geen zekerheid**.

Belangrijker nog, en dit is het echte tegenargument: in NL is eerder gemeten dat
bij 24 artikelen wij goedkoper waren en het koopblok tóch niet kregen, omdat de
concurrent binnen 1 dag levert en wij 3-5 werkdagen. Bol.com weegt levertijd mee.

Dat betekent dat op de artikelen die we WEL winnen, ons prijsvoordeel misschien
precies dat levertijdnadeel compenseert. De marge die er "voor niets" lijkt te
liggen, kan in werkelijkheid het koopblok kopen. Verhogen kan dus koopblokken
kosten — en hoeveel is niet vooraf te meten.

## Waarom het toch verantwoord is

Het risico is beperkt en tijdelijk, om één reden: **de ochtend-snelstart
repareert het de volgende dag.** Verliezen we een koopblok doordat we te hoog
gingen, dan matcht `match_prices.py` het artikel de volgende ochtend meteen weer
net onder de concurrent. Geen dagen grinden, één ronde.

Elk artikel vindt zo zijn eigen plafond. Er hoeft niets vooraf geraden te worden.

## Het voorstel

Een derde correctie, alleen in de scripts die LIVE checken (ochtend-snelstart
en/of sync). Niet in de cloud-run — die kan geen koopblok-status opvragen.

Gedrag per bevroren artikel:

1. hebben wij het koopblok, en staat onze prijs onder de volle prijs?
2. zo ja: **€0,50 erbij**, nooit boven de volle prijs
3. koopblok kwijt bij een volgende check: laat het artikel terugvallen in de
   normale route (uit `frozen`), dan zakt het weer zoals altijd
4. zie je een concurrent ónder onze volle prijs: niet verhogen

Stapgrootte €0,50 — hetzelfde ritme als omlaag, dus voorspelbaar. Bij €9,30
gemiddelde ruimte duurt het een aantal dagen voor een artikel bovenaan staat, en
dat is precies de bedoeling: langzaam aftasten in plaats van springen.

## Waarom niet eerst een proef op een kleine groep

Overwogen, maar niet nodig: de €0,50-stap ís al de proef. Elk artikel test zijn
eigen plafond en de schade is per artikel één stap. Een aparte proefgroep levert
dezelfde informatie op, alleen langzamer.

## Testen vóór uitrol

1. **Droogloop** op de echte `frozen.json`: hoeveel artikelen zouden een stap
   omhoog krijgen, en komt er geen enkele boven zijn volle prijs uit?
2. **Plafond**: een artikel dat al op de volle prijs staat mag geen stap krijgen.
3. **Bodem blijft heilig**: de bestaande bodemcontrole en de bandcontrole
   (`[bodemprijs, volle prijs]`) moeten daarna nog steeds 0 overtredingen geven.
4. **Terugval**: een artikel dat het koopblok verliest verdwijnt uit `frozen` en
   volgt weer de normale route.

## Uitrol

De cloud-job draait de versie op **GitHub**, niet de lokale. Upload het
gewijzigde bestand los via de Contents API, niet via `setup_upload.py`.

Volg na uitrol een paar dagen hoeveel koopblokken er wegvallen. Blijft dat laag,
dan is de winst echt. Loopt het op, dan is het levertijdnadeel dominanter dan
gedacht en is terugdraaien één regel.
