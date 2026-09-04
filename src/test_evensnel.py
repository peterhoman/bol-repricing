"""
Gecontroleerde test (4 september, akkoord Peter): VIJF bevroren artikelen uit
de groep "even snel" EUR1 omhoog - NIET tot vlak onder de concurrent.

Waarom: in die groep (76 van 176 op 4 sept) doet de optimize-regel niets,
omdat "tot 2 cent onder de concurrent" daar op 1 sept maar 20% behoud gaf.
Maar of een BESCHEIDEN stap, ruim onder de concurrent, het koopblok kost is
nooit gemeten. Peter verwacht dat +EUR2 al verliest; daarom +EUR1, en eerst
vijf artikelen (Peter, 4 sept).

    python src/test_evensnel.py kandidaten   # alle bevroren live scannen, 5 kiezen (schrijft niets)
    python src/test_evensnel.py start        # die 5 opnieuw live checken en +EUR1 pushen
    python src/test_evensnel.py status       # wie heeft nu het koopblok op die 5
    python src/test_evensnel.py revert       # de 5 terug naar hun oude prijs

Selectie: concurrent levert even snel (beide levertijden leesbaar en gelijk),
goedkoopste concurrent minstens MIN_RUIMTE boven ons (zodat we na +EUR1 nog
ruim eronder zitten en dus echt "+EUR1" meten en niet "vlak onder"), doel
geklemd op [bodem, vol], maximaal MAX_PER_VERKOPER per verkoper voor spreiding.

Beoordelen bij de sync van de volgende dag(en). Afspraak met Peter (4 sept):
verliezen we koopblokken, dan draaien we terug - die beslissing neemt de
chat zelf, zonder te vragen. Wie het koopblok verliest gaat sowieso vanzelf
via de dagroute terug; `revert` is voor de artikelen die STAAN maar waarvan
we besluiten dat +EUR1 toch niet loont.
"""
import os
import sys
import json
import requests
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase2_repricing import RepricingEngine
from probe_recovery import CSV_URL, GITHUB_REPO, github_headers, upload_json, trigger_workflow
from dotenv import load_dotenv
load_dotenv()

STAP = 1.00
MIN_RUIMTE = 2.00
AANTAL = 5
MAX_PER_VERKOPER = 2
UNDERCUT = 0.02
OUT = Path(__file__).resolve().parent.parent / "output"
KANDIDATEN = OUT / "test_evensnel_kandidaten.json"
BACKUP = OUT / "test_evensnel.json"
BACKUP_GITHUB = "test_evensnel.json"


def lees_frozen_vers():
    """frozen.json via de Contents-API (niet de raw-CDN, die cachet)."""
    h = dict(github_headers())
    h["Accept"] = "application/vnd.github.raw"
    h["Cache-Control"] = "no-cache"
    r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/contents/frozen.json", headers=h, timeout=30)
    r.raise_for_status()
    return json.loads(r.text)


def beoordeel(engine, ean, kp, res):
    """Geeft (ok, info). ok=True als dit artikel aan de testcriteria voldoet."""
    onze = engine.calculate_normal_price(kp)
    feed_kp = engine.bliving_klantprijzen.get(ean)
    if feed_kp is None:
        return False, "niet in feed"
    bodem = engine.calculate_minimum_price(feed_kp)
    vol = engine.calculate_normal_price(feed_kp)
    if not res.get("found"):
        return False, "check mislukt"
    if not res["others"]:
        return False, "geen concurrent"
    laagste, naam, conc_lev = res["others"][0]
    onze_lev = res.get("our_delivery")
    if conc_lev is None or onze_lev is None:
        return False, "levertijd onleesbaar"
    if conc_lev != onze_lev:
        return False, "niet even snel"
    ruimte = round(laagste - onze, 2)
    if ruimte < MIN_RUIMTE:
        return False, "te weinig ruimte"
    doel = min(onze + STAP, laagste - UNDERCUT, vol)
    doel = max(doel, bodem)
    if doel <= onze + 0.02:
        return False, "geen ruimte binnen band"
    return True, {"ean": ean, "oud_kp": kp, "oud_prijs": onze, "doel": round(doel, 2),
                  "nieuw_kp": engine.calculate_klantprijs_for_target_price(doel),
                  "concurrent": naam, "conc_prijs": laagste, "ruimte": ruimte,
                  "levertijd": [onze_lev, conc_lev], "vol": vol, "bodem": bodem}


