PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  country TEXT NOT NULL,
  city TEXT NOT NULL,
  can_buy INTEGER NOT NULL DEFAULT 1,
  can_sell INTEGER NOT NULL DEFAULT 1,
  can_transport INTEGER NOT NULL DEFAULT 0,
  verified INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','member')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS supplier_profiles (
  company_id INTEGER PRIMARY KEY REFERENCES companies(id),
  description TEXT NOT NULL DEFAULT '',
  own_delivery INTEGER NOT NULL DEFAULT 0,
  pickup INTEGER NOT NULL DEFAULT 1,
  third_party_shipping INTEGER NOT NULL DEFAULT 0,
  service_area TEXT NOT NULL DEFAULT '',
  pickup_address TEXT NOT NULL DEFAULT '',
  accepts_new_buyers INTEGER NOT NULL DEFAULT 1,
  default_payment_terms TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS supplier_relationships (
  buyer_id INTEGER NOT NULL REFERENCES companies(id),
  supplier_id INTEGER NOT NULL REFERENCES companies(id),
  status TEXT NOT NULL CHECK(status IN ('requested','approved','declined')),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(buyer_id,supplier_id)
);
CREATE TABLE IF NOT EXISTS rfq_messages (
  id INTEGER PRIMARY KEY,
  rfq_id INTEGER NOT NULL REFERENCES rfqs(id),
  supplier_id INTEGER NOT NULL REFERENCES companies(id),
  sender_company_id INTEGER NOT NULL REFERENCES companies(id),
  sender_user_id INTEGER NOT NULL REFERENCES users(id),
  body TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS rfqs (
  id INTEGER PRIMARY KEY,
  buyer_id INTEGER NOT NULL REFERENCES companies(id),
  product TEXT NOT NULL,
  specification TEXT NOT NULL DEFAULT '',
  quantity TEXT NOT NULL,
  unit TEXT NOT NULL,
  destination TEXT NOT NULL,
  required_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','awarded','cancelled')),
  created_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS invitations (
  id INTEGER PRIMARY KEY,
  rfq_id INTEGER NOT NULL REFERENCES rfqs(id),
  supplier_id INTEGER NOT NULL REFERENCES companies(id),
  UNIQUE(rfq_id, supplier_id)
);
CREATE TABLE IF NOT EXISTS rfq_items (
  id INTEGER PRIMARY KEY,
  rfq_id INTEGER NOT NULL REFERENCES rfqs(id),
  position INTEGER NOT NULL,
  product TEXT NOT NULL,
  specification TEXT NOT NULL DEFAULT '',
  quantity TEXT NOT NULL,
  unit TEXT NOT NULL,
  UNIQUE(rfq_id, position)
);
CREATE TABLE IF NOT EXISTS quotes (
  id INTEGER PRIMARY KEY,
  invitation_id INTEGER NOT NULL UNIQUE REFERENCES invitations(id),
  unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
  shipping_cents INTEGER NOT NULL CHECK(shipping_cents >= 0),
  currency TEXT NOT NULL CHECK(currency IN ('USD','MXN')),
  available_quantity TEXT NOT NULL,
  delivery_date TEXT NOT NULL,
  payment_terms TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  created_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS quote_items (
  id INTEGER PRIMARY KEY,
  quote_id INTEGER NOT NULL REFERENCES quotes(id),
  rfq_item_id INTEGER NOT NULL REFERENCES rfq_items(id),
  unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
  available_quantity TEXT NOT NULL,
  UNIQUE(quote_id, rfq_item_id)
);
CREATE TABLE IF NOT EXISTS purchase_orders (
  id INTEGER PRIMARY KEY,
  rfq_id INTEGER NOT NULL REFERENCES rfqs(id),
  quote_id INTEGER NOT NULL REFERENCES quotes(id),
  buyer_id INTEGER NOT NULL REFERENCES companies(id),
  supplier_id INTEGER NOT NULL REFERENCES companies(id),
  quantity TEXT NOT NULL,
  unit_price_cents INTEGER NOT NULL,
  shipping_cents INTEGER NOT NULL,
  total_cents INTEGER NOT NULL,
  currency TEXT NOT NULL,
  payment_terms TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending_release'
    CHECK(status IN ('pending_release','released','partial','received')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS po_items (
  id INTEGER PRIMARY KEY,
  po_id INTEGER NOT NULL REFERENCES purchase_orders(id),
  rfq_item_id INTEGER NOT NULL REFERENCES rfq_items(id),
  product TEXT NOT NULL,
  quantity TEXT NOT NULL,
  unit TEXT NOT NULL,
  unit_price_cents INTEGER NOT NULL,
  UNIQUE(po_id, rfq_item_id)
);
CREATE TABLE IF NOT EXISTS receipts (
  id INTEGER PRIMARY KEY,
  po_id INTEGER NOT NULL REFERENCES purchase_orders(id),
  received_quantity TEXT NOT NULL,
  rejected_quantity TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  received_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS receipt_items (
  id INTEGER PRIMARY KEY,
  po_item_id INTEGER NOT NULL REFERENCES po_items(id),
  received_quantity TEXT NOT NULL,
  rejected_quantity TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  received_by INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY,
  actor_user_id INTEGER NOT NULL REFERENCES users(id),
  company_id INTEGER NOT NULL REFERENCES companies(id),
  object_type TEXT NOT NULL,
  object_id INTEGER NOT NULL,
  event TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rfqs_buyer ON rfqs(buyer_id, created_at);
CREATE INDEX IF NOT EXISTS idx_invitations_supplier ON invitations(supplier_id, rfq_id);
CREATE INDEX IF NOT EXISTS idx_rfq_messages_pair ON rfq_messages(rfq_id, supplier_id, id);
CREATE INDEX IF NOT EXISTS idx_rfq_items_rfq ON rfq_items(rfq_id, position);
CREATE INDEX IF NOT EXISTS idx_quote_items_quote ON quote_items(quote_id, rfq_item_id);
CREATE INDEX IF NOT EXISTS idx_pos_buyer ON purchase_orders(buyer_id, status);
CREATE INDEX IF NOT EXISTS idx_pos_supplier ON purchase_orders(supplier_id, status);
CREATE INDEX IF NOT EXISTS idx_po_items_po ON po_items(po_id, rfq_item_id);

-- Buyer-owned replenishment data. The source remains explicit; no QuickBooks writes.
CREATE TABLE IF NOT EXISTS buyer_products (
  id INTEGER PRIMARY KEY, buyer_id INTEGER NOT NULL REFERENCES companies(id),
  name TEXT NOT NULL, purchase_unit TEXT NOT NULL DEFAULT 'caja',
  sale_unit TEXT NOT NULL DEFAULT 'lb', pack_size TEXT NOT NULL DEFAULT '1',
  stock_target TEXT NOT NULL DEFAULT '0', stock_snapshot TEXT NOT NULL DEFAULT '0',
  snapshot_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  snapshot_usage_id INTEGER NOT NULL DEFAULT 0,
  lead_days INTEGER NOT NULL DEFAULT 1 CHECK(lead_days BETWEEN 0 AND 90),
  waste_percent TEXT NOT NULL DEFAULT '0',
  source TEXT NOT NULL DEFAULT 'manual',
  UNIQUE(id,buyer_id)
);
CREATE TABLE IF NOT EXISTS product_usage (
  id INTEGER PRIMARY KEY, buyer_id INTEGER NOT NULL REFERENCES companies(id),
  product_id INTEGER NOT NULL REFERENCES buyer_products(id),
  quantity TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('sale','waste','internal','receipt')),
  occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, source TEXT NOT NULL DEFAULT 'manual'
);
CREATE INDEX IF NOT EXISTS idx_usage_product ON product_usage(buyer_id,product_id,occurred_at);
CREATE TABLE IF NOT EXISTS product_offers (
  id INTEGER PRIMARY KEY, buyer_id INTEGER NOT NULL REFERENCES companies(id),
  product_id INTEGER NOT NULL REFERENCES buyer_products(id),
  supplier_id INTEGER NOT NULL REFERENCES companies(id),
  unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents>=0),
  currency TEXT NOT NULL CHECK(currency IN ('USD','MXN')),
  valid_until TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(buyer_id,product_id,supplier_id)
);
CREATE TABLE IF NOT EXISTS direct_orders (
  id INTEGER PRIMARY KEY, buyer_id INTEGER NOT NULL REFERENCES companies(id),
  supplier_id INTEGER NOT NULL REFERENCES companies(id),
  currency TEXT NOT NULL CHECK(currency IN ('USD','MXN')),
  total_cents INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending_release'
    CHECK(status IN ('pending_release','released','received')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS direct_order_items (
  id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES direct_orders(id),
  product_id INTEGER NOT NULL REFERENCES buyer_products(id),
  product_name TEXT NOT NULL, purchase_unit TEXT NOT NULL,
  pack_size TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0),
  unit_price_cents INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_direct_buyer ON direct_orders(buyer_id,created_at);
CREATE INDEX IF NOT EXISTS idx_direct_supplier ON direct_orders(supplier_id,created_at);
