import tempfile
import unittest
from pathlib import Path

from app import app, init_db


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
        self.assertIn(b'value="3" class="order-qty"', page)
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
        self.assertIn(b'value="0" class="order-qty"', self.buyer.get("/compras").data)
        self.assertIn(b"Orden #1", self.buyer.get("/compras?supplier=2&from=2000-01-01&to=2099-01-01").data)
        self.assertNotIn(b"Orden #1", self.buyer.get("/compras?supplier=3").data)

    def test_rejects_other_company_offer_and_avoids_double_count_after_stocktake(self):
        self.post(self.buyer, "/compras/productos", {
            "name": "Roma", "purchase_unit": "caja", "sale_unit": "lb", "pack_size": "25",
            "stock_snapshot": "100", "stock_target": "100", "lead_days": "0", "waste_percent": "0",
        })
        self.post(self.buyer, "/compras/productos/1/consumo", {"kind": "waste", "quantity": "25"})
        self.post(self.buyer, "/compras/productos/1/conteo", {"quantity": "100"})
        self.assertIn(b'value="0" class="order-qty"', self.buyer.get("/compras").data)
        self.post(self.other, "/compras/productos/1/consumo", {"kind": "sale", "quantity": "1"}, status=404)
        self.post(self.buyer, "/compras/ordenar", {"product_id": "1", "quantity_1": "2", "offer_1": "1"})
        self.assertNotIn(b"Orden #1", self.buyer.get("/compras").data)


if __name__ == "__main__":
    unittest.main()
