# Instructie voor de BE-chat: feed-download ook opnieuw proberen bij een 503

Geschreven vanuit de NL-chat op 21 oktober 2026, op verzoek van Peter
("geef het ook even door aan BE, kan die het ook inbouwen"). Uitvoeren na
Peters akkoord in de BE-chat; niets in het NL-project aanraken.

## Aanleiding

21 oktober 14:49 kregen NL en BE op hetzelfde moment een "Run failed". De
B-Living-server was bereikbaar, maar antwoordde met **HTTP 503** (server
overbelast of onderhoud). Het logboek:

```
Error: 503
[ERROR] No klantprijzen loaded from B-Living feed
```

De retry in `_get_with_retries` (7 pogingen, verdubbelende wachttijd)
grijpt alleen bij een VERBINDINGSFOUT (exception). Een 503 komt als een
gewone response terug, de aanroeper ziet `status_code != 200` en de run
stopt direct - zonder ook maar één keer te wachten. Terwijl zo'n 503
meestal binnen een minuut voorbij is. Het is dus hetzelfde soort storing
als de B-Living-uitval van september, alleen met een ander antwoord van de
server.

## De wijziging (NL, `src/phase2_repricing.py`, `_get_with_retries`)

Alleen de lus is anders; handtekening, aanroepers en het gedrag bij een
echte verbindingsfout blijven gelijk.

```python
        RETRY_STATUSES = {429, 500, 502, 503, 504}
        last_exception = None
        last_response = None
        wait = backoff
        for attempt in range(1, retries + 1):
            try:
                response = requests.get(url, timeout=timeout, headers=self._fresh_headers(url))
                if response.status_code not in RETRY_STATUSES:
                    return response
                last_response = response
                reden = f"HTTP {response.status_code}"
            except requests.exceptions.RequestException as e:
                last_exception = e
                reden = str(e)
            if attempt < retries:
                print(f"   Attempt {attempt}/{retries} failed ({reden}), retrying in {wait}s...")
                time.sleep(wait)
                wait *= 2
        if last_response is not None:
            return last_response      # aanroeper ziet status != 200 en stopt netjes
        raise last_exception
```

Wat het doet:
- 5xx en 429: opnieuw proberen met dezelfde wachttijden als bij een
  verbindingsfout (10/20/40/80/160/320 s, max ~10,5 min bij 7 pogingen).
- Andere statuscodes (200, maar ook 404 enz.) worden direct teruggegeven:
  een 404 is geen storing.
- Blijft het 7 keer 5xx, dan krijgt de aanroeper de laatste response en
  stopt de run precies zoals nu ("No klantprijzen loaded"), alleen later.
- Een verbindingsfout gevolgd door een 503 gevolgd door 200 werkt ook.

Let op bij BE: `_fresh_headers` is NL-specifiek (Contents-API-headers);
gebruik wat er bij BE in de `requests.get` staat. En check of BE's
`retries` nog op 5 of al op 7 staat; de wijziging werkt met beide.

## Test (zonder netwerk)

`time.sleep` vervangen door niets, `requests.get` door een nep-functie die
een vaste reeks antwoorden geeft. Verwacht:

| reeks | eindresultaat |
|---|---|
| 503, 503, 200 | 200 (na 2 keer wachten) |
| 7x 503 | 503 (aanroeper stopt netjes) |
| 404, 200 | 404 direct, geen retry |
| verbindingsfout, 503, 200 | 200 |

Bij NL: alle vier goed.

## Timing van de push

`phase2_repricing.py` draait in de cloud, dus de push naar GitHub moet.
Doe dat direct ná een geslaagde cloud-run (niet in de minuten rond een
cron-moment), anders kan de run die net zijn XML wegschrijft een 409 geven.
Eén onschuldige mail, maar het hoeft niet.
