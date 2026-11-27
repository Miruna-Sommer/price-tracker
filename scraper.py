"""Descărcarea paginilor și extragerea prețului (requests + BeautifulSoup).

Strategia de extragere, în ordine:
  1. JSON-LD (schema.org/Product) - date structurate puse de magazin pentru
     motoarele de căutare; cea mai stabilă sursă.
  2. Meta tag-uri / microdata (og:price:amount, itemprop="price").
  3. Selectori CSS specifici fiecărui magazin (SITE_SELECTORS) - ultima
     soluție, pentru că se strică atunci când magazinul își schimbă designul.
"""

import json
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = "PriceTrackerStudent/1.0 (proiect educational; curs web scraping)"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml",
}
TIMEOUT = 15  # secunde

# Selectori de rezervă pe domeniu: (selector nume, selector preț).
# Se verifică și se actualizează cu DevTools (F12 -> Inspect) pe pagina produsului.
SITE_SELECTORS = {
    "emag.ro": ("h1.page-title", "p.product-new-price"),
    "pcgarage.ro": ("h1", ".ps_sell_price .price_num"),
    "libris.ro": ("h1", ".price-prp-pr, .pr-pret-redus"),
    "carturesti.ro": ("h1.titluProdus", ".pretProdus"),
}


class ScrapeError(Exception):
    """Pagina nu a putut fi descărcată sau prețul nu a fost găsit."""


@dataclass
class ProductData:
    name: str
    price: float
    currency: str = "RON"
    available: bool = True
    source: str = ""  # metoda care a găsit prețul: json-ld / meta / css


# ---------------------------------------------------------------- preț -> float