def cmd_kandidaten():
    engine = RepricingEngine(CSV_URL)
    frozen = lees_frozen_vers()
    s = requests.Session()
    print(f"[TEST] {len(frozen)} bevroren artikelen live scannen op 'even snel' met >= EUR{MIN_RUIMTE:.2f} ruimte...")
    ok, redenen = [], {}
    for i, (ean, kp) in enumerate(frozen.items()):
        goed, info = beoordeel(engine, ean, kp, engine.check_all_offers(ean, s))
        if goed:
            ok.append(info)
        else:
            redenen[info] = redenen.get(info, 0) + 1
        if (i + 1) % 40 == 0:
            print(f"   {i+1}/{len(frozen)} bekeken...")
    ok.sort(key=lambda k: -k["ruimte"])
    gekozen, per_verkoper = [], {}
    for k in ok:
        v = k["concurrent"]
        if per_verkoper.get(v, 0) >= MAX_PER_VERKOPER:
            continue
        per_verkoper[v] = per_verkoper.get(v, 0) + 1
        gekozen.append(k)
        if len(gekozen) == AANTAL:
            break
    print(f"[TEST] voldoet aan de criteria: {len(ok)} | afgevallen: {redenen}")
    print()
    print(f"{'EAN':<15}{'nu':>9}{'wordt':>9}{'conc.':>9}{'ruimte':>8}  lev.  verkoper")
    for k in gekozen:
        lev = f"{k['levertijd'][0]}/{k['levertijd'][1]}"
        print(f"{k['ean']:<15}{k['oud_prijs']:>9.2f}{k['doel']:>9.2f}{k['conc_prijs']:>9.2f}{k['ruimte']:>8.2f}  {lev:<5} {k['concurrent'][:24]}")
    OUT.mkdir(exist_ok=True)
    KANDIDATEN.write_text(json.dumps({"gemaakt": datetime.now().isoformat(timespec="seconds"),
                                      "gekozen": gekozen, "alle_geschikt": ok}, indent=2), encoding="utf-8")
    print()
    print(f"[DONE] {len(gekozen)} kandidaten opgeslagen in {KANDIDATEN.name} (niets gepusht); geschikt in totaal: {len(ok)}")


def cmd_start():
    if BACKUP.exists():
        print(f"[STOP] {BACKUP.name} bestaat al - er loopt een test. Eerst 'revert'.")
        return
    if not KANDIDATEN.exists():
        print("[STOP] Eerst 'kandidaten' draaien.")
        return
    kand = json.loads(KANDIDATEN.read_text(encoding="utf-8"))
    leeftijd = (datetime.now() - datetime.fromisoformat(kand["gemaakt"])).total_seconds() / 3600
    if leeftijd > 3:
        print(f"[STOP] Kandidatenlijst is {leeftijd:.1f} uur oud - opnieuw 'kandidaten' draaien.")
        return
    engine = RepricingEngine(CSV_URL)
    frozen = lees_frozen_vers()
    s = requests.Session()
    artikelen, verhoogd = {}, {}
    print(f"[TEST] {len(kand['gekozen'])} kandidaten opnieuw live checken...")
    for k in kand["gekozen"]:
        ean = k["ean"]
        if ean not in frozen:
            print(f"   {ean}: niet meer bevroren - overgeslagen")
            continue
        goed, info = beoordeel(engine, ean, frozen[ean], engine.check_all_offers(ean, s))
        if not goed:
            print(f"   {ean}: voldoet niet meer ({info}) - overgeslagen")
            continue
        artikelen[ean] = info
        verhoogd[ean] = info["nieuw_kp"]
        print(f"   {ean}: {info['oud_prijs']:.2f} -> {info['doel']:.2f} (conc. {info['conc_prijs']:.2f}, {info['concurrent'][:24]})")
    if not verhoogd:
        print("[DONE] Niets te doen")
        return
    backup = {"gestart": datetime.now().isoformat(timespec="seconds"), "stap": STAP, "artikelen": artikelen}
    OUT.mkdir(exist_ok=True)
    BACKUP.write_text(json.dumps(backup, indent=2), encoding="utf-8")
    frozen.update(verhoogd)
    if not upload_json(frozen, "frozen.json", f"Test even-snel: {len(verhoogd)} bevroren prijs(en) EUR{STAP:.2f} omhoog"):
        print("[ERROR] frozen.json upload mislukt (409?) - NIETS gewijzigd op GitHub; lokale backup verwijderd")
        BACKUP.unlink()
        return
    upload_json(backup, BACKUP_GITHUB, "Test even-snel: backup van de oude prijzen")
    trigger_workflow()
    winst = sum(a["doel"] - a["oud_prijs"] for a in artikelen.values())
    print()
    print(f"[DONE] {len(verhoogd)} artikelen EUR{STAP:.2f} omhoog, backup in {BACKUP.name} + op GitHub, feed getriggerd")
    print(f"[DONE] opbrengst als alles standhoudt: EUR {winst:.2f} per verkoopcyclus")


