"""Prépare la revue visuelle des cartes Son Goku de Fusion World (base officielle Bandai).

Dans Fusion World, les cartes s'appellent simplement « Son Goku » : la forme (SS3...) ne se
voit que sur l'illustration. Ce script :
  1. récupère toutes les cartes « Son Goku » de dbs-cardgame.com/fw (recto, verso des
     Leaders, versions parallèles _p1, _p2...), en excluant les formes qui ne peuvent pas
     être SS3 (enfant, singe géant, Black, Jr.) ;
  2. lit la fiche de chaque numéro (rareté, couleur, type, où l'obtenir) ;
  3. télécharge les illustrations et les assemble en planches numérotées (24 par planche)
     pour repérer les Goku SS3 à l'œil.

Le tri automatique par le modèle de vision local a été essayé (23/09/2026) : trop de faux
négatifs (ST01-044, SS3 évident, classé SS1), et le mode « réflexion » prend > 10 min par
image. La revue visuelle des planches reste la méthode fiable.

Usage (depuis ai-server/) :
  UV_PROJECT_ENVIRONMENT=~/.local/share/goku-ai-server/venv uv run python tools/find_fw_ss3.py <dossier>
→ <dossier>/index.json (une entrée par illustration) et <dossier>/sheet_XX.jpg
"""

import asyncio
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

BASE = "https://www.dbs-cardgame.com/fw/en/cardlist/"
IMG_BASE = "https://www.dbs-cardgame.com/fw/images/cards/card/en/"
EXCLUDED_NAMES = re.compile(r"Childhood|Great Ape|Black|Jr\.")


class CardListParser(HTMLParser):
    """Extrait (numéro, nom, image) des <li class="cardItem"> de la liste."""

    def __init__(self):
        super().__init__()
        self.cards, self._in_item, self._no = [], False, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "li" and a.get("class") == "cardItem":
            self._in_item = True
        elif self._in_item and tag == "a" and "card_no=" in (a.get("data-src") or ""):
            self._no = a["data-src"].split("card_no=")[1]
        elif self._in_item and tag == "img" and self._no:
            self.cards.append({"no": self._no, "name": a.get("alt", "").split(" ", 1)[-1],
                               "img": a.get("data-src", "").split("/")[-1]})
            self._in_item, self._no = False, None


def parse_detail(html: str) -> dict:
    """Fiche carte : 1re ligne = numéro, 2e = rareté ; puis paires libellé / valeur."""
    html = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S | re.I)
    lines = [l.strip() for l in re.sub(r"<[^>]+>", "\n", html).splitlines() if l.strip()]
    start = next((i for i, l in enumerate(lines) if re.fullmatch(r"[A-Z]+\d*-\d+", l)), 0)
    value = lambda k: next((lines[i + 1] for i, l in enumerate(lines) if l == k and i + 1 < len(lines)), None)
    return {"rarity": lines[start + 1] if start + 1 < len(lines) else None, "type": value("Card type"),
            "color": value("Color"), "where": value("Where to get it")}


async def get(http: httpx.AsyncClient, url: str, **kw) -> httpx.Response:
    """Le serveur Bandai coupe parfois les connexions : on réessaie en espaçant."""
    for attempt in range(5):
        try:
            return await http.get(url, **kw)
        except httpx.HTTPError:
            await asyncio.sleep(2 * (attempt + 1))
    raise RuntimeError(f"échec : {url}")


def contact_sheets(out: Path, entries: list[dict], cols: int = 6, rows: int = 4, w: int = 200, h: int = 280):
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 15)
    per = cols * rows
    for s in range(0, len(entries), per):
        sheet = Image.new("RGB", (w * cols, (h + 20) * rows), "white")
        draw = ImageDraw.Draw(sheet)
        for k, e in enumerate(entries[s:s + per]):
            im = Image.open(out / e["img"]).convert("RGB")
            im.thumbnail((w, h))
            x, y = (k % cols) * w, (k // cols) * (h + 20)
            sheet.paste(im, (x + (w - im.width) // 2, y + 20))
            draw.text((x + 4, y + 2), f"#{s + k} {e['img'].rsplit('.', 1)[0]}", fill="black", font=font)
        sheet.save(out / f"sheet_{s // per:02d}.jpg", quality=80)


async def main(out_dir: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=60, headers={"User-Agent": "Mozilla/5.0 goku-ss3-collection"}) as http:
        parser = CardListParser()
        parser.feed((await get(http, BASE, params={"search": "true", "q": "Son Goku"})).text)
        cards = [c for c in parser.cards if "Son Goku" in c["name"] and not EXCLUDED_NAMES.search(c["name"])]
        for c in list(cards):  # Leaders : ajouter le verso (souvent la forme transformée)
            if "_f" in c["img"]:
                cards.append({**c, "img": c["img"].replace("_f", "_b")})
        uniq = {c["img"]: c for c in cards}

        details = {}
        for no in sorted({c["no"] for c in uniq.values()}):
            details[no] = parse_detail((await get(http, BASE + "detail.php", params={"card_no": no})).text)
            await asyncio.sleep(0.15)

        entries = []
        for img, c in sorted(uniq.items()):
            if not (out / img).exists():
                r = await get(http, IMG_BASE + img)
                if r.status_code != 200:
                    print(f"image absente : {img} ({r.status_code})")
                    continue
                (out / img).write_bytes(r.content)
                await asyncio.sleep(0.1)
            entries.append({**c, **details[c["no"]], "img_url": IMG_BASE + img})

    (out / "index.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1))
    contact_sheets(out, entries)
    print(f"{len(entries)} illustrations, {len(details)} numéros → {out}/sheet_*.jpg")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "fw_goku"))
