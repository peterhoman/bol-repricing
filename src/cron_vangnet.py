#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vangnet voor overgeslagen cron-runs.

GitHub start geplande workflows niet altijd: op 2 en 4 augustus 2026 bleven
er hele ochtenden runs uit, zonder foutmelding - ze werden simpelweg niet
aangemaakt. Gevolg is mild (Channable importeert dan dezelfde prijs opnieuw,
dus de prijzen zakken trager), maar het kost wel tijd richting de concurrent.

Dit script kijkt hoe lang geleden de laatste run was en start er zelf een als
het te lang stil is. Draait alleen binnen de venstertijden, zodat het 's
nachts niets doet.

    python src/cron_vangnet.py           # checken, zo nodig starten
    python src/cron_vangnet.py --dryrun  # alleen kijken, niets starten
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

# Een run hoort er elke ~30 min te zijn. Pas ingrijpen na 45 min, zodat een
# normale vertraging van GitHub niet meteen een extra run oplevert.
STILTE_GRENS_MIN = 45
VENSTER_START, VENSTER_EIND = 8, 22   # lokale uren waarin de cron hoort te draaien


def main():
    dryrun = "--dryrun" in sys.argv
    token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPO")
    if not token or not repo:
        print("[FOUT] GITHUB_TOKEN of GITHUB_REPO ontbreekt in .env")
        return 1

    h = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    basis = f"https://api.github.com/repos/{repo}/actions/workflows/reprice.yml"

    nu_lokaal = datetime.now()
    if not (VENSTER_START <= nu_lokaal.hour < VENSTER_EIND):
        print(f"[SLAPEN] {nu_lokaal:%H:%M} valt buiten het venster "
              f"{VENSTER_START}:00-{VENSTER_EIND}:00, niets te doen")
        return 0

    r = requests.get(f"{basis}/runs?per_page=1", headers=h, timeout=20)
    if r.status_code != 200:
        print(f"[FOUT] kan runs niet ophalen: {r.status_code}")
        return 1
    runs = r.json().get("workflow_runs", [])
    if not runs:
        print("[FOUT] geen runs gevonden")
        return 1

    laatste = datetime.strptime(runs[0]["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    stil = (datetime.now(timezone.utc) - laatste).total_seconds() / 60

    lokaal = laatste.astimezone()
    print(f"[CHECK] laatste run: {lokaal:%H:%M} lokaal, {stil:.0f} min geleden "
          f"({runs[0]['event']}, {runs[0]['conclusion']})")

    if stil < STILTE_GRENS_MIN:
        print(f"[OK] binnen de grens van {STILTE_GRENS_MIN} min, niets doen")
        return 0

    if dryrun:
        print(f"[DRYRUN] zou nu een inhaalrun starten ({stil:.0f} min stil)")
        return 0

    d = requests.post(f"{basis}/dispatches", headers=h, json={"ref": "main"}, timeout=20)
    if d.status_code == 204:
        print(f"[ACTIE] inhaalrun gestart na {stil:.0f} min stilte")
        return 0
    print(f"[FOUT] starten mislukt: {d.status_code} {d.text[:200]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
