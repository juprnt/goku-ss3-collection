"""Veille quotidienne des nouvelles cartes Son Goku SS3 dans les bases officielles Bandai.

Lancé chaque jour par launchd (voir ../install.sh). Compare les bases officielles
dbs-cardgame.com à ce qui a déjà été vu (~/.local/share/goku-watch/seen.json) :

- Masters : les noms officiels contiennent la forme (« SS3 Son Goku, … »). Une carte Goku
  dont le nom contient SS3 / Super Saiyan 3 et dont le numéro n'est pas au catalogue est
  ajoutée **directement** (aucun doute). Une nouvelle variante officielle (_PR, _SPR…) d'une
  carte connue va dans « Cartes à valider » (correspondance incertaine avec les V.1/V.2 Cardmarket).
- Fusion World : les cartes s'appellent « Son Goku » sans la forme. Chaque nouvelle illustration
  Goku (recto, verso des Leaders, parallèles) passe par le modèle de vision local : écartée
  seulement s'il est sûr d'une forme non dorée (base, Blue, God, Ultra Instinct, SS4) ; sinon
  elle va dans « Cartes à valider » (le modèle confond parfois SS3 et SS1 : on ne s'y fie pas
  pour accepter une carte, seulement pour écarter les cas évidents).

Les séries inconnues sont ajoutées à game_sets. Notification macOS s'il y a du nouveau.

Usage (depuis ai-server/) :
  UV_PROJECT_ENVIRONMENT=~/.local/share/goku-ai-server/venv uv run python tools/watch_bandai.py [--seed] [--dry-run]
  --seed    : marque tout l'existant comme vu, sans rien ajouter (première installation)
  --dry-run : affiche ce qui serait ajouté, sans écrire dans Supabase ni dans seen.json
"""

import asyncio
import datetime as dt
import html
import json
import re
import subprocess
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import find_fw_ss3 as fw  # noqa: E402  (liste, fiches et images Fusion World)
import server  # noqa: E402  (ollama_json, prepare_image, SUPABASE_URL)

KEY_FILE = Path.home() / ".config/goku-backup/secret"  # même clé secrète que la sauvegarde
SEEN_FILE = Path.home() / ".local/share/goku-watch/seen.json"
MASTERS_SEARCH = "https://www.dbs-cardgame.com/us-en/cardlist/index.php?search=true"
MASTERS_IMG = "https://www.dbs-cardgame.com/images/cardlist/cardimg/"
NOT_SS3_FORMS = {"base", "super_saiyan_blue", "super_saiyan_god", "ultra_instinct", "super_saiyan_4"}
TODAY = dt.date.today().strftime("%d/%m/%Y")

RARITY = {"C": "Common", "UC": "Uncommon", "R": "Rare", "SR": "Super Rare", "SCR": "Secret Rare",
          "L": "Leader", "PR": "Promo", "SPR": "Special Rare", "ST": "Starter Rare", "GDR": "God Rare"}

FORM_SCHEMA = {
    "type": "object",
    "properties": {
        "goku_form": {"type": "string", "enum": [
            "base", "super_saiyan_1", "super_saiyan_2", "super_saiyan_3", "super_saiyan_4",
            "super_saiyan_god", "super_saiyan_blue", "ultra_instinct", "other", "not_visible"]},
        "confidence": {"type": "number"},
    },
    "required": ["goku_form", "confidence"],
}
FORM_SYSTEM = """Tu es un expert de Dragon Ball. Sous quelle forme Son Goku apparaît-il sur cette carte ?
Base = cheveux noirs en pointes ; Super Saiyan 1/2 = cheveux dorés hérissés ; Super Saiyan 3 =
cheveux dorés très longs jusqu'au dos, sans sourcils ; Super Saiyan 4 = cheveux noirs longs et
fourrure rouge ; God = cheveux rouges ; Blue = cheveux bleus ; Ultra Instinct = cheveux argentés.
confidence = ta certitude entre 0 et 1."""


def log(msg: str):
    print(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def notify(msg: str):
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Veille Bandai Goku SS3"'],
                   check=False, capture_output=True)


