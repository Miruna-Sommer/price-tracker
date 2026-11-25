"""Price tracker - interfața din linia de comandă.

Exemple:
    python tracker.py add "https://magazin.ro/produs" --target 1500
    python tracker.py check
    python tracker.py list
    python tracker.py history 1
    python tracker.py plot 1
    python tracker.py export
"""

import argparse
import sys
import time

import alerts
import db
from scraper import ScrapeError, scrape


def cmd_add(conn, args):
    try:
        product = scrape(args.url, delay=args.delay)
    except ScrapeError as e:
        sys.exit(f"Eroare: {e}")
    try:
        pid = db.add_product(conn, args.url, product.name, args.target)
    except db.sqlite3.IntegrityError:
        sys.exit("Produsul este deja urmărit.")
    db.add_price(conn, pid, product.price, product.currency, product.available)
    print(f"Adăugat [{pid}] {product.name}")
    print(f"  Preț curent: {product.price:.2f} {product.currency} (sursă: {product.source})")
    if args.target is not None:
        print(f"  Prag alertă: {args.target:.2f}")


def cmd_check(conn, args):
    products = db.list_products(conn)
    if not products:
        print("Niciun produs urmărit. Adaugă unul cu: python tracker.py add URL")
        return
    for p in products:
        print(f"[{p['id']}] {p['name']}")
        try:
            data = scrape(p["url"], delay=args.delay)
        except ScrapeError as e:
            print(f"  ⚠ {e}")
            continue
        old = p["last_price"]
        db.add_price(conn, p["id"], data.price, data.currency, data.available)
        change = ""
        if old is not None and data.price != old:
            change = f"  ({data.price - old:+.2f} față de {old:.2f})"
        stock = "" if data.available else "  [stoc epuizat]"
        print(f"  {data.price:.2f} {data.currency}{change}{stock}")
        alerts.notify(
            alerts.check_alerts(p["name"], data.price, old, p["target_price"], data.currency)
        )


def cmd_watch(conn, args):
    print(f"Verific la fiecare {args.interval} ore. Oprire: Ctrl+C")
    try:
        while True:
            print(f"\n--- {db.now()} ---")
            cmd_check(conn, args)
            time.sleep(args.interval * 3600)
    except KeyboardInterrupt:
        print("\nOprit.")


def cmd_list(conn, args):
    products = db.list_products(conn)
    if not products:
        print("Niciun produs urmărit.")
        return
    print(f"{'ID':>3}  {'Curent':>10}  {'Minim':>10}  {'Prag':>10}  Nume")
    for p in products:
        fmt = lambda v: f"{v:.2f}" if v is not None else "-"
        print(f"{p['id']:>3}  {fmt(p['last_price']):>10}  {fmt(p['min_price']):>10}  "
              f"{fmt(p['target_price']):>10}  {p['name'][:60]}")


def _get_product_or_exit(conn, product_id):
    product = db.get_product(conn, product_id)
    if product is None:
        sys.exit(f"Nu există produs cu ID {product_id}. Vezi: python tracker.py list")
    return product


def cmd_history(conn, args):
    product = _get_product_or_exit(conn, args.id)
    rows = db.history(conn, args.id)
    print(product["name"])
    for r in rows:
        stock = "" if r["available"] else "  [stoc epuizat]"
        print(f"  {r['checked_at']}  {r['price']:>10.2f} {r['currency']}{stock}")
    if rows:
        prices = [r["price"] for r in rows]
        print(f"  min {min(prices):.2f} | max {max(prices):.2f} | "
              f"medie {sum(prices) / len(prices):.2f} | {len(rows)} înregistrări")


def cmd_plot(conn, args):
    from plot import plot_history  # import târziu: matplotlib se încarcă lent

    product = _get_product_or_exit(conn, args.id)
    rows = db.history(conn, args.id)
    if not rows:
        sys.exit("Nu există încă prețuri pentru acest produs.")
    out = args.out or f"grafic_{args.id}.png"
    plot_history(product["name"], rows, product["target_price"], out)
    print(f"Grafic salvat: {out}")


def cmd_export(conn, args):
    count = db.export_csv(conn, args.out)
    print(f"{count} înregistrări exportate în {args.out}")


def cmd_remove(conn, args):
    if db.remove_product(conn, args.id):
        print("Produs șters (împreună cu istoricul).")
    else:
        sys.exit(f"Nu există produs cu ID {args.id}.")


def main():
    parser = argparse.ArgumentParser(description="Price tracker (requests + BeautifulSoup)")
    parser.add_argument("--db", default=db.DB_FILE, help="fișierul SQLite (implicit: prices.db)")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="pauza în secunde între cereri către același site (implicit: 3)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", help="adaugă un produs de urmărit")
    p.add_argument("url")
    p.add_argument("--target", type=float, help="prag de preț pentru alertă")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("check", help="verifică acum prețurile tuturor produselor")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("watch", help="verifică periodic, până la Ctrl+C")
    p.add_argument("--interval", type=float, default=6, help="ore între verificări (implicit: 6)")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("list", help="listează produsele urmărite")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("history", help="istoricul de preț al unui produs")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("plot", help="grafic PNG cu evoluția prețului")
    p.add_argument("id", type=int)
    p.add_argument("--out", help="fișierul de ieșire (implicit: grafic_ID.png)")
    p.set_defaults(func=cmd_plot)

    p = sub.add_parser("export", help="exportă tot istoricul în CSV")
    p.add_argument("--out", default="istoric.csv")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("remove", help="șterge un produs")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    conn = db.connect(args.db)
    try:
        args.func(conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