def cmd_status():
    if not BACKUP.exists():
        print("[STOP] Geen lopende test (geen backup).")
        return
    backup = json.loads(BACKUP.read_text(encoding="utf-8"))
    engine = RepricingEngine(CSV_URL)
    frozen = lees_frozen_vers()
    s = requests.Session()
    print(f"[TEST] gestart {backup['gestart']} - stand van de {len(backup['artikelen'])} artikelen:")
    print()
    print(f"{'EAN':<15}{'test':>9}{'goedk.':>9}  bevroren  koopblok bij")
    houdt = 0
    for ean, a in backup["artikelen"].items():
        b = engine.check_buybox(ean, s)
        r = engine.check_all_offers(ean, s)
        goedk = r["offers"][0] if r.get("found") and r.get("offers") else None
        if not b.get("found"):
            wie = f"check mislukt: {b.get('error')}"
        elif b.get("has_buybox"):
            wie = "WIJ"
            houdt += 1
        else:
            wie = (b.get("seller") or "?").strip() + f" op {b.get('price')}"
        goedk_txt = f"(goedkoopste: {goedk[1][:20]} {goedk[0]:.2f})" if goedk else ""
        bevroren = "ja" if ean in frozen else "NEE"
        print(f"{ean:<15}{a['doel']:>9.2f}{(goedk[0] if goedk else 0):>9.2f}  {bevroren:<8}  {wie} {goedk_txt}")
    print()
    print(f"[DONE] koopblok bij ons: {houdt} van {len(backup['artikelen'])}")


def cmd_revert():
    if not BACKUP.exists():
        print("[STOP] Geen lopende test (geen backup).")
        return
    backup = json.loads(BACKUP.read_text(encoding="utf-8"))
    frozen = lees_frozen_vers()
    terug = {ean: a["oud_kp"] for ean, a in backup["artikelen"].items() if ean in frozen}
    print(f"[TEST] {len(terug)} van {len(backup['artikelen'])} staan nog bevroren en gaan terug naar hun oude prijs")
    for ean, kp in terug.items():
        frozen[ean] = kp
    if terug and not upload_json(frozen, "frozen.json", f"Test even-snel: {len(terug)} artikel(en) terug naar oude prijs"):
        print("[ERROR] upload mislukt - niets gewijzigd")
        return
    trigger_workflow()
    afgerond = BACKUP.with_name(f"test_evensnel_afgerond_{datetime.now():%Y%m%d_%H%M}.json")
    BACKUP.rename(afgerond)
    print(f"[DONE] teruggezet, backup hernoemd naar {afgerond.name}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "kandidaten"
    {"kandidaten": cmd_kandidaten, "start": cmd_start, "status": cmd_status, "revert": cmd_revert}[cmd]()
