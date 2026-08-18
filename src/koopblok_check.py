#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meet hoeveel artikelen uit de CSV van vandaag inmiddels het koopblok hebben.

Bedoeld om een paar uur na de ochtendrun te draaien: die zet alle prijzen
scherp, waarna bol.com/Channable tijd nodig heeft om ze te verwerken. Dit
script kijkt dan live per EAN wie het koopblok heeft.

Moet vanaf een gewone (residentiele) verbinding draaien - bol.com blokkeert
live koopblok-checks vanaf cloud-IP's, net als match_prices.py.

    python src/koopblok_check.py --baseline   # nulmeting wegschrijven
    python src/koopblok_check.py              # meten en vergelijken

De nulmeting komt in output/koopblok_baseline.json.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase2_repricing import RepricingEngine

load_dotenv()

CSV_URL = ("https://api.github.com/repos/peterhoman/bol-repricing/"
           "contents/bolcom_productinformatie.csv")
BASELINE = Path(__file__).resolve().parent.parent / "output" / "koopblok_baseline.json"


def main():
    schrijf_baseline = "--baseline" in sys.argv

    engine = RepricingEngine(CSV_URL)
    if not engine.products:
        print("[FOUT] Geen producten uit de CSV geladen")
        return 1

    eans = sorted(engine.products.keys())
    frozen = engine.load_frozen_eans()

    if schrijf_baseline:
        BASELINE.parent.mkdir(exist_ok=True)
        BASELINE.write_text(json.dumps({
            "vastgelegd": datetime.now().isoformat(timespec="seconds"),
            "csv_eans": eans,
            "bevroren_bij_start": sorted(set(frozen) & set(eans)),
            "bevroren_totaal": len(frozen),
        }, indent=2))
        print(f"\n[NULMETING] {len(eans)} EAN's uit de CSV vastgelegd")
        print(f"   waarvan al bevroren: {len(set(frozen) & set(eans))}")
        print(f"   weggeschreven naar: {BASELINE}")
        return 0

    if not BASELINE.exists():
        print(f"[FOUT] Geen nulmeting gevonden op {BASELINE}")
        print("       Draai eerst: python src/koopblok_check.py --baseline")
        return 1

    basis = json.loads(BASELINE.read_text())
    eans = basis["csv_eans"]

    print(f"\n[CHECK] Live koopblok-status van {len(eans)} EAN(s) uit de CSV "
          f"van {basis['vastgelegd'][:16]}...")

    session = requests.Session()
    heeft, niet, mislukt = [], [], []
    for i, ean in enumerate(eans):
        r = engine.check_buybox(ean, session)
        if not r.get("found"):
            mislukt.append(ean)
        elif r.get("has_buybox"):
            heeft.append((ean, float(r.get("price") or 0)))
        else:
            niet.append((ean, float(r.get("price") or 0)))
        if (i + 1) % 50 == 0:
            print(f"   {i+1}/{len(eans)} gecheckt...")

    gecheckt = len(heeft) + len(niet)
    print()
    print("=" * 60)
    print(f"KOOPBLOK-STATUS  ({datetime.now().strftime('%d-%m-%Y %H:%M')})")
    print("=" * 60)
    print(f"  CSV van vanochtend:        {len(eans)} artikelen")
    print(f"  succesvol gecheckt:        {gecheckt}")
    print(f"  MET koopblok:              {len(heeft)}")
    print(f"  zonder koopblok:           {len(niet)}")
    print(f"  check mislukt:             {len(mislukt)}")
    if gecheckt:
        print(f"\n  slagingspercentage:        {100*len(heeft)/gecheckt:.0f}% "
              f"van de gecheckte artikelen")

    # hoeveel daarvan stonden bij de nulmeting nog niet op gewonnen?
    al_bevroren = set(basis.get("bevroren_bij_start", []))
    nieuw = [e for e, _ in heeft if e not in al_bevroren]
    print(f"\n  waarvan nieuw gewonnen sinds de nulmeting: {len(nieuw)}")

    # hoe ver zitten de verliezers er nog vanaf?
    if niet:
        gaten = []
        for ean, conc_prijs in niet:
            fresh = engine.bliving_klantprijzen.get(ean)
            if fresh is None or not conc_prijs:
                continue
            bodem = engine.calculate_minimum_price(fresh)
            gaten.append(round(bodem - conc_prijs, 2))
        onbereikbaar = sum(1 for g in gaten if g > 0)
        print(f"\n  van de {len(niet)} zonder koopblok:")
        print(f"    concurrent zit ONDER onze bodemprijs: {onbereikbaar} "
              f"(onbereikbaar zonder verlies)")
        print(f"    nog haalbaar:                         {len(gaten)-onbereikbaar}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
