#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Margin-recovery probe for frozen (buybox-won) articles.

Problem: once an article wins the buybox at a reduced price, the main tool
holds it there forever - even if the competitor later raises their price or
goes out of stock, we'd never know and never claim back that margin.

This script tests recovery in two phases, run separately (because Channable
only re-imports our feed once per hour, so we can't verify instantly):

  python src/probe_recovery.py start <ean> [<ean> ...]
      Temporarily sets the given frozen EAN(s) to their full NORMAL price
      (no discount) and pushes it live. Backs up the old (safe) price first.

  python src/probe_recovery.py check
      Run this AFTER Channable's next hourly import has had time to apply
      (wait ~70-90 minutes after "start"). Re-checks live buybox status for
      every EAN currently being probed:
        - Still has buybox -> keep the higher price (margin recovered!)
        - Lost the buybox  -> revert to the backed-up safe price immediately

  python src/probe_recovery.py candidates [n]
      Only shows the best n candidates, changes nothing.

  python src/probe_recovery.py auto [n]
      Selects the best n candidates and starts a round straight away.

Both phases must be run from a residential connection (e.g. Peter's own
machine) - bol.com blocks buybox-checking requests from cloud/datacenter
IPs, same limitation as the main tool's check_buybox().

Never run two scraping scripts at once - not the probe alongside sync_buybox,
and not NL alongside BE. That gets us rate-limited by bol.com.
"""
import os
import sys
import json
import requests
import base64
from pathlib import Path
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase2_repricing import RepricingEngine

from dotenv import load_dotenv
load_dotenv()

CSV_URL = "https://raw.githubusercontent.com/peterhoman/bol-repricing/main/bolcom_productinformatie.csv"
GITHUB_REPO = os.getenv("GITHUB_REPO")

# MIN_GAIN is de belangrijkste knop. BE meette dat de opbrengst hieronder
# omslaat: hun ronde op artikelen met veel ruimte hield 12 van 15 (80%), de
# ronde daarna op artikelen met te weinig ruimte maar 1 van 15 (7%).
# NL's eerste ronde hield 3 van 15 (20%) bij dezelfde EUR10-drempel - onze
# markt is drukker, dus hier is de drempel eerder te laag dan te hoog.
MIN_GAIN = 10.0
# Een teruggezet artikel krijgt zijn veilige lage prijs terug en staat daardoor
# de volgende dag weer bovenaan de lijst. Zonder wachttijd probeer je elke
# ronde dezelfde verliezers. Niet optioneel.
COOLDOWN_DAYS = 14
DEFAULT_BATCH = 15


def github_headers():
    token = os.getenv("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def fetch_json(filename, default=None):
    r = requests.get(f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{filename}", timeout=15)
    if r.status_code == 200:
        return r.json()
    return default if default is not None else {}


def upload_json(data, filename, message):
    headers = github_headers()
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    content_b64 = base64.b64encode(json.dumps(data, indent=2).encode("utf-8")).decode("utf-8")
    sha = None
    get_r = requests.get(api_url, headers=headers, timeout=15)
    if get_r.status_code == 200:
        sha = get_r.json().get("sha")
    payload = {"message": message, "content": content_b64}
    if sha:
        payload["sha"] = sha
    r = requests.put(api_url, headers=headers, json=payload, timeout=30)
    return r.status_code in (200, 201)


def trigger_workflow():
    headers = github_headers()
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/reprice.yml/dispatches"
    r = requests.post(api_url, headers=headers, json={"ref": "main"}, timeout=30)
    return r.status_code == 204


def select_candidates(engine, limit=DEFAULT_BATCH):
    """
    Rangschik bevroren artikelen op terug te halen marge:

        winst = volle prijs(VERSE inkoopprijs) - huidige bevroren verkoopprijs

    Let op de VERSE inkoopprijs uit de B-Living-feed, niet de prijs waarop het
    artikel ooit bevroren werd - anders reken je met verouderde inkoop.

    Sluit uit: niet meer in de feed (geen actuele inkoop), al op of boven de
    volle prijs (dat sluit meteen de winnaars van eerdere rondes uit, want die
    staan na een geslaagde probe precies op hun volle prijs), en alles wat
    binnen COOLDOWN_DAYS geprobeerd is.

    Geeft (kandidaten, statistiek) terug.
    """
    frozen = engine.load_frozen_eans()
    feed = engine.bliving_klantprijzen
    history = fetch_json("probe_history.json", {})

    grens = (date.today() - timedelta(days=COOLDOWN_DAYS)).isoformat()
    # Oude vorm was {ean: "JJJJ-MM-DD"}, nieuwe is {ean: {"datum": ..., ...}}.
    # Beide blijven werken zodat bestaande geschiedenis niet verloren gaat.
    in_afkoeling = set()
    for e, v in history.items():
        datum = v.get("datum") if isinstance(v, dict) else v
        if datum and datum >= grens:
            in_afkoeling.add(e)

    kandidaten = []
    stat = {"bevroren": len(frozen), "niet_in_feed": 0, "op_volle_prijs": 0,
            "in_afkoeling": 0, "onder_drempel": 0}

    for ean, kp in frozen.items():
        fresh = feed.get(ean)
        if fresh is None:
            stat["niet_in_feed"] += 1
            continue
        nu = engine.calculate_normal_price(kp)
        vol = engine.calculate_normal_price(fresh)
        winst = round(vol - nu, 2)
        if winst <= 0.02:
            stat["op_volle_prijs"] += 1
            continue
        if ean in in_afkoeling:
            stat["in_afkoeling"] += 1
            continue
        if winst < MIN_GAIN:
            stat["onder_drempel"] += 1
            continue
        kandidaten.append({"ean": ean, "nu": nu, "vol": vol, "winst": winst})

    kandidaten.sort(key=lambda k: -k["winst"])
    stat["boven_drempel"] = len(kandidaten)
    return kandidaten[:limit], stat


def print_candidates(kandidaten, stat):
    print(f"\nBevroren artikelen: {stat['bevroren']}")
    print(f"  boven de drempel van EUR{MIN_GAIN:.2f}: {stat['boven_drempel']}")
    print(f"  al op de volle prijs (niets te halen): {stat['op_volle_prijs']}")
    print(f"  onder de drempel:                     {stat['onder_drempel']}")
    print(f"  in afkoeling ({COOLDOWN_DAYS} dagen):              {stat['in_afkoeling']}")
    if stat["niet_in_feed"]:
        print(f"  niet meer in de B-Living-feed:        {stat['niet_in_feed']}")

    if not kandidaten:
        print("\n[DONE] Geen kandidaten voor een ronde")
        return
    print(f"\nRONDE VAN {len(kandidaten)} ARTIKELEN")
    print(f"{'EAN':<15}{'nu':>10}{'volle prijs':>13}{'erbij':>9}")
    for k in kandidaten:
        print(f"{k['ean']:<15}{k['nu']:>10.2f}{k['vol']:>13.2f}{k['winst']:>9.2f}")
    print(f"\nTerug te halen bij 100% behoud: EUR {sum(k['winst'] for k in kandidaten):.2f}")


def phase_candidates(limit):
    engine = RepricingEngine(CSV_URL)
    kandidaten, stat = select_candidates(engine, limit)
    print_candidates(kandidaten, stat)
    if kandidaten:
        print("\nStarten met:")
        print(f"  python src/probe_recovery.py auto {limit}")


def phase_auto(limit):
    lopend = {k: v for k, v in fetch_json("frozen_probe_backup.json", {}).items()
              if not k.startswith("_")}
    if lopend:
        print(f"\n[STOP] Er loopt nog een probe over {len(lopend)} artikel(en).")
        print("Rond die eerst af:  python src/probe_recovery.py check")
        return
    engine = RepricingEngine(CSV_URL)
    kandidaten, stat = select_candidates(engine, limit)
    print_candidates(kandidaten, stat)
    if not kandidaten:
        return
    print()
    phase_start([k["ean"] for k in kandidaten])


def phase_start(eans):
    # Geen probe meer na 20:30: Channable importeert 's avonds niet meer, dus
    # de artikelen zouden de hele nacht op volle prijs staan zonder dat de
    # check nog iets kan verifieren. Kan gebeuren als de taakplanner een
    # gemiste taak 's avonds inhaalt (-StartWhenAvailable).
    nu = datetime.now()
    if (nu.hour, nu.minute) >= (20, 30):
        print(f"[GEWEIGERD] Het is {nu:%H:%M} - na 20:30 geen probe meer starten "
              f"(Channable importeert vanavond niet meer). Morgen draait de "
              f"geplande ronde gewoon.")
        return

    engine = RepricingEngine(CSV_URL)
    frozen = fetch_json("frozen.json", {})
    probe_backup = fetch_json("frozen_probe_backup.json", {})
    probe_backup.pop("_gestart", None)

    updated = 0
    for ean in eans:
        if ean not in frozen:
            print(f"[SKIP] {ean} is not currently frozen (not a buybox winner) - nothing to probe")
            continue
        if ean not in engine.bliving_klantprijzen:
            print(f"[SKIP] {ean} not found in current B-Living feed")
            continue

        old_klantprijs = frozen[ean]
        fresh_klantprijs = engine.bliving_klantprijzen[ean]

        probe_backup[ean] = old_klantprijs
        frozen[ean] = fresh_klantprijs
        updated += 1
        print(f"[PROBE] {ean}: {old_klantprijs} -> {fresh_klantprijs} "
              f"(price {engine.calculate_normal_price(old_klantprijs):.2f} -> "
              f"{engine.calculate_normal_price(fresh_klantprijs):.2f})")

    if updated == 0:
        print("\n[DONE] Nothing to probe")
        return

    # Starttijd bij de backup, zodat check kan weigeren als hij te vroeg
    # draait. Sleutel begint met _ zodat hij nooit als EAN gelezen wordt.
    probe_backup["_gestart"] = datetime.now().isoformat(timespec="seconds")

    upload_json(frozen, "frozen.json", f"Probe recovery: test {updated} EAN(s) at full price")
    upload_json(probe_backup, "frozen_probe_backup.json", f"Backup before probing {updated} EAN(s)")
    trigger_workflow()

    print(f"\n[STARTED] {updated} EAN(s) set to full normal price and pushed.")
    print("Wait ~70-90 minutes (for Channable's next hourly import), then run:")
    print("  python src/probe_recovery.py check")


def phase_check():
    probe_backup = fetch_json("frozen_probe_backup.json", {})
    gestart = probe_backup.pop("_gestart", None)
    if not probe_backup:
        print("[DONE] No probes currently in progress")
        return

    # Te vroeg checken leest de OUDE prijs (Channable heeft de verhoging dan
    # nog niet geimporteerd), ziet daardoor "koopblok behouden" en houdt een
    # prijs vast die in werkelijkheid niet wint. Minimaal 30 minuten wachten;
    # de backup blijft staan, dus later opnieuw checken kan gewoon.
    if gestart:
        try:
            verstreken = (datetime.now() - datetime.fromisoformat(gestart)).total_seconds() / 60
        except ValueError:
            verstreken = None
        if verstreken is not None and verstreken < 30:
            print(f"[GEWEIGERD] Probe is pas {verstreken:.0f} minuten geleden gestart "
                  f"({gestart}). Minimaal 30 minuten wachten, anders lees je de oude "
                  f"prijs en houd je een niet-winnende prijs vast. Backup blijft staan.")
            return

    engine = RepricingEngine(CSV_URL)
    frozen = fetch_json("frozen.json", {})
    session = requests.Session()

    kept = []
    reverted = []
    remaining_backup = {}

    for ean, old_klantprijs in probe_backup.items():
        result = engine.check_buybox(ean, session)
        if result.get("found") and result.get("has_buybox"):
            kept.append(ean)
            print(f"[KEPT] {ean}: still has buybox at the higher price - margin recovered!")
        else:
            frozen[ean] = old_klantprijs
            reverted.append(ean)
            print(f"[REVERTED] {ean}: lost buybox - restored to safe price {old_klantprijs}")
        import time
        time.sleep(0.3)

    upload_json(frozen, "frozen.json", f"Probe recovery result: kept {len(kept)}, reverted {len(reverted)}")

    # Geschiedenis wegschrijven VOOR het legen van de backup, anders is de lijst
    # weg. Zowel behouden als teruggezette EAN's, zodat select_candidates ze de
    # komende COOLDOWN_DAYS overslaat - een teruggezet artikel staat morgen
    # anders meteen weer bovenaan.
    # Naast de datum ook de UITKOMST, de winst waarop geselecteerd is en de
    # titel. Drie selectiecriteria zijn getest en alle drie voorspellen niets
    # (bedrag, dagen onafgebroken bevroren, productgroep - zie HANDOFF.md).
    # Daarom niet verder zoeken maar gewoon vastleggen: na een aantal rondes
    # is er genoeg data om te zien of er toch een patroon in zit. Afspraak met
    # de BE-chat, 17 augustus.
    history = fetch_json("probe_history.json", {})
    vandaag = date.today().isoformat()
    for ean, oud_kp in probe_backup.items():
        fresh = engine.bliving_klantprijzen.get(ean)
        winst = (round(engine.calculate_normal_price(fresh)
                       - engine.calculate_normal_price(oud_kp), 2)
                 if fresh is not None else None)
        history[ean] = {
            "datum": vandaag,
            "uitkomst": "behouden" if ean in kept else "terug",
            "winst": winst,
            "titel": engine.bliving_titels.get(ean, "")[:60],
        }
    upload_json(history, "probe_history.json",
                f"Probe history: {len(probe_backup)} EAN(s) probed on {vandaag} "
                f"({len(kept)} kept, {len(reverted)} reverted)")

    upload_json({}, "frozen_probe_backup.json", "Clear probe backup - probe cycle complete")
    if reverted:
        trigger_workflow()

    print(f"\n[DONE] Kept higher price: {len(kept)} | Reverted to safe price: {len(reverted)}")
    if reverted:
        print(f"\n[LET OP] Draai de komende ~90 minuten GEEN sync_buybox.py.")
        print("Channable heeft de teruggezette prijzen nog niet geimporteerd, dus een")
        print("sync ziet die artikelen als 'koopblok kwijt' en ontdooit ze onnodig.")
        print("(Gebeurde in NL op 17 augustus: 11 van de 15 'verliezen' waren dit.)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    if command == "start":
        eans = sys.argv[2:]
        if not eans:
            print("Usage: python src/probe_recovery.py start <ean> [<ean> ...]")
            sys.exit(1)
        phase_start(eans)
    elif command == "check":
        phase_check()
    elif command == "candidates":
        phase_candidates(int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BATCH)
    elif command == "auto":
        phase_auto(int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BATCH)
    else:
        print(__doc__)
        sys.exit(1)
