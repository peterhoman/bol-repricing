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

CSV_URL = "https://api.github.com/repos/peterhoman/bol-repricing/contents/bolcom_productinformatie.csv"
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
# Hoeveel we onder de goedkoopste concurrent gaan zitten. AANNAME, niet
# bewezen: BE gebruikt 2 cent maar heeft nooit getest of dat nodig is - een
# gelijke prijs of zelfs iets erboven kan ook winnen (beoordeling/levertijd).
# Als het koopblok bij deze marge blijft, is verlagen naar 0.01 of 0.00 het
# proberen waard; dat is dan wel meetbaar in plaats van gegokt.
UNDERCUT = 0.02


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


MAX_STAP = 5.0   # nooit in een keer naar de volle prijs: zie phase_optimize


# --- Verkoperbewust margeherstel (8 sept, akkoord Peter) ---------------------
# Een week meten (1-8 sept, NL) leerde: niet de levertijd voorspelt of een
# verhoging het koopblok overleeft, maar de VERKOPER. Bohemian Living NL,
# Cactula en Izziet laten ons tot 1-2 cent onder hun prijs zitten, dagen
# achtereen, ongeacht of ze die dag "even snel" of "trager" lezen. Cammeraat
# en Bouwkern pakken het koopblok bij elke verhoging, ook als wij euro's
# goedkoper zijn (Cammeraat 3 van 3 op 7 sept; Bouwkern 3700837158345 op
# 8 sept). Sebic won bij BE 3 van 3 tegen hen. De levertijdregel werkte
# omdat de eerste groep toevallig vaak "trager" leest - maar hij hangt van de
# weekdag af (Cactula: maandag trager, dinsdag even snel) en mist de kern.
# Matching op begin van de naam, kleine letters ("Sebic - CAN-Interiors",
# "Bouwkern.com", "Cammeraat ").
VERKOPERS_VLAK_ONDER = ("bohemian living", "cactula", "izziet")
VERKOPERS_NOOIT = ("cammeraat", "bouwkern", "sebic")

# Geheugen (optimize_history.json op GitHub), voor twee lessen van 4-8 sept:
# 1. 8716522090192 hield op 116-121 en verloor op 122,90 en 126,38 - de
#    EUR5-stap tilde hem elke paar dagen over zijn plafond: een flip-lus die
#    de regel zelf maakte. Na een verlies-na-verhoging: COOLDOWN dagen niets,
#    en daarna nooit meer tot op de prijs waarop het verloor.
# 2. "Geen concurrent" bleek twee keer een momentopname (Cammeraat 4 sept,
#    Bouwkern 8 sept): de concurrent stond even niet op de pagina en wij
#    stapten naar vol. Nu: pas stappen als een EERDERE run (max 3 dagen
#    terug) ook geen concurrent zag, nooit boven de laatst geziene
#    concurrent (7 dagen), en helemaal niet als die laatst geziene een
#    NOOIT-verkoper was.
HISTORY_FILE = "optimize_history.json"
COOLDOWN_NA_VERLIES = 7       # dagen
PLAFOND_MARGE = 1.00          # na cooldown: blijf zoveel onder de verloren prijs
CONC_GEHEUGEN_DAGEN = 7
GEEN_CONC_BEVESTIGING_DAGEN = 3
HISTORY_BEWAREN_DAGEN = 60


def fetch_json_api(filename, default=None):
    """Zoals fetch_json, maar via de Contents-API (vers, geen CDN-cache)."""
    h = github_headers()
    h["Accept"] = "application/vnd.github.raw"
    h["Cache-Control"] = "no-cache"
    r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}", headers=h, timeout=30)
    if r.status_code == 200:
        return json.loads(r.text)
    return default if default is not None else {}


def _dagen_geleden(datum_str, vandaag):
    if not datum_str:
        return None
    return (vandaag - date.fromisoformat(datum_str)).days


def _verkoper_type(naam):
    n = (naam or "").strip().lower()
    if any(n.startswith(v) for v in VERKOPERS_NOOIT):
        return "nooit"
    if any(n.startswith(v) for v in VERKOPERS_VLAK_ONDER):
        return "vlak_onder"
    return "onbekend"


