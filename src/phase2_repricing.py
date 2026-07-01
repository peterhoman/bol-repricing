#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import io
import csv
import re
import json
import time
import base64
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

from dotenv import load_dotenv

load_dotenv()

class RepricingEngine:
    """Main repricing engine for Bol.com buybox optimization."""

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.products = {}
        self.price_history = {}
        self.bliving_klantprijzen = {}
        self.load_products()
        self.load_bliving_feed()

    def load_products(self):
        """Load products from CSV (330 without buybox) via GitHub."""
        print(f"\n[LOAD] Reading CSV from GitHub...")

        try:
            # Download from GitHub
            response = requests.get(self.csv_path, timeout=30)
            if response.status_code != 200:
                print(f"   Error: {response.status_code}")
                return False

            # Parse CSV from response
            lines = response.text.split('\n')
            reader = csv.DictReader(lines, delimiter=';')

            for row in reader:
                try:
                    ean = row.get('EAN', '').strip()
                    if not ean:
                        continue

                    product_name = row.get('Productnaam', '')[:50]

                    self.products[ean] = {
                        'ean': ean,
                        'name': product_name,
                        'current_price': None,
                        'has_buybox': False,
                        'last_check': None
                    }
                except:
                    pass

            print(f"   Loaded {len(self.products)} products")
            return True
        except Exception as e:
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_bliving_feed(self):
        """Download B-Living XML feed and extract klantprijzen."""
        print(f"\n[FEED] Downloading B-Living feed...")

        feed_url = "https://www.b-living.eu/feeds/product-feed-15003253-bbed70ea1f95308232732fe3b662e36f2fab51359cce3fc9ff7e33cac2ef9b07.xml"

        try:
            response = requests.get(feed_url, timeout=30)
            if response.status_code != 200:
                print(f"   Error: {response.status_code}")
                return False

            root = ET.fromstring(response.content)

            for product in root.findall('product'):
                try:
                    ean = product.findtext('ean', '').strip()
                    klantprijs_text = product.findtext('klantprijs', '0').strip()
                    klantprijs = float(klantprijs_text)

                    self.bliving_klantprijzen[ean] = klantprijs
                except:
                    pass

            print(f"   Loaded {len(self.bliving_klantprijzen)} klantprijzen from B-Living")
            return True
        except Exception as e:
            print(f"   Error: {e}")
            return False

    def calculate_normal_price(self, klantprijs: float) -> float:
        """Calculate normal price using Channable formula for this account."""
        if klantprijs < 4:
            # (klantprijs + 2) × 2.4 + 8
            return round(((klantprijs + 2) * 2.4) + 8, 2)
        else:
            # klantprijs × 2.4 + 8
            return round((klantprijs * 2.4) + 8, 2)

    def calculate_minimum_price(self, klantprijs: float) -> float:
        """Calculate minimum price (klantprijs × 1.9 + 8)."""
        return round((klantprijs * 1.9) + 8, 2)

    def calculate_klantprijs_for_target_price(self, target_price: float) -> float:
        """
        Calculate the klantprijs needed to make Channable produce target_price
        as the selling price.

        Channable uses:
          if klantprijs < 4: price = (klantprijs + 2) * 2.4 + 8
          else: price = klantprijs * 2.4 + 8

        We solve for klantprijs directly from the DESIRED target_price
        (not from a "reduction relative to the original price" - that was
        a bug, since it ignored all previous iterations and always reset
        back to "original price - 0.50").
        """
        # Try the >= 4 branch first (most products fall here)
        candidate = (target_price - 8) / 2.4
        if candidate >= 4:
            return round(max(candidate, 0), 2)

        # Otherwise use the < 4 branch
        candidate_low = ((target_price - 8) / 2.4) - 2
        return round(max(candidate_low, 0), 2)

    def generate_reprice_xml(self, output_path: str, adjustments: dict) -> bool:
        """
        Generate XML for Channable import.

        Adjustments dict contains EAN -> NEW_KLANTPRIJS
        Channable will recalculate selling price using its formula
        """
        print(f"\n[XML] Generating repricing XML...")

        try:
            # Download original B-Living feed
            feed_url = "https://www.b-living.eu/feeds/product-feed-15003253-bbed70ea1f95308232732fe3b662e36f2fab51359cce3fc9ff7e33cac2ef9b07.xml"
            response = requests.get(feed_url, timeout=30)
            root = ET.fromstring(response.content)

            # Modify klantprijs for adjusted articles
            for product in root.findall('product'):
                ean = product.findtext('ean', '').strip()

                if ean in adjustments:
                    # adjustments[ean] is NEW KLANTPRIJS
                    klantprijs_elem = product.find('klantprijs')
                    if klantprijs_elem is not None:
                        klantprijs_elem.text = f"{adjustments[ean]:.2f}"

            # Write XML
            tree = ET.ElementTree(root)
            tree.write(output_path, encoding='utf-8', xml_declaration=True)

            print(f"   Generated: {output_path}")
            print(f"   Articles adjusted: {len(adjustments)}")
            return True
        except Exception as e:
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def upload_to_github(self, file_path: str, github_filename: str = "repricing_current.xml") -> bool:
        """
        Upload file to GitHub repo via Contents API using a Personal Access Token.
        Always overwrites the SAME filename, so the Channable import URL never changes.
        """
        print(f"\n[GITHUB] Uploading {github_filename}...")

        github_token = os.getenv("GITHUB_TOKEN")
        github_repo = os.getenv("GITHUB_REPO")

        if not github_token or not github_repo:
            print("   Error: GITHUB_TOKEN or GITHUB_REPO not set in .env")
            return False

        api_url = f"https://api.github.com/repos/{github_repo}/contents/{github_filename}"
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json"
        }

        try:
            with open(file_path, 'rb') as f:
                content_b64 = base64.b64encode(f.read()).decode('utf-8')

            # Get existing file's SHA (required by GitHub API to update a file)
            sha = None
            get_response = requests.get(api_url, headers=headers, timeout=15)
            if get_response.status_code == 200:
                sha = get_response.json().get('sha')

            payload = {
                "message": f"Update repricing feed {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "content": content_b64
            }
            if sha:
                payload["sha"] = sha

            put_response = requests.put(api_url, headers=headers, json=payload, timeout=30)

            if put_response.status_code in (200, 201):
                print(f"   Uploaded successfully!")
                return True
            else:
                print(f"   Error {put_response.status_code}: {put_response.text[:300]}")
                return False
        except Exception as e:
            print(f"   Error: {e}")
            return False

    def upload_json_to_github(self, data: dict, github_filename: str) -> bool:
        """Upload a small JSON state file to GitHub (used to remember progress between runs)."""
        content_b64 = base64.b64encode(json.dumps(data, indent=2).encode('utf-8')).decode('utf-8')

        github_token = os.getenv("GITHUB_TOKEN")
        github_repo = os.getenv("GITHUB_REPO")
        if not github_token or not github_repo:
            print("   Error: GITHUB_TOKEN or GITHUB_REPO not set in .env")
            return False

        api_url = f"https://api.github.com/repos/{github_repo}/contents/{github_filename}"
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json"
        }

        try:
            sha = None
            get_response = requests.get(api_url, headers=headers, timeout=15)
            if get_response.status_code == 200:
                sha = get_response.json().get('sha')

            payload = {
                "message": f"Update {github_filename} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "content": content_b64
            }
            if sha:
                payload["sha"] = sha

            put_response = requests.put(api_url, headers=headers, json=payload, timeout=30)
            return put_response.status_code in (200, 201)
        except Exception as e:
            print(f"   Error uploading {github_filename}: {e}")
            return False

    def load_last_published_klantprijzen(self) -> dict:
        """
        Fetch the currently-published repricing_current.xml from GitHub and
        extract the klantprijs that was last used per EAN. This lets a fresh,
        stateless run (e.g. a GitHub Actions run with no memory of previous
        runs) continue reducing prices from where the last run left off.
        """
        url = "https://raw.githubusercontent.com/peterhoman/bol-repricing/main/repricing_current.xml"
        result = {}
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                return result
            root = ET.fromstring(r.content)
            for product in root.findall('product'):
                ean = product.findtext('ean', '').strip()
                kp_text = product.findtext('klantprijs', '').strip()
                if ean and kp_text:
                    try:
                        result[ean] = float(kp_text)
                    except ValueError:
                        pass
        except Exception as e:
            print(f"   [WARN] Could not load last published klantprijzen: {e}")
        return result

    def load_state(self) -> dict:
        """Fetch state.json from GitHub (tracks the date of the last repricing run)."""
        url = "https://raw.githubusercontent.com/peterhoman/bol-repricing/main/state.json"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def check_buybox(self, ean: str, session: requests.Session, seller_name: str = "Tiptopshop") -> dict:
        """
        Check the LIVE buybox status for one EAN by reading Bol.com's own
        public product page (no API key needed - just the structured
        schema.org JSON-LD data that's on every product page for SEO).

        1. Search bol.com for the EAN to find the product page URL.
        2. Fetch that product page and parse its JSON-LD blocks.
        3. Find the variant matching this EAN (gtin13) and read its
           offers.seller.name - that's whoever currently "wins" the buybox.

        Returns: {'found': bool, 'has_buybox': bool, 'price': float, 'seller': str}
        or {'found': False, 'error': '...'} if anything didn't resolve.
        """
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        try:
            search_r = session.get(f"https://www.bol.com/nl/nl/s/?searchtext={ean}", headers=headers, timeout=15)
            if search_r.status_code != 200:
                return {"found": False, "error": f"search status {search_r.status_code}"}

            urls = re.findall(r'"(/nl/nl/p/[^"]+)"', search_r.text)
            if not urls:
                return {"found": False, "error": "no product url in search results"}
            product_url = "https://www.bol.com" + urls[0]

            product_r = session.get(product_url, headers=headers, timeout=15)
            if product_r.status_code != 200:
                return {"found": False, "error": f"product page status {product_r.status_code}"}

            blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', product_r.text, re.DOTALL)
            for block in blocks:
                try:
                    data = json.loads(block)
                except Exception:
                    continue
                candidates = data.get("hasVariant", [data]) if isinstance(data, dict) else []
                for c in candidates:
                    if c.get("gtin13") == ean:
                        offers = c.get("offers", {})
                        seller = offers.get("seller", {}).get("name", "")
                        return {
                            "found": True,
                            "price": offers.get("price"),
                            "seller": seller,
                            "has_buybox": seller.lower() == seller_name.lower(),
                        }
            return {"found": False, "error": "ean not found in JSON-LD"}
        except Exception as e:
            return {"found": False, "error": str(e)}

    def run_single_iteration_stateless(self, check_buybox_live: bool = True) -> tuple:
        """
        Stateless version of run_iteration, meant to be triggered by an external
        scheduler (e.g. GitHub Actions cron) where no Python process stays running
        and no in-memory state survives between runs.

        Instead of tracking 'current_price' in memory, it reads the klantprijs
        values from the LAST PUBLISHED repricing_current.xml as the starting
        point for one more €0.50 reduction step. If it's a new calendar day
        (tracked via state.json), it resets to the fresh B-Living klantprijs
        instead of continuing yesterday's reduced prices.

        If check_buybox_live is True, each EAN's actual buybox status is checked
        against Bol.com's public product page before deciding what to do:
          - Has buybox already -> HOLD the current price (don't reduce further,
            and don't bump back up either - jumping back to the normal price
            could immediately lose the buybox again to whoever is still low).
          - Does not have buybox -> reduce by another €0.50 as before.

        Returns: (adjustments dict EAN->new_klantprijs, new_state dict, buybox_won list)
        """
        from datetime import date
        today_str = date.today().isoformat()

        state = self.load_state()
        is_new_day = state.get('date') != today_str

        last_published = {} if is_new_day else self.load_last_published_klantprijzen()

        print(f"\n[STATELESS] New day reset: {is_new_day} (last state date: {state.get('date')})")

        session = requests.Session()

        adjustments = {}
        at_minimum = 0
        buybox_won = []
        buybox_checks_failed = 0

        for i, ean in enumerate(self.products):
            if ean not in self.bliving_klantprijzen:
                continue

            original_klantprijs = self.bliving_klantprijzen[ean]
            minimum_price = self.calculate_minimum_price(original_klantprijs)

            # Baseline: continue from last published klantprijs, or reset fresh on a new day
            baseline_klantprijs = last_published.get(ean, original_klantprijs)

            has_buybox = False
            if check_buybox_live:
                result = self.check_buybox(ean, session)
                if result.get("found"):
                    has_buybox = result.get("has_buybox", False)
                    if has_buybox:
                        buybox_won.append(ean)
                else:
                    buybox_checks_failed += 1
                time.sleep(0.3)  # be polite to bol.com, avoid hammering their servers

            if has_buybox:
                # Already winning - hold the price steady, don't reduce further
                # (and don't jump back up, that could lose the buybox again)
                adjustments[ean] = baseline_klantprijs
                continue

            current_selling_price = self.calculate_normal_price(baseline_klantprijs)
            new_selling_price = current_selling_price - 0.50
            if new_selling_price < minimum_price:
                new_selling_price = minimum_price
                at_minimum += 1

            adjustments[ean] = self.calculate_klantprijs_for_target_price(new_selling_price)

        print(f"Adjustments: {len(adjustments)} articles")
        print(f"At minimum price: {at_minimum} articles")
        if check_buybox_live:
            print(f"Buybox already won (held steady): {len(buybox_won)} articles")
            print(f"Buybox check failed (treated as not-won): {buybox_checks_failed} articles")

        new_state = {"date": today_str}
        return adjustments, new_state, buybox_won

    def run_iteration(self, iteration: int) -> dict:
        """
        Run one iteration of repricing.

        For each article without buybox: reduce SELLING PRICE by €0.50
        Never go below minimum (× 1.9 + 8.5)

        Returns: dict of EAN -> NEW_KLANTPRIJS (for XML, Channable will recalculate)
        """
        print(f"\n{'='*70}")
        print(f"ITERATION {iteration} - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*70}")

        adjustments = {}
        articles_to_adjust = 0
        at_minimum = 0

        for ean, product in self.products.items():
            if ean not in self.bliving_klantprijzen:
                continue

            klantprijs = self.bliving_klantprijzen[ean]
            normal_price = self.calculate_normal_price(klantprijs)
            minimum_price = self.calculate_minimum_price(klantprijs)

            # All articles in this list don't have buybox
            has_buybox = False

            if not has_buybox:
                # Calculate new SELLING PRICE: current - €0.50
                current_price = product.get('current_price') or normal_price
                new_selling_price = current_price - 0.50

                # Check minimum
                if new_selling_price < minimum_price:
                    new_selling_price = minimum_price
                    action = "AT_MINIMUM"
                    at_minimum += 1
                else:
                    action = "REDUCED"

                # INVERSE: calculate new klantprijs that produces this selling price
                new_klantprijs = self.calculate_klantprijs_for_target_price(new_selling_price)

                # Store NEW KLANTPRIJS for XML (Channable will recalculate price)
                adjustments[ean] = new_klantprijs

                product['current_price'] = new_selling_price
                articles_to_adjust += 1

                if articles_to_adjust <= 5:  # Show first 5
                    print(f"  {ean}: €{current_price:.2f} → €{new_selling_price:.2f} (klantprijs: {klantprijs:.2f} → {new_klantprijs:.2f})")

        print(f"\nAdjustments: {articles_to_adjust} articles")
        print(f"At minimum price: {at_minimum} articles")

        return adjustments

    def run_repricing_loop(self, max_iterations: int = 999):
        """
        Main loop: run repricing iterations until buybox or manual stop.

        Between iterations: wait 5 minutes (Bol.com processing time)
        """
        print("\n" + "="*70)
        print("FASE 2: REPRICING LOOP (Kat-en-Muis Spel)")
        print("="*70)
        print("\nInstructions:")
        print("  1. Each iteration generates an XML file")
        print("  2. Upload XML to GitHub")
        print("  3. Import in Channable (via GitHub raw URL)")
        print("  4. Wait 5 minutes for Bol.com to process")
        print("  5. Next iteration runs automatically")
        print("  6. Press Ctrl+C to stop")
        print("="*70)

        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1

                # Generate adjustments
                adjustments = self.run_iteration(iteration)

                # Generate XML (always same local filename - no local clutter either)
                xml_path = "C:\\Users\\Avantius\\Documents\\bol-repricing\\output\\repricing_current.xml"

                # Create output dir if needed
                Path("C:\\Users\\Avantius\\Documents\\bol-repricing\\output").mkdir(exist_ok=True)

                self.generate_reprice_xml(xml_path, adjustments)

                # Auto-upload to GitHub (always same filename, Channable URL never changes)
                self.upload_to_github(xml_path, "repricing_current.xml")

                print(f"\n✓ XML ready: repricing_current.xml (iteration {iteration})")
                print(f"✓ Uploaded to GitHub as repricing_current.xml")
                print(f"✓ Next iteration in 80 minutes (1h 20m)...")
                print(f"\nWaiting... (press Ctrl+C to stop)")

                # Wait 80 minutes (1 hour 20 minutes = 4800 seconds)
                time.sleep(4800)  # 80 minutes

        except KeyboardInterrupt:
            print(f"\n\n[STOP] Repricing loop stopped by user")
            print(f"Total iterations: {iteration}")
            return True

        return True

if __name__ == "__main__":
    # GitHub raw URL for daily CSV (always the same filename - Peter overwrites this file each morning)
    csv_url = "https://raw.githubusercontent.com/peterhoman/bol-repricing/main/bolcom_productinformatie.csv"

    engine = RepricingEngine(csv_url)

    if not engine.products:
        print("\n[ERROR] No products loaded from CSV")
        sys.exit(1)

    if not engine.bliving_klantprijzen:
        print("\n[ERROR] No klantprijzen loaded from B-Living feed")
        sys.exit(1)

    # Count matching products
    matching = sum(1 for ean in engine.products if ean in engine.bliving_klantprijzen)

    print(f"\n[INFO] Loaded {len(engine.products)} products from CSV")
    print(f"[INFO] Loaded {len(engine.bliving_klantprijzen)} klantprijzen from B-Living")
    print(f"[INFO] Matching products: {matching}")

    # START REAL LOOP!
    print(f"\n[GO!] Starting repricing loop...")
    print(f"Iterations every 2 minutes until buybox or manual stop (Ctrl+C)")
    engine.run_repricing_loop()