def parse_price(text) -> Optional[float]:
    """Transformă "1.299,99 Lei", "1 299,99", "1299.99" sau 1299.99 în float."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)

    s = re.sub(r"[^\d.,]", "", str(text))
    s = s.strip(".,")
    if not s or not any(c.isdigit() for c in s):
        return None

    if "." in s and "," in s:
        # Ultimul separator apărut este cel zecimal.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # 1.299,99
        else:
            s = s.replace(",", "")                      # 1,299.99
    elif "," in s:
        head, _, tail = s.rpartition(",")
        if len(tail) in (1, 2) and "," not in head:
            s = head + "." + tail                       # 299,99
        else:
            s = s.replace(",", "")                      # 1,299
    elif "." in s:
        head, _, tail = s.rpartition(".")
        if len(tail) == 3 or "." in head:
            s = s.replace(".", "")                      # 1.299 (mii, format RO)
    try:
        return float(s)
    except ValueError:
        return None


# ------------------------------------------------------------------ descărcare

_robots_cache = {}
_last_request = {}


def allowed_by_robots(url: str) -> bool:
    """Verifică robots.txt al site-ului (rezultatul e ținut în cache pe domeniu)."""
    parts = urlparse(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots_cache:
        rp = RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
            else:
                rp.parse([])  # fără robots.txt => nimic interzis
        except requests.RequestException:
            rp.parse([])
        _robots_cache[base] = rp
    return _robots_cache[base].can_fetch(USER_AGENT, url)


def fetch(url: str, delay: float = 3.0, retries: int = 2) -> str:
    """Descarcă HTML-ul paginii, politicos: robots.txt, pauză între cereri, retry."""
    if not allowed_by_robots(url):
        raise ScrapeError("robots.txt nu permite accesarea acestei pagini")

    domain = urlparse(url).netloc
    wait = delay - (time.time() - _last_request.get(domain, 0))
    if wait > 0:
        time.sleep(wait)

    last_error = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            _last_request[domain] = time.time()
            if r.status_code == 200:
                r.encoding = r.encoding or r.apparent_encoding
                return r.text
            last_error = f"HTTP {r.status_code}"
            if r.status_code in (403, 429, 503):
                last_error += " (posibil blocaj anti-bot)"
            if r.status_code in (403, 404):
                break  # nu are rost să reîncercăm
        except requests.RequestException as e:
            last_error = str(e)
        time.sleep(delay * (attempt + 1))  # backoff
    raise ScrapeError(f"Nu am putut descărca pagina: {last_error}")


# --------------------------------------------------------------------- parsare

def _iter_jsonld(node):
    """Parcurge recursiv structura JSON-LD (liste, @graph) și întoarce dict-urile."""
    if isinstance(node, list):
        for item in node:
            yield from _iter_jsonld(item)
    elif isinstance(node, dict):
        yield node
        if "@graph" in node:
            yield from _iter_jsonld(node["@graph"])


def _from_jsonld(soup) -> Optional[ProductData]:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for obj in _iter_jsonld(data):
            types = obj.get("@type", [])
            types = types if isinstance(types, list) else [types]
            if "Product" not in types:
                continue
            offers = obj.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            spec = offers.get("priceSpecification")
            if isinstance(spec, list):
                spec = spec[0] if spec else {}
            if not isinstance(spec, dict):
                spec = {}
            raw = offers.get("price")
            if raw in (None, ""):
                raw = offers.get("lowPrice")   # AggregateOffer
            if raw in (None, ""):
                raw = spec.get("price")
            price = parse_price(raw)
            if price is None:
                continue
            availability = str(offers.get("availability", "InStock"))
            return ProductData(
                name=str(obj.get("name", "")).strip(),
                price=price,
                currency=offers.get("priceCurrency", "RON"),
                available="OutOfStock" not in availability,
                source="json-ld",
            )
    return None


def _from_meta(soup) -> Optional[ProductData]:
    candidates = [
        soup.find("meta", property="product:price:amount"),
        soup.find("meta", property="og:price:amount"),
        soup.find(attrs={"itemprop": "price"}),
    ]
    for tag in candidates:
        if tag is None:
            continue
        price = parse_price(tag.get("content") or tag.get_text())
        if price is not None:
            title = soup.find("meta", property="og:title")
            name = title.get("content", "") if title else ""
            return ProductData(name=name.strip(), price=price, source="meta")
    return None


def _from_css(soup, url) -> Optional[ProductData]:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    for site, (name_sel, price_sel) in SITE_SELECTORS.items():
        if not domain.endswith(site):
            continue
        tag = soup.select_one(price_sel)
        if tag is None:
            return None
        # Unele magazine (ex. eMAG) pun zecimalele în <sup>: 1.299<sup>99</sup>
        sup = tag.find("sup")
        if sup is not None:
            decimals = sup.get_text(strip=True)
            sup.extract()
            price = parse_price(f"{tag.get_text(strip=True).rstrip(',.')},{decimals}")
        else:
            price = parse_price(tag.get_text(" ", strip=True))
        if price is None:
            return None
        name_tag = soup.select_one(name_sel)
        name = name_tag.get_text(" ", strip=True) if name_tag else ""
        return ProductData(name=name, price=price, source="css")
    return None


def parse_product(html: str, url: str = "") -> ProductData:
    """Extrage numele și prețul din HTML. Aruncă ScrapeError dacă nu găsește preț."""
    soup = BeautifulSoup(html, "html.parser")
    product = _from_jsonld(soup) or _from_meta(soup) or _from_css(soup, url)
    if product is None:
        raise ScrapeError(
            "Nu am găsit prețul în pagină (conținut încărcat prin JavaScript, "
            "captcha sau structură necunoscută - adaugă selectori în SITE_SELECTORS)"
        )
    if not product.name:
        h1 = soup.find("h1")
        product.name = (
            h1.get_text(" ", strip=True) if h1
            else (soup.title.get_text(strip=True) if soup.title else url)
        )
    # Titlurile paginilor (og:title) conțin des și numele magazinului: "Produs | Dedeman".
    if " | " in product.name:
        product.name = product.name.rsplit(" | ", 1)[0].strip()
    return product


def scrape(url: str, delay: float = 3.0) -> ProductData:
    """Descarcă pagina și întoarce datele produsului."""
    return parse_product(fetch(url, delay=delay), url)