def registreer_verliezen(history, frozen, engine, vandaag):
    """
    Wie is na een verhoging het koopblok kwijtgeraakt? Dat zien we aan
    frozen.json: het artikel is niet meer bevroren, of is opnieuw bevroren
    op een LAGERE prijs dan waar we het naartoe zetten (teruggewonnen via de
    dagroute). Alleen toegerekend aan de verhoging als die hooguit 3 dagen
    geleden was. Een artikel dat later weer op of boven de verloren prijs
    wint, krijgt zijn record gewist (het plafond is dan achterhaald).
    """
    gevonden = []
    for ean, h in history.items():
        verhoogd_naar = h.get("verhoogd_naar")
        dv = _dagen_geleden(h.get("laatst_verhoogd"), vandaag)
        huidig = engine.calculate_normal_price(frozen[ean]) if ean in frozen else None
        if h.get("verloren_op") and huidig is not None and huidig >= h["verloren_op"] - 0.005:
            h["verloren"] = None
            h["verloren_op"] = None
        if verhoogd_naar and dv is not None and dv <= 3:
            if huidig is None or huidig < verhoogd_naar - 0.05:
                h["verloren"] = vandaag.isoformat()
                h["verloren_op"] = verhoogd_naar
                h["verhoogd_naar"] = None      # zodat dit verlies maar één keer telt
                gevonden.append((ean, verhoogd_naar, huidig))
    return gevonden


