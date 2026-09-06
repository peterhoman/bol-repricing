"""
Gecontroleerde test in de groep "even snel" (akkoord Peter, 4 en 6 sept):
bevroren artikelen waarvan de concurrent even snel levert een BESCHEIDEN
stap omhoog, ruim onder de concurrent - niet tot vlak eronder.

Waarom: in die groep (76-84 van ~180 bevroren) doet de optimize-regel niets,
omdat "tot 2 cent onder de concurrent" daar op 1 sept maar 20% behoud gaf.
Maar of +EUR1 terwijl we er nog EUR10 onder zitten het koopblok kost, was
nooit gemeten. Uitslag: 5 van 5 gehouden op 5 én 6 sept.

Groepen (elk met eigen terugzetpunt, in output/test_evensnel.json en als
test_evensnel.json op GitHub):
  G1   4 sept 19:30  5 artikelen +EUR1        (oud_kp = originele prijs)
  G1b  6 sept        dezelfde 5 nog +EUR1     (oud_kp = de +EUR1-prijs van G1)
  G2   6 sept        15 nieuwe artikelen +EUR1

    python src/test_evensnel.py kandidaten          # alle bevroren live scannen (schrijft niets)
    python src/test_evensnel.py start G2 15         # 15 uit de kandidaten +STAP, als groep G2
    python src/test_evensnel.py verhoog G1 G1b      # groep G1 nog een STAP omhoog, vastgelegd als G1b
    python src/test_evensnel.py status [GROEP]      # wie heeft het koopblok
    python src/test_evensnel.py revert GROEP        # groep terug naar haar terugzetpunt

Selectie: concurrent even snel (beide levertijden leesbaar en gelijk),
goedkoopste concurrent na de stap nog >= MIN_RUIMTE boven ons, doel geklemd
op [bodem, vol], maximaal MAX_PER_VERKOPER per verkoper, EAN's die al in een
groep zitten uitgesloten.

Afspraak met Peter: verliezen we in een groep 2 of meer koopblokken, dan
draait de chat die groep terug zonder te vragen. Wie verliest gaat sowieso
vanzelf via de dagroute terug; `revert` is voor de artikelen die nog staan.
Bij elk verlies eerst `status`: wie heeft het koopblok en op welke prijs.
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
MIN_RUIMTE = 2.00          # ruimte die na de stap nog moet overblijven
MAX_PER_VERKOPER = 3
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


def lees_backup():
    if not BACKUP.exists():
        return {"groepen": {}}
    b = json.loads(BACKUP.read_text(encoding="utf-8"))
    if "groepen" not in b:            # oude vorm (4 sept): één naamloze test -> G1
        b = {"groepen": {"G1": {"gestart": b["gestart"], "stap": b["stap"], "artikelen": b["artikelen"]}}}
    return b


def schrijf_backup(b, bericht):
    OUT.mkdir(exist_ok=True)
    BACKUP.write_text(json.dumps(b, indent=2), encoding="utf-8")
    upload_json(b, BACKUP_GITHUB, bericht)


def in_groep(b):
    return {ean for g in b["groepen"].values() for ean in g["artikelen"]}


def beoordeel(engine, ean, kp, res):
    """Geeft (ok, info). ok=True als dit artikel nu een STAP omhoog kan binnen de criteria."""
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
    if ruimte - STAP < MIN_RUIMTE:
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
    bezet = in_groep(lees_backup())
    s = requests.Session()
    print(f"[TEST] {len(frozen)} bevroren artikelen live scannen ({len(bezet)} al in een groep, overgeslagen)...")
    ok, redenen = [], {}
    for i, (ean, kp) in enumerate(frozen.items()):
        if ean in bezet:
            continue
        goed, info = beoordeel(engine, ean, kp, engine.check_all_offers(ean, s))
        if goed:
            ok.append(info)
        else:
            redenen[info] = redenen.get(info, 0) + 1
        if (i + 1) % 40 == 0:
            print(f"   {i+1}/{len(frozen)} bekeken...")
    ok.sort(key=lambda k: -k["ruimte"])
    print(f"[TEST] voldoet aan de criteria: {len(ok)} | afgevallen: {redenen}")
    OUT.mkdir(exist_ok=True)
    KANDIDATEN.write_text(json.dumps({"gemaakt": datetime.now().isoformat(timespec="seconds"),
                                      "geschikt": ok}, indent=2), encoding="utf-8")
    print(f"[DONE] {len(ok)} kandidaten opgeslagen in {KANDIDATEN.name} (niets gepusht)")


def _push_groep(naam, artikelen, verhoogd, frozen, b, omschrijving):
    b["groepen"][naam] = {"gestart": datetime.now().isoformat(timespec="seconds"), "stap": STAP,
                          "omschrijving": omschrijving, "artikelen": artikelen}
    frozen.update(verhoogd)
    if not upload_json(frozen, "frozen.json", f"Test even-snel {naam}: {len(verhoogd)} bevroren prijs(en) EUR{STAP:.2f} omhoog"):
        print("[ERROR] frozen.json upload mislukt (409?) - NIETS gewijzigd, groep niet vastgelegd")
        return False
    schrijf_backup(b, f"Test even-snel {naam}: terugzetpunt vastgelegd")
    trigger_workflow()
    winst = sum(a["doel"] - a["oud_prijs"] for a in artikelen.values())
    print()
    print(f"[DONE] groep {naam}: {len(verhoogd)} artikelen EUR{STAP:.2f} omhoog, terugzetpunt in {BACKUP.name} + op GitHub, feed getriggerd")
    print(f"[DONE] opbrengst als alles standhoudt: EUR {winst:.2f} per verkoopcyclus")
    return True


def cmd_start(naam, aantal):
    b = lees_backup()
    if naam in b["groepen"]:
        print(f"[STOP] groep {naam} bestaat al")
        return
    if not KANDIDATEN.exists():
        print("[STOP] Eerst 'kandidaten' draaien.")
        return
    kand = json.loads(KANDIDATEN.read_text(encoding="utf-8"))
    leeftijd = (datetime.now() - datetime.fromisoformat(kand["gemaakt"])).total_seconds() / 3600
    if leeftijd > 3:
        print(f"[STOP] Kandidatenlijst is {leeftijd:.1f} uur oud - opnieuw 'kandidaten' draaien.")
        return
    bezet = in_groep(b)
    engine = RepricingEngine(CSV_URL)
    frozen = lees_frozen_vers()
    s = requests.Session()
    artikelen, verhoogd, per_verkoper = {}, {}, {}
    print(f"[TEST] groep {naam}: {aantal} kiezen uit {len(kand['geschikt'])} kandidaten, live hercontrole...")
    for k in kand["geschikt"]:
        if len(artikelen) == aantal:
            break
        ean = k["ean"]
        if ean in bezet or ean not in frozen:
            continue
        if per_verkoper.get(k["concurrent"], 0) >= MAX_PER_VERKOPER:
            continue
        goed, info = beoordeel(engine, ean, frozen[ean], engine.check_all_offers(ean, s))
        if not goed:
            print(f"   {ean}: voldoet niet meer ({info}) - overgeslagen")
            continue
        per_verkoper[info["concurrent"]] = per_verkoper.get(info["concurrent"], 0) + 1
        artikelen[ean] = info
        verhoogd[ean] = info["nieuw_kp"]
        print(f"   {ean}: {info['oud_prijs']:>8.2f} -> {info['doel']:>8.2f}  (conc. {info['conc_prijs']:.2f}, {info['concurrent'][:24]})")
    if not verhoogd:
        print("[DONE] Niets te doen")
        return
    _push_groep(naam, artikelen, verhoogd, frozen, b, f"{len(verhoogd)} nieuwe artikelen +EUR{STAP:.2f}")


def cmd_verhoog(bron, naam):
    b = lees_backup()
    if bron not in b["groepen"]:
        print(f"[STOP] groep {bron} bestaat niet")
        return
    if naam in b["groepen"]:
        print(f"[STOP] groep {naam} bestaat al")
        return
    engine = RepricingEngine(CSV_URL)
    frozen = lees_frozen_vers()
    s = requests.Session()
    artikelen, verhoogd = {}, {}
    print(f"[TEST] groep {bron} nog EUR{STAP:.2f} omhoog als {naam}, live hercontrole...")
    for ean in b["groepen"][bron]["artikelen"]:
        if ean not in frozen:
            print(f"   {ean}: niet meer bevroren - overgeslagen")
            continue
        goed, info = beoordeel(engine, ean, frozen[ean], engine.check_all_offers(ean, s))
        if not goed:
            print(f"   {ean}: voldoet niet meer ({info}) - overgeslagen")
            continue
        artikelen[ean] = info
        verhoogd[ean] = info["nieuw_kp"]
        print(f"   {ean}: {info['oud_prijs']:>8.2f} -> {info['doel']:>8.2f}  (conc. {info['conc_prijs']:.2f}, {info['concurrent'][:24]})")
    if not verhoogd:
        print("[DONE] Niets te doen")
        return
    _push_groep(naam, artikelen, verhoogd, frozen, b, f"groep {bron} nog +EUR{STAP:.2f} (terugzetpunt = prijs van {bron})")


def cmd_status(alleen=None):
    b = lees_backup()
    if not b["groepen"]:
        print("[STOP] Geen lopende test.")
        return
    engine = RepricingEngine(CSV_URL)
    frozen = lees_frozen_vers()
    s = requests.Session()
    for naam, g in b["groepen"].items():
        if alleen and naam != alleen:
            continue
        print()
        print(f"[TEST] groep {naam} ({g.get('omschrijving', '')}, gestart {g['gestart']}):")
        print(f"{'EAN':<15}{'test':>9}{'goedk.':>9}  bevroren  koopblok bij")
        houdt = 0
        for ean, a in g["artikelen"].items():
            bb = engine.check_buybox(ean, s)
            r = engine.check_all_offers(ean, s)
            goedk = r["offers"][0] if r.get("found") and r.get("offers") else None
            if not bb.get("found"):
                wie = f"check mislukt: {bb.get('error')}"
            elif bb.get("has_buybox"):
                wie = "WIJ"
                houdt += 1
            else:
                wie = (bb.get("seller") or "?").strip() + f" op {bb.get('price')}"
            goedk_txt = f"(goedkoopste: {goedk[1][:20]} {goedk[0]:.2f})" if goedk else ""
            bevroren = "ja" if ean in frozen else "NEE"
            print(f"{ean:<15}{a['doel']:>9.2f}{(goedk[0] if goedk else 0):>9.2f}  {bevroren:<8}  {wie} {goedk_txt}")
        print(f"[DONE] groep {naam}: koopblok bij ons {houdt} van {len(g['artikelen'])}")


def cmd_revert(naam):
    b = lees_backup()
    if naam not in b["groepen"]:
        print(f"[STOP] groep {naam} bestaat niet")
        return
    g = b["groepen"][naam]
    frozen = lees_frozen_vers()
    terug = {ean: a["oud_kp"] for ean, a in g["artikelen"].items() if ean in frozen}
    print(f"[TEST] groep {naam}: {len(terug)} van {len(g['artikelen'])} staan nog bevroren en gaan terug naar hun terugzetpunt")
    for ean, kp in terug.items():
        frozen[ean] = kp
    if terug and not upload_json(frozen, "frozen.json", f"Test even-snel {naam}: {len(terug)} artikel(en) terug naar terugzetpunt"):
        print("[ERROR] upload mislukt - niets gewijzigd")
        return
    trigger_workflow()
    b.setdefault("afgerond", {})[f"{naam}_{datetime.now():%Y%m%d_%H%M}"] = g
    del b["groepen"][naam]
    schrijf_backup(b, f"Test even-snel {naam}: teruggezet en afgerond")
    print(f"[DONE] groep {naam} teruggezet en verplaatst naar 'afgerond'")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "kandidaten"
    if cmd == "kandidaten":
        cmd_kandidaten()
    elif cmd == "start":
        cmd_start(a[1], int(a[2]))
    elif cmd == "verhoog":
        cmd_verhoog(a[1], a[2])
    elif cmd == "status":
        cmd_status(a[1] if len(a) > 1 else None)
    elif cmd == "revert":
        cmd_revert(a[1])
    else:
        print(__doc__)
