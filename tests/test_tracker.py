"""Teste care rulează fără internet:  python -m unittest discover tests"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import alerts
import db
from scraper import ScrapeError, parse_price, parse_product

JSONLD_PAGE = """
<html><head><title>Laptop X</title>
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "BreadcrumbList"},
  {"@type": "Product", "name": "Laptop X 15",
   "offers": {"@type": "Offer", "price": "3499.99", "priceCurrency": "RON",
              "availability": "https://schema.org/OutOfStock"}}
]}
</script></head><body><h1>Laptop X 15</h1></body></html>
"""

META_PAGE = """
<html><head>
<meta property="og:title" content="Carte Y">
<meta property="product:price:amount" content="45,50">
</head><body></body></html>
"""

EMAG_STYLE_PAGE = """
<html><body>
<h1 class="page-title"> Telefon Z 128GB </h1>
<p class="product-new-price">1.299<sup>99</sup> <span>Lei</span></p>
</body></html>
"""


class TestParsePrice(unittest.TestCase):
    def test_formats(self):
        cases = {
            "1.299,99 Lei": 1299.99,
            "1 299,99 lei": 1299.99,
            "1,299.99": 1299.99,
            "1299.99": 1299.99,
            "299,9": 299.9,
            "1.299": 1299.0,
            "1.234.567": 1234567.0,
            "45 RON": 45.0,
            "12.5": 12.5,
            3499: 3499.0,
        }
        for text, expected in cases.items():
            self.assertAlmostEqual(parse_price(text), expected, msg=repr(text))

    def test_invalid(self):
        self.assertIsNone(parse_price("Indisponibil"))
        self.assertIsNone(parse_price(None))


class TestParseProduct(unittest.TestCase):
    def test_jsonld(self):
        p = parse_product(JSONLD_PAGE)
        self.assertEqual((p.name, p.price, p.currency, p.source),
                         ("Laptop X 15", 3499.99, "RON", "json-ld"))
        self.assertFalse(p.available)

    def test_meta(self):
        p = parse_product(META_PAGE)
        self.assertEqual((p.name, p.price, p.source), ("Carte Y", 45.5, "meta"))

    def test_meta_title_without_store_name(self):
        page = """<html><head>
        <meta property="og:title" content="Brad artificial de Craciun, 180 cm | Dedeman">
        </head><body><meta itemprop="price" content="300.00"></body></html>"""
        p = parse_product(page)
        self.assertEqual((p.name, p.price, p.source),
                         ("Brad artificial de Craciun, 180 cm", 300.0, "meta"))

    def test_css_with_sup_decimals(self):
        p = parse_product(EMAG_STYLE_PAGE, "https://www.emag.ro/telefon-z/pd/ABC/")
        self.assertEqual((p.name, p.price, p.source), ("Telefon Z 128GB", 1299.99, "css"))

    def test_no_price(self):
        with self.assertRaises(ScrapeError):
            parse_product("<html><body><h1>Nimic</h1></body></html>", "https://x.ro/p")


class TestAlerts(unittest.TestCase):
    def test_target_and_drop(self):
        msgs = alerts.check_alerts("P", 90, 100, 95)
        self.assertEqual(len(msgs), 2)
        self.assertIn("-10.0%", msgs[1])

    def test_no_alert(self):
        self.assertEqual(alerts.check_alerts("P", 100, 100, 95), [])
        self.assertEqual(alerts.check_alerts("P", 110, 100, None), [])


class TestDb(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(os.path.join(tmp, "t.db"))
            pid = db.add_product(conn, "https://x.ro/p", "Produs", 50)
            db.add_price(conn, pid, 60, "RON", True)
            db.add_price(conn, pid, 55, "RON", True)
            self.assertEqual(db.last_price(conn, pid), 55)
            self.assertEqual(len(db.history(conn, pid)), 2)
            self.assertEqual(db.list_products(conn)[0]["min_price"], 55)
            self.assertEqual(db.export_csv(conn, os.path.join(tmp, "e.csv")), 2)
            self.assertTrue(db.remove_product(conn, pid))
            self.assertEqual(db.history(conn, pid), [])
            conn.close()


if __name__ == "__main__":
    unittest.main()