def phase_optimize(limit):
    """
    Margeherstel op basis van de ECHTE concurrentprijzen, niet op gokwerk.

    Vervangt de probe (die zette op vol, wachtte 90 minuten en keek of het
    koopblok het overleefde; werkte in augustus, faalde daarna volledig).
    Sinds 1 september lezen we per artikel alle verkopers, prijzen en
    levertijden uit (engine.check_all_offers), ook als wij het koopblok
    hebben.

    Regels per bevroren artikel (sinds 8 sept verkoperbewust):
      in cooldown na verlies-na-verhoging    -> niets doen
      geen andere verkoper                   -> stap van max MAX_STAP, maar pas
                                                als een eerdere run dat ook zag,
                                                nooit boven de laatst geziene
                                                concurrent, en niet als die een
                                                NOOIT-verkoper was
      goedkoopste ander ONDER of OP ons      -> niets doen (we winnen al)
      goedkoopste ander is NOOIT-verkoper    -> niets doen
      goedkoopste ander is VLAK-ONDER-verkoper -> tot UNDERCUT eronder, ongeacht levertijd
      anders: alleen als hij aantoonbaar TRAGER levert -> tot UNDERCUT eronder;
              even snel / sneller / onleesbaar -> niets doen
    Altijd: max MAX_STAP per ronde, geklemd op [bodem, vol], en na een eerder
    verlies nooit tot op de prijs waarop het verloor (PLAFOND_MARGE eronder).

    De EUR5-stap per ronde is bewust: een pagina die verkeerd geparsed is ziet
    er precies zo uit als "geen concurrent", en stapsgewijs kom je binnen een
    paar dagen op hetzelfde punt uit met veel minder risico. Bij Bohemian
    duurde het 2-3 dagen tot 2 cent onder - allemaal gehouden.
    """
    engine = RepricingEngine(CSV_URL)
    frozen = engine.load_frozen_eans()
    feed = engine.bliving_klantprijzen
    eans = [e for e in frozen if e in feed][:limit]
    vandaag = date.today()
    history = fetch_json_api(HISTORY_FILE, {})

    verliezen = registreer_verliezen(history, frozen, engine, vandaag)
    for ean, prijs, huidig in verliezen:
        print(f"[VERLIES] {ean}: verhoogd naar EUR{prijs:.2f}, nu "
              f"{'niet meer bevroren' if huidig is None else f'teruggewonnen op EUR{huidig:.2f}'} "
              f"-> {COOLDOWN_NA_VERLIES} dagen rust, daarna plafond EUR{prijs - PLAFOND_MARGE:.2f}")

    print(f"\n[OPTIMIZE] {len(eans)} bevroren artikel(en) nakijken op echte concurrentprijzen...")
    session = requests.Session()
    verhoogd, met_rust, mislukt = {}, 0, 0
    geen_conc_bevestigd, geen_conc_wacht, geen_conc_geblokkeerd = 0, 0, 0
    cooldown, verkoper_nooit, verkoper_vlak = 0, 0, 0
    lev_onleesbaar, lev_gelijk, lev_sneller, lev_trager = 0, 0, 0, 0
    overgeslagen = []
    regels = []

    for i, ean in enumerate(eans):
        res = engine.check_all_offers(ean, session)
        if not res.get("found"):
            mislukt += 1
            continue
        onze = engine.calculate_normal_price(frozen[ean])
        bodem = engine.calculate_minimum_price(feed[ean])
        vol = engine.calculate_normal_price(feed[ean])
        anderen = res["others"]
        h = history.setdefault(ean, {})

        dv = _dagen_geleden(h.get("verloren"), vandaag)
        if dv is not None and dv < COOLDOWN_NA_VERLIES:
            cooldown += 1
            overgeslagen.append((ean, onze, h.get("verloren_op") or 0, "-", None, None,
                                 f"cooldown (verloor {dv}d geleden op {h['verloren_op']:.2f})"))
            continue
        plafond = (h["verloren_op"] - PLAFOND_MARGE) if h.get("verloren_op") else None

        if not anderen:
            laatst = _dagen_geleden(h.get("conc_gezien"), vandaag)
            eerder_geen = _dagen_geleden(h.get("geen_conc_gezien"), vandaag)
            h["geen_conc_gezien"] = vandaag.isoformat()
            if laatst is not None and laatst <= CONC_GEHEUGEN_DAGEN and _verkoper_type(h.get("conc_naam")) == "nooit":
                geen_conc_geblokkeerd += 1
                overgeslagen.append((ean, onze, h.get("conc_prijs") or 0, h.get("conc_naam", "?"), None, None,
                                     f"geen concurrent, maar {laatst}d geleden nog {h.get('conc_naam', '?')[:16]} (nooit-verkoper)"))
                continue
            if eerder_geen is None or eerder_geen == 0 or eerder_geen > GEEN_CONC_BEVESTIGING_DAGEN:
                geen_conc_wacht += 1
                overgeslagen.append((ean, onze, 0, "-", None, None, "geen concurrent, wacht op bevestiging volgende run"))
                continue
            tak = "geen"
            doel = min(onze + MAX_STAP, vol)
            reden = "geen concurrent (bevestigd)"
            if laatst is not None and laatst <= CONC_GEHEUGEN_DAGEN and h.get("conc_prijs"):
                doel = min(doel, h["conc_prijs"] - UNDERCUT)
                reden += f", plafond {h.get('conc_naam', '?')[:14]} {h['conc_prijs']:.2f} ({laatst}d)"
        else:
            laagste, naam, conc_lev = anderen[0]
            onze_lev = res.get("our_delivery")
            h["conc_gezien"] = vandaag.isoformat()
            h["conc_prijs"] = laagste
            h["conc_naam"] = naam
            if laagste <= onze:
                met_rust += 1
                continue
            soort = _verkoper_type(naam)
            if soort == "nooit":
                verkoper_nooit += 1
                overgeslagen.append((ean, onze, laagste, naam, onze_lev, conc_lev, "verkoper: nooit verhogen"))
                continue
            if soort == "vlak_onder":
                tak = "vlak"
                reden = f"onder {naam[:22]} (EUR{laagste:.2f}, vlak-onder-verkoper)"
            else:
                if conc_lev is None or onze_lev is None:
                    lev_onleesbaar += 1
                    overgeslagen.append((ean, onze, laagste, naam, onze_lev, conc_lev, "levertijd onleesbaar"))
                    continue
                if conc_lev == onze_lev:
                    lev_gelijk += 1
                    overgeslagen.append((ean, onze, laagste, naam, onze_lev, conc_lev, "even snel"))
                    continue
                if conc_lev < onze_lev:
                    lev_sneller += 1
                    overgeslagen.append((ean, onze, laagste, naam, onze_lev, conc_lev, "sneller"))
                    continue
                tak = "trager"
                reden = f"onder {naam[:22]} (EUR{laagste:.2f}, levert {conc_lev - onze_lev}d later)"
            doel = min(laagste - UNDERCUT, onze + MAX_STAP, vol)

        if plafond is not None and doel > plafond:
            doel = plafond
            reden += f", plafond na verlies {plafond:.2f}"
        doel = max(doel, bodem)
        if doel <= onze + 0.02:
            met_rust += 1
            continue
        verhoogd[ean] = engine.calculate_klantprijs_for_target_price(doel)
        if tak == "vlak":
            verkoper_vlak += 1
        elif tak == "trager":
            lev_trager += 1
        else:
            geen_conc_bevestigd += 1
        h["laatst_verhoogd"] = vandaag.isoformat()
        h["verhoogd_naar"] = round(doel, 2)
        regels.append((ean, onze, doel, round(doel - onze, 2), reden))
        if (i + 1) % 20 == 0:
            print(f"   {i+1}/{len(eans)} bekeken...")

    print(f"\n{'EAN':<15}{'nu':>9}{'wordt':>9}{'erbij':>8}  reden")
    for ean, nu, doel, plus, reden in sorted(regels, key=lambda r: -r[3]):
        print(f"{ean:<15}{nu:>9.2f}{doel:>9.2f}{plus:>8.2f}  {reden}")

    # Alleen in het lokale log (geen [..]-prefix): per overgeslagen artikel
    # de reden, prijzen en levertijden, zodat de tellers hieronder na te lopen zijn.
    if overgeslagen:
        print()
        print(f"{'EAN':<15}{'onze':>9}{'conc.':>9}  {'wij':>4} {'zij':>4}  reden / verkoper")
        for ean, nu, conc, naam, wl, cl, reden in overgeslagen:
            wl_s = "?" if wl is None else str(wl)
            cl_s = "?" if cl is None else str(cl)
            print(f"{ean:<15}{nu:>9.2f}{conc:>9.2f}  {wl_s:>4} {cl_s:>4}  {reden} / {str(naam)[:22]}")

    n_over = len(overgeslagen)
    print(f"\n[OPTIMIZE] verhoogd: {len(verhoogd)} "
          f"(vlak-onder-verkoper {verkoper_vlak}, trager {lev_trager}, geen concurrent {geen_conc_bevestigd}) "
          f"| met rust gelaten: {met_rust} | overgeslagen: {n_over} "
          f"= nooit-verkoper {verkoper_nooit} + even snel {lev_gelijk} + sneller {lev_sneller} "
          f"+ onleesbaar {lev_onleesbaar} + cooldown {cooldown} + geen conc. wacht {geen_conc_wacht} "
          f"+ geen conc. geblokkeerd {geen_conc_geblokkeerd} | mislukt: {mislukt}")
    print(f"[OPTIMIZE] opbrengst: EUR {sum(r[3] for r in regels):.2f} per verkoopcyclus")

    # Geheugen opschonen en altijd wegschrijven (ook de verliezen en de
    # "gezien"-datums van vandaag zijn waardevol als er niets verhoogd is).
    grens = HISTORY_BEWAREN_DAGEN
    history = {e: h for e, h in history.items()
               if any(_dagen_geleden(h.get(k), vandaag) is not None and _dagen_geleden(h.get(k), vandaag) <= grens
                      for k in ("laatst_verhoogd", "verloren", "conc_gezien", "geen_conc_gezien"))}
    upload_json(history, HISTORY_FILE, f"Optimize-geheugen {vandaag.isoformat()}: {len(verhoogd)} verhoogd, {len(verliezen)} verlies geregistreerd")

    if not verhoogd:
        print("[DONE] Niets te wijzigen")
        return

    frozen.update(verhoogd)
    upload_json(frozen, "frozen.json",
                f"Optimize: {len(verhoogd)} bevroren prijs(en) omhoog o.b.v. echte concurrentprijzen")
    trigger_workflow()
    print("[DONE] frozen.json bijgewerkt en feed getriggerd")


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
        # Een netwerkhapering mag de hele ronde niet omvergooien. Op 22
        # augustus sloot bol.com de verbinding halverwege (RemoteDisconnected);
        # het script crashte VOOR de upload, waardoor frozen.json niet werd
        # bijgewerkt en de backup bleef staan - wat de probe van de volgende
        # dag blokkeerde. Een mislukte check telt nu als "geen koopblok", en
        # dat is de veilige kant: het artikel gaat terug naar zijn veilige
        # prijs in plaats van op de probe-prijs te blijven staan.
        try:
            result = engine.check_buybox(ean, session)
        except Exception as exc:
            print(f"[WARN] {ean}: check mislukt ({type(exc).__name__}) - "
                  f"behandeld als koopblok kwijt, prijs gaat terug")
            result = {"found": False}
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
    elif command == "optimize":
        phase_optimize(int(sys.argv[2]) if len(sys.argv) > 2 else 40)
    elif command == "auto":
        phase_auto(int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BATCH)
    else:
        print(__doc__)
        sys.exit(1)
