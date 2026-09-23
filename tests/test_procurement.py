import tempfile
import unittest
import io
import json
import os
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from app import app, init_db
import sqlite3


class PredictivePurchaseFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True, DATABASE=str(Path(self.tmp.name) / "test.sqlite3"),
                          SECRET_KEY="test-only-secret")
        init_db()
        self.buyer = app.test_client()
        self.supplier = app.test_client()
        self.other = app.test_client()
        for client, name, email in ((self.buyer, "Tienda", "buyer@test.com"),
                                     (self.supplier, "Dallas Fresh", "supplier@test.com"),
                                     (self.other, "Otra tienda", "other@test.com")):
            self.post(client, "/registrar", {"company_name": name, "country": "US", "city": "Dallas",
                                            "email": email, "password": "long-password-123"})

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, client, path, data, status=302):
        client.get("/entrar")
        with client.session_transaction() as session:
            token = session["csrf"]
        response = client.post(path, data={"csrf": token, **data})
        self.assertEqual(response.status_code, status, response.data[:400])
        return response

    def test_stock_prediction_provider_order_and_company_isolation(self):
        self.post(self.buyer, "/compras/productos", {
            "name": "Tomate Roma", "purchase_unit": "caja", "sale_unit": "lb", "pack_size": "25",
            "stock_snapshot": "250", "stock_target": "250", "lead_days": "0", "waste_percent": "0",
        })
        self.post(self.buyer, "/compras/productos/1/consumo", {"kind": "sale", "quantity": "52"})
        self.post(self.buyer, "/compras/productos/1/precios", {
            "supplier_id": "2", "price": "10", "currency": "USD", "valid_until": "2099-01-01",
        })
        page = self.buyer.get("/compras").data
        self.assertIn(b'name="quantity_1" value="3"', page)
        self.assertNotIn(b"Tomate Roma", self.other.get("/compras").data)
        self.post(self.buyer, "/compras/ordenar", {"product_id": "1", "quantity_1": "3", "offer_1": "1"})
        self.assertIn(b"30.00", self.buyer.get("/compras/ordenes/1").data)
        self.assertEqual(self.other.get("/compras/ordenes/1").status_code, 404)
        self.assertEqual(self.supplier.get("/compras/productos").status_code, 200)
        self.assertNotIn(b"<h2>Tomate Roma</h2>", self.supplier.get("/compras/productos").data)
        self.post(self.buyer, "/compras/ordenes/1/liberar", {}, status=404)
        self.post(self.supplier, "/compras/ordenes/1/liberar", {})
        self.post(self.buyer, "/compras/ordenes/1/recibir", {})
        self.assertIn(b"Recibida", self.buyer.get("/compras/ordenes/1").data)
        self.assertIn(b'name="quantity_1" value="0"', self.buyer.get("/compras").data)
        self.assertIn(b'<td>#1</td>', self.buyer.get("/compras?supplier=2&from=2000-01-01&to=2099-01-01").data)
        self.assertNotIn(b'<td>#1</td>', self.buyer.get("/compras?supplier=3").data)

    def test_rejects_other_company_offer_and_avoids_double_count_after_stocktake(self):
        self.post(self.buyer, "/compras/productos", {
            "name": "Roma", "purchase_unit": "caja", "sale_unit": "lb", "pack_size": "25",
            "stock_snapshot": "100", "stock_target": "100", "lead_days": "0", "waste_percent": "0",
        })
        self.post(self.buyer, "/compras/productos/1/consumo", {"kind": "waste", "quantity": "25"})
        self.post(self.buyer, "/compras/productos/1/conteo", {"quantity": "100"})
        self.assertIn(b'name="quantity_1" value="0"', self.buyer.get("/compras").data)
        self.post(self.other, "/compras/productos/1/consumo", {"kind": "sale", "quantity": "1"}, status=404)
        self.post(self.buyer, "/compras/ordenar", {"product_id": "1", "quantity_1": "2", "offer_1": "1"})
        self.assertNotIn(b"Orden #1", self.buyer.get("/compras").data)

    def test_read_only_connector_sync_uses_sales_and_is_tenant_scoped(self):
        day=(date.today()-timedelta(days=1)).isoformat()
        payload={"ok":True,"read_only":True,"complete":True,"environment":"sandbox",
                 "sales_window_start":(date.today()-timedelta(days=29)).isoformat(),
                 "products":[{"external_id":"qbo-123","name":"Roma QBO"}],
                 "sales":[{"external_id":"qbo-123","date":day,"quantity":"52"}]}
        env={"B2B_SYNC_COMPANY_ID":"1","B2B_CONNECTOR_URL":"https://connector.example.test",
             "B2B_CONNECTOR_READ_KEY":"secret","B2B_CONNECTOR_EXPECTED_ENV":"sandbox"}

        class FakeOpener:
            def open(self, req, timeout):
                if req.full_url!="https://connector.example.test/api/b2b-read" or req.get_header("X-b2b-read-key")!="secret":
                    raise AssertionError("Unexpected endpoint or key")
                return io.BytesIO(json.dumps(payload).encode())

        with patch.dict(os.environ,env),patch("procurement.build_opener",return_value=FakeOpener()):
            self.post(self.other,"/compras/sincronizar-productos",{},status=403)
            self.post(self.buyer,"/compras/sincronizar-productos",{})
            self.post(self.buyer,"/compras/sincronizar-productos",{})
            with sqlite3.connect(app.config["DATABASE"]) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM buyer_products WHERE buyer_id=1").fetchone()[0],1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM external_daily_sales WHERE buyer_id=1").fetchone()[0],1)
                db.execute("UPDATE buyer_products SET pack_size='25',stock_target='250',stock_snapshot='250',"
                           "lead_days=7,snapshot_at=? WHERE buyer_id=1",((date.today()-timedelta(days=3)).isoformat(),))
                db.commit()
            page=self.buyer.get("/compras").data
            self.assertIn(b"Roma QBO",page)
            self.assertIn(b'name="quantity_1" value="3"',page)
            self.assertNotIn(b"Roma QBO",self.other.get("/compras").data)
        with patch.dict(os.environ,{"B2B_SYNC_COMPANY_ID":"1","B2B_CONNECTOR_URL":"http://insecure.test","B2B_CONNECTOR_READ_KEY":"secret"}):
            self.post(self.buyer,"/compras/sincronizar-productos",{})
            with sqlite3.connect(app.config["DATABASE"]) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM buyer_products WHERE buyer_id=1").fetchone()[0],1)


if __name__ == "__main__":
    unittest.main()
