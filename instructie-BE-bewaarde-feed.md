# Instructie voor de BE-chat: terugvallen op de laatst bewaarde B-Living-feed

Geschreven vanuit de NL-chat op 21 oktober 2026, 16:30, op verzoek van Peter
("ja bouw maar, ook aan BE doorgeven"). Uitvoeren na Peters akkoord in de
BE-chat; niets in het NL-project aanraken. Hoort bij
`instructie-BE-retry-op-503.md` van dezelfde dag.

## Aanleiding

21 oktober ~14:45: B-Living offline ("Website temporarily unavailable -
urgent maintenance"), samen met een groot deel van Nederland vanwege een
PHP-lek (NU.nl). Hun feed geeft HTTP 503, ook vanaf Peters pc. Gevolg:
elke cloud-run mislukt met "No klantprijzen loaded" (een mail per run), en
ook de lokale taken stoppen, want alles begint met het laden van de feed.
Het hele systeem staat stil zolang B-Living stil staat; prijzen blijven
op de laatste goede versie (geen schade, wel stilstand).

Kernargument waarom een bewaarde feed hier veilig is: zolang B-Living's
site plat ligt, kan hun inkoopprijs ook niet wijzigen. De kopie is dan net
zo goed als de echte feed.

## Wat NL gebouwd heeft (`src/phase2_repricing.py`, bij `load_bliving_feed`)

Gedrag:
1. **Lukt het ophalen** (HTTP 200): feed parsen zoals altijd, en daarna
   `_save_bliving_cache()`: schrijf `bliving_cache.json` naar GitHub via
   `upload_json_to_github`, maar hooguit elke `CACHE_MIN_UREN` (6) uur om
   commits te sparen. Inhoud: `{"bewaard": "<ISO-tijd>", "aantal": n,
   "klantprijzen": {...}, "titels": {...}}`.
2. **Lukt het niet** (status != 200 ná de retries, of een exception):
   `_load_bliving_cache(reden)`: lees `bliving_cache.json` via de
   Contents-API (vers, met token). Is er een kopie en is die jonger dan
   `CACHE_MAX_UREN` (72), dan die gebruiken en loggen:
   `[FEED] B-Living onbereikbaar (HTTP 503) - bewaarde feed van 21-10 13:38 gebruikt (3 uur oud, 5423 klantprijzen)`.
   Geen kopie, of ouder dan 72 uur: stoppen zoals voorheen.

De drie helpers (`_bliving_cache_url`, `_read_bliving_cache`,
`_save_bliving_cache`, `_load_bliving_cache`) staan direct onder
`load_bliving_feed`; ze gebruiken `os.getenv("GITHUB_REPO")`,
`GITHUB_TOKEN`, `_fresh_headers` (BE: eigen equivalent) en het bestaande
`upload_json_to_github(data, filename)`. Imports nodig: `json`,
`datetime`, `timedelta`.

De code zelf staat in NL's `phase2_repricing.py` op GitHub
(`peterhoman/bol-repricing`, commit van 21 okt "Bewaarde B-Living-feed als
terugval"); de BE-chat kan hem daar lezen en overnemen, aangepast aan de
BE-bestandsnamen.

## Test (zonder netwerk) - zes gevallen, bij NL alle zes goed

| feed | bewaarde kopie | verwacht |
|---|---|---|
| 200 | geen | geladen; kopie bewaard |
| 200 | 5 uur oud | geladen; kopie NIET ververst (< 6 uur) |
| 200 | 7 uur oud | geladen; kopie ververst |
| 503 | 5 uur oud | kopie gebruikt, geladen |
| 503 | 100 uur oud | stoppen |
| 503 | geen | stoppen |

`requests.get` vervangen door een nepfunctie (GitHub-URL -> de kopie of
404; feed-URL -> 200 met een mini-XML of 503), `time.sleep` uitgeschakeld,
`upload_json_to_github` vervangen door iets dat alleen vastlegt dat er
geschreven is.

## Belangrijk: de eerste kopie ontstaat pas bij de eerste geslaagde run

Er is nu nog geen kopie. Die wordt geschreven zodra B-Living weer
bereikbaar is en één run slaagt. De terugval helpt dus niet voor DEZE
storing, wel voor elke volgende. Niets handmatig vullen: de echte
kostbasis staat nergens anders (de klantprijzen in frozen.json en de XML
zijn omgerekende doelprijzen, geen inkoopprijzen).

## Timing van de push

Zolang B-Living plat ligt, schrijven de mislukte runs niets, dus een push
kan nu zonder 409-risico. Daarna weer: direct ná een geslaagde run.