def base_key(number: str) -> str:
    """'BT4-004-R' / 'BT4-004_PR' / 'EB1-43' -> 'BT4-4' (préfixe + numéro sans zéros ni suffixe)."""
    m = re.match(r"([A-Z]+\d*)-0*(\d+)", number or "")
    return f"{m.group(1)}-{m.group(2)}" if m else (number or "")


# ------------------------------------------------------------------ Supabase (clé secrète)

class Supabase:
    def __init__(self, http: httpx.AsyncClient, key: str):
        self.http = http
        self.h = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"):  # ancienne clé service_role (JWT)
            self.h["Authorization"] = f"Bearer {key}"

    async def select(self, table: str, params: dict) -> list:
        r = await self.http.get(f"{server.SUPABASE_URL}/rest/v1/{table}", params=params, headers=self.h)
        r.raise_for_status()
        return r.json()

    async def insert(self, table: str, rows: list, on_conflict: str) -> list:
        if not rows:
            return []
        r = await self.http.post(f"{server.SUPABASE_URL}/rest/v1/{table}", params={"on_conflict": on_conflict},
                                 headers={**self.h, "Prefer": "return=representation,resolution=ignore-duplicates"},
                                 json=rows)
        r.raise_for_status()
        return r.json()


# ------------------------------------------------------------------ Masters

def parse_masters(page: str) -> list[dict]:
    cards = []
    for li in re.findall(r"<li>\s*(<dl class=\"cardListCol.*?)</li>", page, flags=re.S):
        field = lambda cls: [html.unescape(re.sub(r"<[^>]+>", " ", v)).split() for v in
                             re.findall(rf'class="{cls}"[^>]*>(.*?)</d[dt]>', li, flags=re.S)]
        join = lambda parts: " ".join(parts)
        numbers = field("cardNumber")
        if not numbers:
            continue
        img = re.search(r'cardimg/([^"]+\.png)', li)
        series = re.search(r'seriesCol">\s*<dt>Series</dt>\s*<dd>(.*?)</dd>', li, flags=re.S)
        rarity = re.search(r'rarityCol">\s*<dt>Rarity</dt>\s*<dd>(.*?)</dd>', li, flags=re.S)
        chars = re.findall(r'characterCol">\s*<dt>Character</dt>\s*<dd>(.*?)</dd>', li, flags=re.S)
        cards.append({
            "number": join(numbers[0]),
            "names": [join(n) for n in field("cardName")],
            "series": html.unescape(re.sub(r"<br\s*/?>", " ", series.group(1))).strip() if series else "",
            "rarity": html.unescape(rarity.group(1)).strip() if rarity else "",
            "characters": [html.unescape(c).strip() for c in chars],
            "img": img.group(1) if img else None,
        })
    return cards


async def fetch_masters(http: httpx.AsyncClient) -> list[dict]:
    found = {}
    for q in ("SS3", "Super Saiyan 3", "SSJ3"):
        for attempt in range(5):  # le formulaire de recherche Masters est en POST
            try:
                r = await http.post(MASTERS_SEARCH, data={"free": "", "card": q, "category_exp": "",
                                                          "character": "", "btn_search": "search"})
                break
            except httpx.HTTPError:
                await asyncio.sleep(2 * (attempt + 1))
        for c in parse_masters(r.text):
            found[c["number"]] = c
        await asyncio.sleep(1)
    # Goku reconnu par le personnage, ou par le nom quand Bandai n'indique pas de personnage
    # (ex. BT24-138_PR02).
    is_goku = lambda c: (any("Son Goku" in ch and not re.search(r"Jr\.|Black", ch) for ch in c["characters"])
                         or any("Goku" in n and not re.search(r"Goku Black|Jr\.", n) for n in c["names"]))
    return [c for c in found.values()
            if is_goku(c) and any(re.search(r"SS3|Super Saiyan 3|SSJ3", n) for n in c["names"])]


def masters_set_name(series: str) -> str:
    m = re.search(r"[-～~]\s*([^-～~]+?)\s*[-～~]", series)
    name = m.group(1) if m else re.sub(r"^.*?\d+\s*", "", series)
    return name.strip().title().replace("'S", "'s") or series


# ------------------------------------------------------------------ séries (game_sets)

