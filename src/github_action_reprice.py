#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entry point for the scheduled GitHub Actions job.

Runs ONE repricing iteration and exits (no infinite loop, no sleeping).
GitHub Actions itself provides the schedule (cron), so this script can be
completely stateless - it reads its "current position" from the last
published repricing_current.xml on GitHub instead of relying on memory.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from phase2_repricing import RepricingEngine

CSV_URL = "https://raw.githubusercontent.com/peterhoman/bol-repricing/main/bolcom_productinformatie.csv"

if __name__ == "__main__":
    engine = RepricingEngine(CSV_URL)

    if not engine.products:
        print("\n[ERROR] No products loaded from CSV")
        sys.exit(1)

    if not engine.bliving_klantprijzen:
        print("\n[ERROR] No klantprijzen loaded from B-Living feed")
        sys.exit(1)

    adjustments, new_state, buybox_won = engine.run_single_iteration_stateless()

    if buybox_won:
        print(f"\n[BUYBOX] Won buybox this run, price held steady: {buybox_won}")

    output_dir = Path(__file__).resolve().parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    xml_path = str(output_dir / "repricing_current.xml")

    if not engine.generate_reprice_xml(xml_path, adjustments):
        print("\n[ERROR] Failed to generate XML")
        sys.exit(1)

    if not engine.upload_to_github(xml_path, "repricing_current.xml"):
        print("\n[ERROR] Failed to upload XML to GitHub")
        sys.exit(1)

    if not engine.upload_json_to_github(new_state, "state.json"):
        print("\n[ERROR] Failed to upload state.json to GitHub")
        sys.exit(1)

    print("\n[DONE] Single repricing iteration complete")
