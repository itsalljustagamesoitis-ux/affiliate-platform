"""
Backfill price_band for products that have an empty value.
Uses brand lookup + title signals. Does not overwrite existing values.

Usage:
    python3 scripts/backfill-price-band.py --site /path/to/site [--dry-run]
"""
import re
import sys
import argparse
from pathlib import Path

# pip install pyyaml ruamel.yaml
from ruamel.yaml import YAML

# ── Brand tables ──────────────────────────────────────────────────────────────
PREMIUM_BRANDS = {
    'specialized', 'trek', 'giant', 'cannondale', 'yamaha', 'husqvarna', 'scott',
    'riese', 'haibike', 'merida', 'bulls', 'cube', 'focus', 'kalkhoff', 'stromer',
    'pivot', 'orbea', 'bianchi', 'bosch', 'brose', 'shimano', 'fazua',
    'nox', 'grace bikes', 'weyless',
}

MID_BRANDS = {
    'rad power', 'radpower', 'aventon', 'heybike', 'lectric', 'ride1up',
    'juiced', 'addmotor', 'hiboy', 'pedego', 'sixthreezero', 'cowboy', 'vanmoof',
    'schwinn', 'retrospec', 'ariel rider', 'biktrix', 'espin', 'rambo', 'ridon',
    'mokwheel', 'velotric', 'fiido', 'engwe', 'lankeleisi', 'cybervelo', 'lumos',
    'kemimoto', 'lamicall', 'weize', 'creek', 'vevor', 'mobility', 'enjoy mfg',
    'macfox', 'urlife', 'mooncool', 'freesky', 'actbest', 'flasld', 'pexmor',
    'aipas', 'narrak', 'happyrun', 'tst', 'himiway', 'ecotric', 'ancheer',
    'speedrid', 'nakto', 'swagtron', 'nireeka', 'bintelli', 'biktrix',
    'magnum', 'charge', 'super73', 'onguard', 'kryptonite', 'frog',
}

BUDGET_BRANDS = {
    'gotrax', 'jasion', 'vivi', 'euy', 'razor', 'funhang', 'eskute',
    'isinwheel', 'misodo', 'qlife', 'puckipuppy', 'euybike', 'toocust',
    'extral', 'gymax', 'actbest',
}

# Title keywords that indicate an accessory regardless of brand → mid
ACCESSORY_TERMS = [
    'charger', 'adapter', 'rack', 'basket', 'cover', 'cargo net', 'bag',
    'helmet', 'lock', 'pump', 'mirror', 'light', 'bell', 'kickstand',
    'mount', 'phone mount', 'water bottle', 'harness', 'trailer', 'liner',
    'panniers', 'fender', 'mudguard', 'cable', 'grease', 'lube', 'tool',
    'inner tube', 'tire', 'tyre', 'brake pad', 'chain', 'sprocket', 'derailleur',
    'display', 'screen protector', 'reflector', 'pedals', 'grips', 'saddle',
    'seat', 'handlebar', 'stem', 'fork', 'gift card',
]

WATT_RE = re.compile(r'\b(\d[\d,]*)\s*w(?:att)?(?:s\b|\b)', re.IGNORECASE)


def classify(product_id: str, p: dict) -> str:
    brand = (p.get('brand') or '').lower().strip()
    title = (p.get('title') or p.get('name') or '').lower()
    hub   = (p.get('hub') or '').lower()

    # Accessories first — hub signal
    if hub in ('accessories-and-gear',):
        # Even accessories hubs can have premium items, but default mid
        for pb, brands in [('premium', PREMIUM_BRANDS), ('mid', MID_BRANDS), ('budget', BUDGET_BRANDS)]:
            if any(b in brand for b in brands):
                return pb
        return 'mid'

    # Accessories by title
    for term in ACCESSORY_TERMS:
        if term in title:
            return 'mid'

    # E-bike product signal — premium only applies to actual e-bike/cycling products
    EBIKE_TERMS = ('bike', 'bicycle', 'e-bike', 'ebike', 'cycle', 'cycling', 'mtb',
                   'electric bike', 'cargo bike', 'gravel', 'commuter bike')
    is_ebike_product = any(t in title for t in EBIKE_TERMS) or hub.startswith('brand-')

    # Premium brands — only for actual e-bike products
    if any(b in brand for b in PREMIUM_BRANDS):
        return 'premium' if is_ebike_product else 'mid'

    # Mid and budget brand lookup
    for pb, brands in [('mid', MID_BRANDS), ('budget', BUDGET_BRANDS)]:
        if any(b in brand for b in brands):
            return pb

    # Budget hub
    if hub == 'budget-and-price-roundups':
        return 'budget'

    # Unbranded / unknown brand — use wattage heuristic
    # Generic unbranded e-bikes on Amazon are almost always budget
    if brand in ('unbranded', '', 'generic'):
        watts = [int(m.group(1).replace(',', '')) for m in WATT_RE.finditer(title)]
        if watts:
            max_w = max(watts)
            if max_w >= 1000 or max_w <= 400:
                return 'budget'
        return 'budget'

    # Known accessory-only brand signals
    if brand in ('ac', 'dog', 'pcs', 'enjoy'):
        return 'mid'

    # Unknown brand → mid (benefit of doubt)
    return 'mid'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', required=True, help='Path to site root')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    products_path = Path(args.site) / 'content/products/products.yaml'
    if not products_path.exists():
        print(f'ERROR: {products_path} not found', file=sys.stderr)
        sys.exit(1)

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096

    with open(products_path) as f:
        products = yaml.load(f)

    filled = 0
    band_counts = {'budget': 0, 'mid': 0, 'premium': 0}

    for product_id, p in products.items():
        if p.get('price_band'):
            continue
        band = classify(product_id, p)
        band_counts[band] += 1
        filled += 1
        if not args.dry_run:
            p['price_band'] = band

    print(f'Products backfilled: {filled}')
    print(f'  budget:  {band_counts["budget"]}')
    print(f'  mid:     {band_counts["mid"]}')
    print(f'  premium: {band_counts["premium"]}')

    if args.dry_run:
        print('(dry run — no changes written)')
        return

    with open(products_path, 'w') as f:
        yaml.dump(products, f)

    print(f'Written: {products_path}')


if __name__ == '__main__':
    main()
