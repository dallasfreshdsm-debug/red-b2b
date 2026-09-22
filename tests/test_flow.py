import tempfile
import unittest
from pathlib import Path

from app import app, init_db


class BuyerSupplierFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app.config.update(TESTING=True, DATABASE=str(Path(self.tmp.name) / "test.sqlite3"),
                          SECRET_KEY="test-only-secret")
        init_db()
        self.buyer = app.test_client()
        self.supplier_a = app.test_client()
        self.supplier_b = app.test_client()
        self.outsider = app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def token(self, client):
        client.get("/entrar")
        with client.session_transaction() as s:
            return s["csrf"]

    def post(self, client, path, data, expected=302):
        response = client.post(path, data={"csrf": self.token(client), **data})
        self.assertEqual(response.status_code, expected, response.data[:300])
        return response

    def register(self, client, name, email):
        self.post(client, "/registrar", {
            "company_name": name, "country": "US", "city": "Des Moines",
            "email": email, "password": "long-password-123",
        })

    def test_private_quotes_and_complete_po(self):
        self.register(self.buyer, "Comprador", "buy@example.com")
        self.register(self.supplier_a, "Proveedor A", "a@example.com")
        self.register(self.supplier_b, "Proveedor B", "b@example.com")
        self.register(self.outsider, "Ajeno", "c@example.com")
        self.post(self.buyer, "/solicitudes/nueva", {
            "product": "Tomate Roma", "quantity": "40", "unit": "cajas",
            "destination": "Iowa", "required_date": "2099-01-01",
            "supplier_id": ["2", "3"],
        })
        self.assertEqual(self.outsider.get("/solicitudes/1").status_code, 404)
        self.post(self.supplier_a, "/solicitudes/1/cotizar", {
            "unit_price": "20.00", "shipping": "100", "currency": "USD",
            "available_quantity": "40", "delivery_date": "2099-01-01",
            "payment_terms": "Prepago", "notes": "Precio confidencial A",
        })
        self.post(self.supplier_b, "/solicitudes/1/cotizar", {
            "unit_price": "19.00", "shipping": "140", "currency": "USD",
            "available_quantity": "40", "delivery_date": "2099-01-01",
            "payment_terms": "Net 7", "notes": "Precio confidencial B",
        })
        self.assertNotIn(b"Precio confidencial B", self.supplier_a.get("/solicitudes/1").data)
        self.assertNotIn(b"Precio confidencial A", self.supplier_b.get("/solicitudes/1").data)
        self.assertIn(b"Precio confidencial B", self.buyer.get("/solicitudes/1").data)
        self.post(self.supplier_a, "/solicitudes/1/aprobar/1", {}, expected=404)
        self.post(self.buyer, "/solicitudes/1/aprobar/1", {})
        self.post(self.buyer, "/solicitudes/1/aprobar/2", {}, expected=404)
        self.assertEqual(self.outsider.get("/ordenes/1").status_code, 404)
        self.post(self.buyer, "/ordenes/1/liberar", {}, expected=404)
        self.post(self.supplier_a, "/ordenes/1/liberar", {})
        self.post(self.supplier_a, "/ordenes/1/recibir", {
            "received_quantity": "40", "rejected_quantity": "0",
        }, expected=404)
        self.post(self.buyer, "/ordenes/1/recibir", {
            "received_quantity": "38", "rejected_quantity": "2", "notes": "2 rechazadas por calidad",
        })
        page = self.buyer.get("/ordenes/1").data
        self.assertIn("Recibida".encode(), page)
        self.assertIn(b"2 rechazadas por calidad", page)
        self.post(self.buyer, "/ordenes/1/recibir", {
            "received_quantity": "1", "rejected_quantity": "0",
        }, expected=404)

    def test_post_needs_csrf(self):
        self.assertEqual(self.buyer.post("/registrar", data={}).status_code, 400)

    def test_multi_product_awards_are_separate_and_private(self):
        self.register(self.buyer, "Comprador", "buy@example.com")
        self.register(self.supplier_a, "Proveedor A", "a@example.com")
        self.register(self.supplier_b, "Proveedor B", "b@example.com")
        self.post(self.buyer, "/solicitudes/nueva", {
            "item_product": ["Tomate Roma", "Aguacate 48s"],
            "item_specification": ["Grande", "Caja 48"],
            "item_quantity": ["40", "20"],
            "item_unit": ["cajas", "cajas"],
            "destination": "Iowa", "required_date": "2099-01-01",
            "supplier_id": ["2", "3"],
        })
        self.assertIn(b"Tomate Roma", self.buyer.get("/solicitudes/1").data)
        self.post(self.supplier_a, "/solicitudes/1/cotizar", {
            "item_price_1": "20.00", "item_available_1": "40",
            "item_price_2": "45.00", "item_available_2": "20",
            "shipping": "100", "currency": "USD", "delivery_date": "2099-01-01",
            "payment_terms": "Prepago", "notes": "Solo A sabe esta nota",
        })
        self.post(self.supplier_b, "/solicitudes/1/cotizar", {
            "item_price_1": "22.00", "item_available_1": "40",
            "item_price_2": "35.00", "item_available_2": "20",
            "shipping": "80", "currency": "USD", "delivery_date": "2099-01-01",
            "payment_terms": "Net 7", "notes": "Solo B sabe esta nota",
        })
        self.assertNotIn(b"Solo B sabe esta nota", self.supplier_a.get("/solicitudes/1").data)
        self.assertNotIn(b"Solo A sabe esta nota", self.supplier_b.get("/solicitudes/1").data)
        self.post(self.supplier_a, "/solicitudes/1/conversacion/2", {
            "body": "Puedo entregar Roma el lunes",
        })
        self.assertEqual(self.supplier_b.get("/solicitudes/1/conversacion/2").status_code, 404)
        self.assertNotIn(b"Puedo entregar Roma", self.supplier_b.get("/solicitudes/1/conversacion/3").data)
        self.assertIn(b"Puedo entregar Roma", self.buyer.get("/solicitudes/1/conversacion/2").data)
        self.post(self.buyer, "/solicitudes/1/aprobar-productos", {
            "item_quote_1": "1", "item_quote_2": "2",
        })
        self.assertEqual(self.supplier_a.get("/ordenes/2").status_code, 404)
        self.assertEqual(self.supplier_b.get("/ordenes/1").status_code, 404)
        self.assertNotIn(b"orden #2", self.supplier_a.get("/solicitudes/1").data)
        self.assertIn(b"Tomate Roma", self.supplier_a.get("/ordenes/1").data)
        self.assertNotIn(b"Aguacate 48s", self.supplier_a.get("/ordenes/1").data)
        self.post(self.supplier_a, "/ordenes/1/liberar", {})
        self.post(self.buyer, "/ordenes/1/renglones/1/recibir", {
            "received_quantity": "38", "rejected_quantity": "2", "notes": "Calidad",
        })
        self.assertIn("Recibida".encode(), self.buyer.get("/ordenes/1").data)
        self.post(self.buyer, "/ordenes/2/renglones/1/recibir", {
            "received_quantity": "20", "rejected_quantity": "0",
        }, expected=404)

    def test_supplier_controls_new_buyer_access(self):
        self.register(self.buyer, "Comprador", "buy@example.com")
        self.register(self.supplier_a, "Proveedor", "a@example.com")
        self.post(self.supplier_a, "/mi-perfil-proveedor", {
            "description": "Tomate y aguacate", "pickup": "1",
            "service_area": "Texas", "default_payment_terms": "Prepago",
        })
        self.assertNotIn(b"Proveedor</strong>", self.buyer.get("/solicitudes/nueva").data)
        self.post(self.buyer, "/proveedores/2/solicitar", {})
        self.assertIn(b"Comprador", self.supplier_a.get("/relaciones").data)
        self.post(self.supplier_a, "/relaciones/1/aprobar", {})
        self.assertIn(b"Proveedor</strong>", self.buyer.get("/solicitudes/nueva").data)


if __name__ == "__main__":
    unittest.main()