async def ensure_set(sb: Supabase, sets: list, game_slug: str, code: str, name: str, dry: bool) -> str:
    """Renvoie le set_name à utiliser ; crée la série si son code n'est pas encore connu."""
    for s in sets:
        if s["game_slug"] == game_slug and s["display_name"].endswith(f"({code})"):
            return s["set_name"]
    order = max([s["sort_order"] or 0 for s in sets if s["game_slug"] == game_slug] or [0]) + 1
    row = {"game_slug": game_slug, "set_name": name, "display_name": f"{name} ({code})", "sort_order": order}
    log(f"Nouvelle série {game_slug} : {row['display_name']}")
    if not dry:
        await sb.insert("game_sets", [row], "game_slug,set_name")
    sets.append(row)
    return name


# ------------------------------------------------------------------ principal

async def main(seed: bool, dry: bool):
    if not KEY_FILE.exists() or not KEY_FILE.read_text().strip():
        log(f"Clé absente : {KEY_FILE}")
        notify("Clé Supabase absente : veille non effectuée.")
        sys.exit(1)
    seen = json.loads(SEEN_FILE.read_text()) if SEEN_FILE.exists() else {"masters": [], "fw": []}
    seen_masters, seen_fw = set(seen["masters"]), set(seen["fw"])

    async with httpx.AsyncClient(timeout=60, headers={"User-Agent": "Mozilla/5.0 goku-ss3-collection"}) as http:
        sb = Supabase(http, KEY_FILE.read_text().strip())
        catalogue = await sb.select("cards", {"select": "game_slug,card_number,official_image_url"})
        sets = await sb.select("game_sets", {"select": "game_slug,set_name,display_name,sort_order"})
        known_masters = {base_key(c["card_number"]) for c in catalogue if c["game_slug"] == "dbscg-masters"}
        known_imgs = {(c["official_image_url"] or "").rsplit("/", 1)[-1] for c in catalogue}

        # ---- Masters
        masters = await fetch_masters(http)
        new_rows = []
        for c in masters:
            if c["number"] in seen_masters or seed:
                continue
            base_no = c["number"].split("_")[0]
            variant = c["number"][len(base_no) + 1:] if "_" in c["number"] else None
            if not variant and base_key(base_no) in known_masters:
                continue
            code = base_no.split("-")[0]
            rar_abbr = re.search(r"\[(\w+)\]", c["rarity"])
            rar_abbr = rar_abbr.group(1) if rar_abbr else None
            set_name = await ensure_set(sb, sets, "dbscg-masters", code, masters_set_name(c["series"]), dry)
            new_rows.append({
                "game": "DBS-CG", "game_slug": "dbscg-masters", "set_code": code, "set_name": set_name,
                "card_number": base_no + (f"-{rar_abbr}" if rar_abbr else "") + (f"-{variant}" if variant else ""),
                "card_name": " // ".join(c["names"]) + (f" (variante officielle {variant})" if variant else ""),
                "rarity": RARITY.get(rar_abbr, c["rarity"].split("[")[0] or None), "language": "EN",
                "card_type": "COMBAT", "official_image_url": MASTERS_IMG + c["img"] if c["img"] else None,
                "source_url": "https://www.dbs-cardgame.com/us-en/cardlist/",
                "review_status": "pending_review" if variant else "confirmed", "review_source": "bandai-veille",
                "notes": f"Ajoutée automatiquement par la veille Bandai le {TODAY} (série officielle : {c['series']})."
                         + (f" Variante officielle {variant} de {base_no} : à valider, correspondance incertaine "
                            f"avec les versions déjà au catalogue." if variant else ""),
            })

        # ---- Fusion World
        parser = fw.CardListParser()
        parser.feed((await fw.get(http, fw.BASE, params={"search": "true", "q": "Son Goku"})).text)
        fw_cards = [c for c in parser.cards if "Son Goku" in c["name"] and not fw.EXCLUDED_NAMES.search(c["name"])]
        for c in list(fw_cards):
            if "_f" in c["img"]:
                fw_cards.append({**c, "img": c["img"].replace("_f", "_b")})
        fw_uniq = {c["img"]: c for c in fw_cards}
        for img, c in sorted(fw_uniq.items()):
            if img in seen_fw or img in known_imgs or seed:
                continue
            detail = fw.parse_detail((await fw.get(http, fw.BASE + "detail.php", params={"card_no": c["no"]})).text)
            r = await fw.get(http, fw.IMG_BASE + img)
            if r.status_code != 200:
                continue
            try:
                form = await server.ollama_json(FORM_SYSTEM, "Analyse cette carte.", FORM_SCHEMA, [server.prepare_image(r.content)])
            except Exception as e:
                form = {"goku_form": "not_visible", "confidence": 0}
                log(f"Modèle de vision indisponible ({e}) : {img} envoyée en validation sans filtre.")
            if form.get("goku_form") in NOT_SS3_FORMS and (form.get("confidence") or 0) >= 0.9:
                log(f"FW {img} écartée (forme {form['goku_form']}, confiance {form['confidence']}).")
                continue
            code = c["no"].split("-")[0]
            where = detail.get("where") or ""
            set_label = "Promotion Cards" if code == "FP" else re.sub(r"^.*?-\s*|\s*-\s*\[.*$|\s*\[.*$", "", where).strip().title() or code
            set_name = await ensure_set(sb, sets, "dbscg-fusion", code, set_label, dry)
            par = img.rsplit("_p", 1)[1].split(".")[0] if "_p" in img else None
            leader = (detail.get("type") or "").upper() == "LEADER"
            new_rows.append({
                "game": "DBS-CG-FW", "game_slug": "dbscg-fusion", "set_code": code, "set_name": set_name,
                "card_number": c["no"] + (f"-P{par}" if par else ""),
                "card_name": c["name"] + (" (Leader, face éveillée)" if leader and "_b" in img else "")
                             + (f" (Parallèle {par})" if par else ""),
                "rarity": (RARITY.get(detail.get("rarity"), detail.get("rarity")) or "") + (" — Parallèle" if par else "") or None,
                "card_type": "LEADER" if leader else "COMBAT", "color": detail.get("color"), "language": "EN",
                "official_image_url": fw.IMG_BASE + img,
                "source_url": f"{fw.BASE}detail.php?card_no={c['no']}",
                "review_status": "pending_review", "review_source": "bandai-veille",
                "notes": f"Détectée automatiquement par la veille Bandai le {TODAY} : nouvelle illustration de Son Goku. "
                         f"Forme estimée par l'IA locale : {form.get('goku_form')} (confiance {form.get('confidence')}), "
                         "à vérifier sur l'image." + (f" Obtention : {where}." if where else ""),
            })
            await asyncio.sleep(0.3)

        # ---- écriture
        confirmed = [r for r in new_rows if r["review_status"] == "confirmed"]
        pending = [r for r in new_rows if r["review_status"] == "pending_review"]
        for r in new_rows:
            log(f"{'AJOUT' if r['review_status'] == 'confirmed' else 'À VALIDER'} {r['card_number']} — {r['card_name']}")
        if not dry:
            if new_rows:
                await sb.insert("cards", new_rows, "game,set_code,card_number,language")
            SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            SEEN_FILE.write_text(json.dumps({"masters": sorted(seen_masters | {c["number"] for c in masters}),
                                             "fw": sorted(seen_fw | set(fw_uniq))}, indent=1))
        log(f"Veille terminée : {len(masters)} cartes Masters SS3 et {len(fw_uniq)} illustrations Goku Fusion World "
            f"examinées ; {len(confirmed)} ajoutée(s), {len(pending)} à valider{' (simulation)' if dry else ''}"
            f"{' (initialisation)' if seed else ''}.")
        if new_rows and not dry:
            notify(f"{len(confirmed)} nouvelle(s) carte(s) Goku SS3 ajoutée(s), {len(pending)} à valider dans l'app.")


if __name__ == "__main__":
    try:
        asyncio.run(main(seed="--seed" in sys.argv, dry="--dry-run" in sys.argv))
    except Exception as e:
        log(f"Échec de la veille : {e!r}")
        notify("La veille Bandai a échoué. Voir le journal.")
        sys.exit(1)
