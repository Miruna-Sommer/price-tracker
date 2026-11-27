# Price Tracker

Proiect pentru cursul de web scraping: un program care urmărește prețurile unor
produse din magazine online, păstrează istoricul, anunță scăderile de preț și
desenează graficul evoluției.

**Tehnologii:** Python 3.9+, `requests`, `BeautifulSoup`, `sqlite3`, `matplotlib`.

## Instalare

```bash
pip install -r requirements.txt
```

## Utilizare

```bash
# 1. Adaugă un produs (opțional, cu prag de alertă)
python tracker.py add "https://www.magazin.ro/produs" --target 1500

# 2. Verifică prețurile tuturor produselor
python tracker.py check

# 3. Vezi produsele, istoricul și graficul
python tracker.py list
python tracker.py history 1
python tracker.py plot 1          # -> grafic_1.png
python tracker.py export          # -> istoric.csv

# Verificare periodică (la 6 ore), până la Ctrl+C
python tracker.py watch --interval 6

# Șterge un produs
python tracker.py remove 1
```

Opțiuni generale (puse înaintea comenzii): `--db fisier.db`, `--delay secunde`.

Pentru rulare automată zilnică, fără `watch`:

- **Linux/macOS (cron):** `0 9 * * * cd /cale/proiect && python tracker.py check`
- **Windows:** Task Scheduler -> acțiune `python tracker.py check`

## Structura proiectului

| Fișier | Rol |
|---|---|
| `scraper.py` | descarcă pagina (`requests`) și extrage numele + prețul (`BeautifulSoup`) |
| `db.py` | baza de date SQLite: tabelele `products` și `prices`, export CSV |
| `alerts.py` | regulile de alertă; scrie în consolă și în `alerts.log` |
| `plot.py` | graficul evoluției prețului |
| `tracker.py` | interfața din linia de comandă, leagă totul |
| `tests/` | teste unitare, rulează fără internet |

## Cum funcționează

```
URL -> fetch() -> HTML -> parse_product() -> ProductData -> SQLite -> alerte / grafic
```

### 1. Descărcarea (`fetch`)

- verifică `robots.txt` înainte de orice cerere (`urllib.robotparser`);
- trimite un `User-Agent` care identifică proiectul;
- pune o pauză (implicit 3 s) între cereri către același site;
- reîncearcă la erori temporare, cu pauză crescătoare (backoff).

### 2. Extragerea prețului (`parse_product`)

Trei metode, încercate în ordine, de la cea mai stabilă la cea mai fragilă:

1. **JSON-LD** - blocul `<script type="application/ld+json">` cu date
   `schema.org/Product`, pe care magazinele îl pun pentru Google. Nu depinde de
   designul paginii.
2. **Meta tag-uri** - `product:price:amount`, `itemprop="price"`.
3. **Selectori CSS pe magazin** - dicționarul `SITE_SELECTORS` din `scraper.py`.

Comanda `add` afișează ce metodă a funcționat (`sursă: json-ld / meta / css`).

### 3. Normalizarea prețului (`parse_price`)

Prețurile apar ca text în formate diferite: `1.299,99 Lei`, `1 299,99`,
`1299.99`. Funcția le aduce la `float`, hotărând care separator e cel zecimal.

### 4. Alertele

- **Prag atins:** prețul nou <= pragul dat la `--target`.
- **Scădere:** prețul nou < prețul de la verificarea anterioară.

## Adăugarea unui magazin nou

Dacă `add` spune că nu găsește prețul:

1. Deschide pagina în browser -> `Ctrl+U` (view source) și caută prețul.
   - Dacă **nu apare în sursă**, pagina îl încarcă prin JavaScript și
     `requests` nu îl poate vedea (ar fi nevoie de Selenium/Playwright).
2. Dacă apare, `F12` -> Inspect pe preț și notează selectorul CSS.
3. Adaugă o linie în `SITE_SELECTORS`:

```python
"magazin.ro": ("h1.titlu-produs", "span.pret"),
```

## Limitări și etică

- Magazinele mari folosesc protecții anti-bot (captcha, HTTP 403). Programul
  raportează eroarea și **nu** încearcă să le ocolească.
- Citește termenii și condițiile magazinului: unele interzic explicit
  colectarea automată. Proiectul e gândit pentru uz educațional, cu puține
  produse și verificări rare (de câteva ori pe zi), nu pentru scraping în masă.
- Selectorii CSS se strică atunci când magazinul își schimbă pagina; de aceea
  JSON-LD e prima metodă încercată.

## Date colectate

Am lăsat programul să ruleze automat de două ori pe zi (09:47 și 20:47), din 25 noiembrie
până pe 9 decembrie 2026. Am urmărit 10 produse de pe libris.ro:
cărți, seturi LEGO și jocuri de societate. Am prins și perioada de Black Friday.

Lista de produse s-a schimbat de două ori pe parcurs:

- **25 noiembrie:** am pornit cu 5 produse, dar două dintre ele (LEGO Classic și Catan) erau
  epuizate, iar produsele fără stoc rareori își schimbă prețul. Am mai adăugat câteva în stoc:
  Catan Duelul, Atomic Habits și Dixit.
- **27 noiembrie:** după primele zile niciun preț nu se schimbase, nici de Black Friday
  (Libris a oferit vouchere și puncte de fidelitate, nu reduceri pe produse). Am adăugat două
  cărți de Matt Haig, „autorul lunii” la Libris, cu 20% reducere în noiembrie. Când se termină
  promoția, prețul ar trebui să crească la loc, ceea ce testează urmărirea schimbărilor de preț.

Produsele adăugate mai târziu au de aceea un istoric mai scurt. Data adăugării fiecăruia e
în câmpul `created_at` din tabela `products`.

| Fișier | Conținut |
|---|---|
| `date/prices.db` | baza de date cu tot istoricul |
| `date/istoric.csv` | istoricul exportat cu `python tracker.py export` |
| `date/grafice/` | graficul fiecărui produs (`python tracker.py plot N`) |
| `date/alerts.log` | alertele declanșate |
| `date/check_log.txt` | ieșirea fiecărei verificări |

Comenzile merg direct pe datele colectate, de exemplu:

```bash
python tracker.py --db date/prices.db list
python tracker.py --db date/prices.db history 1
```

În timpul colectării, doar Libris a răspuns normal. Celelalte magazine pe care le-am încercat
(eMAG, PC Garage, Cărturești, elefant.ro, evoMAG, CEL.ro, Altex) au refuzat cererile automate:
captcha, Cloudflare, HTTP 429 sau niciun răspuns.

Verificarea programată e în `tools/run_check.sh`: rulează `check`, adaugă ieșirea în
`date/check_log.txt` și regenerează CSV-ul și graficele. Se poate pune în cron:

```bash
47 9,20 * * * /cale/proiect/tools/run_check.sh
```

## Teste

```bash
python -m unittest discover tests
```

Testele acoperă formatele de preț, cele trei metode de extragere (pe HTML
de exemplu), regulile de alertă și baza de date.
