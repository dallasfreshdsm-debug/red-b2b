"""Independent buyer/supplier pilot. No connection to Dallas Fresh production data."""

import os
import secrets
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("B2B_SECRET_KEY", secrets.token_hex(32)),
    DATABASE=os.environ.get("B2B_DATABASE", str(ROOT / "instance" / "red_b2b.sqlite3")),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("B2B_SECURE_COOKIE") == "1",
    MAX_CONTENT_LENGTH=64 * 1024,
)


def init_db():
    path = Path(app.config["DATABASE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript((ROOT / "schema.sql").read_text())
    # V1 kept one PO per RFQ. Remove that constraint while retaining pilot data.
    if any(index[3] == "u" for index in db.execute("PRAGMA index_list(purchase_orders)")):
        db.execute("PRAGMA foreign_keys=OFF")
        db.executescript("""
            BEGIN;
            CREATE TABLE purchase_orders_new (
              id INTEGER PRIMARY KEY,
              rfq_id INTEGER NOT NULL REFERENCES rfqs(id),
              quote_id INTEGER NOT NULL REFERENCES quotes(id),
              buyer_id INTEGER NOT NULL REFERENCES companies(id),
              supplier_id INTEGER NOT NULL REFERENCES companies(id),
              quantity TEXT NOT NULL, unit_price_cents INTEGER NOT NULL,
              shipping_cents INTEGER NOT NULL, total_cents INTEGER NOT NULL,
              currency TEXT NOT NULL, payment_terms TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending_release'
                CHECK(status IN ('pending_release','released','partial','received')),
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO purchase_orders_new SELECT * FROM purchase_orders;
            DROP TABLE purchase_orders;
            ALTER TABLE purchase_orders_new RENAME TO purchase_orders;
            CREATE INDEX idx_pos_buyer ON purchase_orders(buyer_id,status);
            CREATE INDEX idx_pos_supplier ON purchase_orders(supplier_id,status);
            COMMIT;
        """)
        db.execute("PRAGMA foreign_keys=ON")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise RuntimeError("La migración de órdenes dejó referencias inválidas")
    db.close()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.before_request
def load_user():
    g.user = None
    if session.get("user_id"):
        g.user = get_db().execute(
            "SELECT u.*, c.name AS company_name FROM users u "
            "JOIN companies c ON c.id=u.company_id WHERE u.id=?",
            (session["user_id"],),
        ).fetchone()
    if request.method == "POST":
        if not session.get("csrf") or not secrets.compare_digest(
            request.form.get("csrf", ""), session["csrf"]
        ):
            abort(400, "Formulario vencido. Actualiza la página y vuelve a intentarlo.")


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self' data:; form-action 'self'; frame-ancestors 'none'"
    )
    return response


@app.context_processor
def template_helpers():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(24)
    return {"csrf_token": session["csrf"], "today": date.today().isoformat()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def text_field(key, max_len=160):
    value = request.form.get(key, "").strip()
    if not value or len(value) > max_len:
        raise ValueError(f"Revisa el campo {key}.")
    return value


def amount(key, *, allow_zero=False):
    try:
        value = Decimal(text_field(key, 24))
    except InvalidOperation as exc:
        raise ValueError(f"Revisa el número de {key}.") from exc
    if not value.is_finite() or value > Decimal("1000000000"):
        raise ValueError(f"Revisa el número de {key}.")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{key} debe ser positivo.")
    return value


def decimal_value(raw, label, *, allow_zero=False):
    try:
        value = Decimal(str(raw).strip())
    except InvalidOperation as exc:
        raise ValueError(f"Revisa {label}.") from exc
    if not value.is_finite() or value > Decimal("1000000000") or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"Revisa {label}.")
    return value


def cents_value(raw, label):
    value = decimal_value(raw, label, allow_zero=True)
    if value.as_tuple().exponent < -2:
        raise ValueError(f"{label} admite dos decimales como máximo.")
    return int(value * 100)


def cents(key):
    value = amount(key, allow_zero=True)
    if value.as_tuple().exponent < -2:
        raise ValueError(f"{key} admite dos decimales como máximo.")
    return int(value * 100)


def valid_date(key):
    value = text_field(key, 10)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Fecha inválida.") from exc
    if parsed < date.today():
        raise ValueError("La fecha no puede estar en el pasado.")
    return value


def audit(db, object_type, object_id, event):
    db.execute(
        "INSERT INTO audit_events(actor_user_id,company_id,object_type,object_id,event) "
        "VALUES(?,?,?,?,?)",
        (g.user["id"], g.user["company_id"], object_type, object_id, event),
    )


@app.template_filter("money")
def money(cents_value):
    return f"{int(cents_value) / 100:,.2f}"


@app.template_filter("status_es")
def status_es(value):
    return {
        "open": "Recibiendo propuestas", "awarded": "Compra aprobada",
        "cancelled": "Cancelada", "pending_release": "Pendiente de liberar",
        "released": "Liberada", "partial": "Recepción parcial",
        "received": "Recibida", "requested": "Solicitada",
        "approved": "Aprobada", "declined": "Rechazada",
    }.get(value, value)


@app.route("/")
@login_required
def dashboard():
    db = get_db()
    company = g.user["company_id"]
    purchases = db.execute(
        "SELECT r.*, (SELECT COUNT(*) FROM quotes q JOIN invitations i ON i.id=q.invitation_id "
        "WHERE i.rfq_id=r.id) quote_count FROM rfqs r WHERE r.buyer_id=? "
        "ORDER BY r.id DESC", (company,)
    ).fetchall()
    invitations = db.execute(
        "SELECT i.id AS invitation_id, r.*, c.name AS buyer_name, q.id AS quote_id "
        "FROM invitations i JOIN rfqs r ON r.id=i.rfq_id "
        "JOIN companies c ON c.id=r.buyer_id "
        "LEFT JOIN quotes q ON q.invitation_id=i.id "
        "WHERE i.supplier_id=? ORDER BY r.id DESC", (company,)
    ).fetchall()
    orders = db.execute(
        "SELECT p.*, r.product, r.unit, buyer.name AS buyer_name, "
        "supplier.name AS supplier_name FROM purchase_orders p "
        "JOIN rfqs r ON r.id=p.rfq_id JOIN companies buyer ON buyer.id=p.buyer_id "
        "JOIN companies supplier ON supplier.id=p.supplier_id "
        "WHERE p.buyer_id=? OR p.supplier_id=? ORDER BY p.id DESC",
        (company, company),
    ).fetchall()
    return render_template("dashboard.html", purchases=purchases,
                           invitations=invitations, orders=orders)


@app.get("/proveedores")
@login_required
def supplier_directory():
    rows = get_db().execute(
        "SELECT c.id,c.name,c.city,c.country,c.verified,p.description,p.own_delivery,"
        "p.pickup,p.third_party_shipping,p.service_area,p.pickup_address,"
        "COALESCE(p.accepts_new_buyers,1) AS accepts_new_buyers,r.status AS relationship "
        "FROM companies c LEFT JOIN supplier_profiles p ON p.company_id=c.id "
        "LEFT JOIN supplier_relationships r ON r.supplier_id=c.id AND r.buyer_id=? "
        "WHERE c.id<>? AND c.can_sell=1 ORDER BY c.name",
        (g.user["company_id"], g.user["company_id"]),
    ).fetchall()
    return render_template("suppliers.html", suppliers=rows)


@app.route("/mi-perfil-proveedor", methods=["GET", "POST"])
@admin_required
def supplier_profile():
    db = get_db()
    if request.method == "POST":
        description = request.form.get("description", "").strip()[:500]
        service_area = request.form.get("service_area", "").strip()[:160]
        pickup_address = request.form.get("pickup_address", "").strip()[:160]
        payment = request.form.get("default_payment_terms", "").strip()[:160]
        flags = [int(request.form.get(key) == "1") for key in
                 ("own_delivery", "pickup", "third_party_shipping", "accepts_new_buyers")]
        if not any(flags[:3]):
            flash("Selecciona por lo menos una forma de entrega o recolección.")
        else:
            with db:
                db.execute(
                    "INSERT INTO supplier_profiles(company_id,description,service_area,pickup_address,"
                    "default_payment_terms,own_delivery,pickup,third_party_shipping,accepts_new_buyers) "
                    "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(company_id) DO UPDATE SET "
                    "description=excluded.description,service_area=excluded.service_area,"
                    "pickup_address=excluded.pickup_address,default_payment_terms=excluded.default_payment_terms,"
                    "own_delivery=excluded.own_delivery,pickup=excluded.pickup,"
                    "third_party_shipping=excluded.third_party_shipping,"
                    "accepts_new_buyers=excluded.accepts_new_buyers,updated_at=CURRENT_TIMESTAMP",
                    (g.user["company_id"], description, service_area, pickup_address,
                     payment, *flags),
                )
                audit(db, "company", g.user["company_id"], "supplier_profile_updated")
            flash("Perfil de proveedor guardado.")
            return redirect(url_for("supplier_profile"))
    profile = db.execute("SELECT * FROM supplier_profiles WHERE company_id=?",
                         (g.user["company_id"],)).fetchone()
    return render_template("supplier_profile.html", profile=profile)


@app.post("/proveedores/<int:supplier_id>/solicitar")
@admin_required
def request_supplier(supplier_id):
    db = get_db()
    company = db.execute("SELECT id FROM companies WHERE id=? AND id<>? AND can_sell=1",
                         (supplier_id, g.user["company_id"])).fetchone()
    if company is None:
        abort(404)
    with db:
        db.execute(
            "INSERT INTO supplier_relationships(buyer_id,supplier_id,status) VALUES(?,?,'requested') "
            "ON CONFLICT(buyer_id,supplier_id) DO UPDATE SET status='requested',updated_at=CURRENT_TIMESTAMP "
            "WHERE status='declined'",
            (g.user["company_id"], supplier_id),
        )
        audit(db, "company", supplier_id, "supplier_access_requested")
    flash("Solicitud enviada. El proveedor decidirá si acepta la relación comercial.")
    return redirect(url_for("supplier_directory"))


@app.get("/relaciones")
@admin_required
def relationships():
    buyers = get_db().execute(
        "SELECT r.buyer_id,r.status,r.updated_at,c.name,c.city,c.country,c.verified "
        "FROM supplier_relationships r JOIN companies c ON c.id=r.buyer_id "
        "WHERE r.supplier_id=? ORDER BY CASE r.status WHEN 'requested' THEN 0 ELSE 1 END,r.updated_at DESC",
        (g.user["company_id"],),
    ).fetchall()
    return render_template("relationships.html", buyers=buyers)


@app.post("/relaciones/<int:buyer_id>/<decision>")
@admin_required
def decide_relationship(buyer_id, decision):
    if decision not in ("aprobar", "rechazar"):
        abort(404)
    status = "approved" if decision == "aprobar" else "declined"
    db = get_db()
    with db:
        changed = db.execute(
            "UPDATE supplier_relationships SET status=?,updated_at=CURRENT_TIMESTAMP "
            "WHERE buyer_id=? AND supplier_id=? AND status='requested'",
            (status, buyer_id, g.user["company_id"]),
        ).rowcount
        if not changed:
            abort(404)
        audit(db, "company", buyer_id, "relationship_" + status)
    flash("Relación comercial actualizada. Cada compra sigue sujeta a las condiciones que acuerden.")
    return redirect(url_for("relationships"))


@app.route("/registrar", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            name = text_field("company_name")
            country = text_field("country", 80)
            city = text_field("city", 80)
            email = text_field("email", 254).lower()
            password = text_field("password", 128)
            if len(password) < 12 or "@" not in email:
                raise ValueError("Usa un correo válido y una contraseña de al menos 12 caracteres.")
            db = get_db()
            with db:
                company = db.execute(
                    "INSERT INTO companies(name,country,city) VALUES(?,?,?)",
                    (name, country, city),
                ).lastrowid
                user = db.execute(
                    "INSERT INTO users(company_id,email,password_hash,role) VALUES(?,?,?,'admin')",
                    (company, email, generate_password_hash(password)),
                ).lastrowid
            session.clear()
            session["user_id"] = user
            flash("Empresa registrada. Ya puedes preparar una solicitud de compra.")
            return redirect(url_for("dashboard"))
        except (ValueError, sqlite3.IntegrityError) as exc:
            flash("Ese correo ya existe o los datos no son válidos." if isinstance(exc, sqlite3.IntegrityError) else str(exc))
    return render_template("auth.html", action="registrar")


@app.route("/entrar", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Correo o contraseña incorrectos.")
    return render_template("auth.html", action="entrar")


@app.post("/salir")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/solicitudes/nueva", methods=["GET", "POST"])
@admin_required
def new_rfq():
    db = get_db()
    suppliers = db.execute(
        "SELECT c.id,c.name,c.city,c.country FROM companies c "
        "LEFT JOIN supplier_profiles p ON p.company_id=c.id "
        "LEFT JOIN supplier_relationships r ON r.supplier_id=c.id AND r.buyer_id=? "
        "WHERE c.id<>? AND c.can_sell=1 AND "
        "(COALESCE(p.accepts_new_buyers,1)=1 OR r.status='approved') "
        "ORDER BY c.name", (g.user["company_id"], g.user["company_id"]),
    ).fetchall()
    if request.method == "POST":
        try:
            items = []
            products = request.form.getlist("item_product")
            quantities = request.form.getlist("item_quantity")
            units = request.form.getlist("item_unit")
            specifications = request.form.getlist("item_specification")
            if products:
                if not (len(products) == len(quantities) == len(units) == len(specifications)) or len(products) > 8:
                    raise ValueError("Revisa los productos de la solicitud (máximo 8).")
                for raw_product, raw_quantity, raw_unit, raw_spec in zip(products, quantities, units, specifications):
                    if not any((raw_product.strip(), raw_quantity.strip(), raw_unit.strip(), raw_spec.strip())):
                        continue
                    if not raw_product.strip() or not raw_unit.strip() or len(raw_product.strip()) > 160 or len(raw_unit.strip()) > 30 or len(raw_spec.strip()) > 500:
                        raise ValueError("Completa producto, cantidad y unidad de cada renglón utilizado.")
                    items.append((raw_product.strip(), raw_spec.strip(),
                                  str(decimal_value(raw_quantity, "cantidad")), raw_unit.strip()))
                if not items:
                    raise ValueError("Agrega por lo menos un producto.")
                product = items[0][0] if len(items) == 1 else f"Compra de {len(items)} productos"
                specification = ""
                quantity = Decimal("1") if len(items) > 1 else Decimal(items[0][2])
                unit = "solicitud" if len(items) > 1 else items[0][3]
            else:
                # Compatibility with RFQs created using the first pilot form.
                product = text_field("product")
                specification = request.form.get("specification", "").strip()[:500]
                quantity = amount("quantity")
                unit = text_field("unit", 30)
            destination = text_field("destination")
            required_date = valid_date("required_date")
            ids = {int(x) for x in request.form.getlist("supplier_id")}
            available = {x["id"] for x in suppliers}
            if not ids or not ids.issubset(available):
                raise ValueError("Selecciona al menos un proveedor del directorio.")
            with db:
                rfq_id = db.execute(
                    "INSERT INTO rfqs(buyer_id,product,specification,quantity,unit,destination,"
                    "required_date,created_by) VALUES(?,?,?,?,?,?,?,?)",
                    (g.user["company_id"], product, specification, str(quantity), unit,
                     destination, required_date, g.user["id"]),
                ).lastrowid
                db.executemany("INSERT INTO invitations(rfq_id,supplier_id) VALUES(?,?)",
                               [(rfq_id, i) for i in ids])
                db.executemany(
                    "INSERT INTO rfq_items(rfq_id,position,product,specification,quantity,unit) "
                    "VALUES(?,?,?,?,?,?)",
                    [(rfq_id, n, *item) for n, item in enumerate(items, 1)],
                )
                audit(db, "rfq", rfq_id, "created")
            flash("Solicitud enviada a los proveedores seleccionados.")
            return redirect(url_for("rfq_detail", rfq_id=rfq_id))
        except (ValueError, OverflowError) as exc:
            flash(str(exc))
    return render_template("new_rfq.html", suppliers=suppliers)


def accessible_rfq(rfq_id):
    row = get_db().execute(
        "SELECT r.*, c.name AS buyer_name FROM rfqs r JOIN companies c ON c.id=r.buyer_id "
        "WHERE r.id=? AND (r.buyer_id=? OR EXISTS "
        "(SELECT 1 FROM invitations i WHERE i.rfq_id=r.id AND i.supplier_id=?))",
        (rfq_id, g.user["company_id"], g.user["company_id"]),
    ).fetchone()
    if row is None:
        abort(404)
    return row


@app.get("/solicitudes/<int:rfq_id>")
@login_required
def rfq_detail(rfq_id):
    db = get_db()
    rfq = accessible_rfq(rfq_id)
    items = db.execute("SELECT * FROM rfq_items WHERE rfq_id=? ORDER BY position", (rfq_id,)).fetchall()
    own = rfq["buyer_id"] == g.user["company_id"]
    if own:
        invitees = db.execute(
            "SELECT c.id,c.name FROM invitations i JOIN companies c ON c.id=i.supplier_id "
            "WHERE i.rfq_id=? ORDER BY c.name", (rfq_id,)
        ).fetchall()
        quotes = db.execute(
            "SELECT q.*, i.supplier_id, c.name AS supplier_name FROM quotes q "
            "JOIN invitations i ON i.id=q.invitation_id "
            "JOIN companies c ON c.id=i.supplier_id WHERE i.rfq_id=? ORDER BY q.id",
            (rfq_id,),
        ).fetchall()
        if items:
            quotes = [dict(q) for q in quotes]
            for quote_row in quotes:
                quote_row["items"] = {
                    x["rfq_item_id"]: x for x in db.execute(
                        "SELECT * FROM quote_items WHERE quote_id=?", (quote_row["id"],)
                    ).fetchall()
                }
                quote_row["estimated_cents"] = quote_row["shipping_cents"] + sum(
                    int((Decimal(item["quantity"]) * quote_row["items"][item["id"]]["unit_price_cents"]).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )) for item in items if item["id"] in quote_row["items"]
                )
        else:
            quotes = [dict(q, estimated_cents=int(
                (Decimal(rfq["quantity"]) * q["unit_price_cents"]).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                ) + q["shipping_cents"]
            )) for q in quotes]
        invitation = None
    else:
        invitees = []
        profile = db.execute("SELECT default_payment_terms FROM supplier_profiles WHERE company_id=?",
                             (g.user["company_id"],)).fetchone()
        invitation = db.execute(
            "SELECT i.id AS invitation_id, q.id AS quote_id FROM invitations i "
            "LEFT JOIN quotes q ON q.invitation_id=i.id "
            "WHERE i.rfq_id=? AND i.supplier_id=?",
            (rfq_id, g.user["company_id"]),
        ).fetchone()
        quotes = db.execute(
            "SELECT q.* FROM quotes q JOIN invitations i ON i.id=q.invitation_id "
            "WHERE i.rfq_id=? AND i.supplier_id=?",
            (rfq_id, g.user["company_id"]),
        ).fetchall()
        if items and quotes:
            quotes = [dict(quotes[0])]
            quotes[0]["items"] = {
                x["rfq_item_id"]: x for x in db.execute(
                    "SELECT * FROM quote_items WHERE quote_id=?", (quotes[0]["id"],)
                ).fetchall()
            }
    pos = db.execute(
        "SELECT id,supplier_id FROM purchase_orders WHERE rfq_id=? AND "
        "(buyer_id=? OR supplier_id=?) ORDER BY id",
        (rfq_id, g.user["company_id"], g.user["company_id"]),
    ).fetchall()
    return render_template("rfq.html", rfq=rfq, quotes=quotes, own=own,
                           default_terms=profile["default_payment_terms"] if not own and profile else "",
                           invitation=invitation, pos=pos, items=items, invitees=invitees)


@app.route("/solicitudes/<int:rfq_id>/conversacion/<int:supplier_id>", methods=["GET", "POST"])
@login_required
def conversation(rfq_id, supplier_id):
    db = get_db()
    rfq = accessible_rfq(rfq_id)
    invitation = db.execute(
        "SELECT c.name AS supplier_name FROM invitations i "
        "JOIN companies c ON c.id=i.supplier_id WHERE i.rfq_id=? AND i.supplier_id=?",
        (rfq_id, supplier_id),
    ).fetchone()
    if invitation is None or g.user["company_id"] not in (rfq["buyer_id"], supplier_id):
        abort(404)
    if request.method == "POST":
        try:
            body = text_field("body", 2000)
            with db:
                message_id = db.execute(
                    "INSERT INTO rfq_messages(rfq_id,supplier_id,sender_company_id,sender_user_id,body) "
                    "VALUES(?,?,?,?,?)",
                    (rfq_id, supplier_id, g.user["company_id"], g.user["id"], body),
                ).lastrowid
                audit(db, "message", message_id, "sent")
            return redirect(url_for("conversation", rfq_id=rfq_id, supplier_id=supplier_id))
        except ValueError as exc:
            flash(str(exc))
    messages = db.execute(
        "SELECT m.id,m.body,m.created_at,c.name AS sender_name "
        "FROM rfq_messages m JOIN companies c ON c.id=m.sender_company_id "
        "WHERE m.rfq_id=? AND m.supplier_id=? ORDER BY m.id",
        (rfq_id, supplier_id),
    ).fetchall()
    return render_template("conversation.html", rfq=rfq, supplier_id=supplier_id,
                           supplier_name=invitation["supplier_name"], messages=messages)


@app.post("/solicitudes/<int:rfq_id>/cotizar")
@admin_required
def quote(rfq_id):
    db = get_db()
    rfq = accessible_rfq(rfq_id)
    if rfq["buyer_id"] == g.user["company_id"] or rfq["status"] != "open":
        abort(404)
    invitation = db.execute(
        "SELECT id FROM invitations WHERE rfq_id=? AND supplier_id=?",
        (rfq_id, g.user["company_id"]),
    ).fetchone()
    if invitation is None:
        abort(404)
    items = db.execute("SELECT * FROM rfq_items WHERE rfq_id=?", (rfq_id,)).fetchall()
    try:
        if items:
            prices = [(item["id"],
                       cents_value(request.form.get(f"item_price_{item['id']}", ""), "precio"),
                       decimal_value(request.form.get(f"item_available_{item['id']}", ""), "disponibilidad", allow_zero=True))
                      for item in items]
            if not any(available > 0 for _, _, available in prices):
                raise ValueError("Indica disponibilidad para al menos un producto.")
            price = 0  # Legacy summary fields; line prices live in quote_items.
            available = Decimal("0")
        else:
            price = cents("unit_price")
            available = amount("available_quantity")
        shipping = cents("shipping")
        delivery = valid_date("delivery_date")
        currency = text_field("currency", 3)
        if currency not in ("USD", "MXN"):
            raise ValueError("Selecciona USD o MXN.")
        terms = text_field("payment_terms", 160)
        notes = request.form.get("notes", "").strip()[:500]
        with db:
            quote_id = db.execute(
                "INSERT INTO quotes(invitation_id,unit_price_cents,shipping_cents,currency,"
                "available_quantity,delivery_date,payment_terms,notes,created_by) "
                "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(invitation_id) DO UPDATE SET "
                "unit_price_cents=excluded.unit_price_cents,shipping_cents=excluded.shipping_cents,"
                "currency=excluded.currency,available_quantity=excluded.available_quantity,"
                "delivery_date=excluded.delivery_date,payment_terms=excluded.payment_terms,"
                "notes=excluded.notes,created_by=excluded.created_by,created_at=CURRENT_TIMESTAMP",
                (invitation["id"], price, shipping, currency, str(available),
                 delivery, terms, notes, g.user["id"]),
            ).lastrowid
            if items:
                quote_id = db.execute(
                    "SELECT id FROM quotes WHERE invitation_id=?", (invitation["id"],)
                ).fetchone()["id"]
                db.execute("DELETE FROM quote_items WHERE quote_id=?", (quote_id,))
                db.executemany(
                    "INSERT INTO quote_items(quote_id,rfq_item_id,unit_price_cents,available_quantity) "
                    "VALUES(?,?,?,?)",
                    [(quote_id, item_id, cents_amount, str(available_qty))
                     for item_id, cents_amount, available_qty in prices],
                )
            audit(db, "rfq", rfq_id, "quote_submitted")
        flash("Cotización privada guardada.")
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for("rfq_detail", rfq_id=rfq_id))


@app.post("/solicitudes/<int:rfq_id>/aprobar/<int:quote_id>")
@admin_required
def award(rfq_id, quote_id):
    db = get_db()
    rfq = db.execute("SELECT * FROM rfqs WHERE id=? AND buyer_id=?",
                     (rfq_id, g.user["company_id"])).fetchone()
    if rfq is None or rfq["status"] != "open":
        abort(404)
    if db.execute("SELECT 1 FROM rfq_items WHERE rfq_id=?", (rfq_id,)).fetchone():
        abort(404)
    quote_row = db.execute(
        "SELECT q.*, i.supplier_id FROM quotes q JOIN invitations i ON i.id=q.invitation_id "
        "WHERE q.id=? AND i.rfq_id=?", (quote_id, rfq_id)
    ).fetchone()
    if quote_row is None:
        abort(404)
    quantity = Decimal(rfq["quantity"])
    if Decimal(quote_row["available_quantity"]) < quantity:
        flash("Este proveedor no tiene suficiente cantidad para la solicitud completa.")
        return redirect(url_for("rfq_detail", rfq_id=rfq_id))
    total = int((quantity * quote_row["unit_price_cents"]).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )) + quote_row["shipping_cents"]
    with db:
        changed = db.execute(
            "UPDATE rfqs SET status='awarded' WHERE id=? AND buyer_id=? AND status='open'",
            (rfq_id, g.user["company_id"]),
        ).rowcount
        if changed != 1:
            abort(409)
        po_id = db.execute(
            "INSERT INTO purchase_orders(rfq_id,quote_id,buyer_id,supplier_id,quantity,"
            "unit_price_cents,shipping_cents,total_cents,currency,payment_terms) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (rfq_id, quote_id, g.user["company_id"], quote_row["supplier_id"],
             str(quantity), quote_row["unit_price_cents"], quote_row["shipping_cents"],
             total, quote_row["currency"], quote_row["payment_terms"]),
        ).lastrowid
        audit(db, "po", po_id, "created_by_buyer")
    flash("Compra aprobada. El proveedor debe revisar las condiciones y liberarla.")
    return redirect(url_for("po_detail", po_id=po_id))


@app.post("/solicitudes/<int:rfq_id>/aprobar-productos")
@admin_required
def award_items(rfq_id):
    db = get_db()
    rfq = db.execute(
        "SELECT * FROM rfqs WHERE id=? AND buyer_id=? AND status='open'",
        (rfq_id, g.user["company_id"]),
    ).fetchone()
    if rfq is None:
        abort(404)
    items = db.execute("SELECT * FROM rfq_items WHERE rfq_id=? ORDER BY position", (rfq_id,)).fetchall()
    if not items:
        abort(404)
    groups = {}
    try:
        for item in items:
            quote_id = int(request.form.get(f"item_quote_{item['id']}", ""))
            offer = db.execute(
                "SELECT qi.unit_price_cents,qi.available_quantity,q.id AS quote_id,"
                "q.shipping_cents,q.currency,q.payment_terms,i.supplier_id "
                "FROM quote_items qi JOIN quotes q ON q.id=qi.quote_id "
                "JOIN invitations i ON i.id=q.invitation_id "
                "WHERE qi.rfq_item_id=? AND q.id=? AND i.rfq_id=?",
                (item["id"], quote_id, rfq_id),
            ).fetchone()
            if offer is None or Decimal(offer["available_quantity"]) < Decimal(item["quantity"]):
                raise ValueError(f"La propuesta para {item['product']} no cubre la cantidad solicitada.")
            group = groups.setdefault(quote_id, {"offer": offer, "items": []})
            group["items"].append((item, offer["unit_price_cents"]))
    except (ValueError, TypeError) as exc:
        flash(str(exc) if str(exc) else "Elige un proveedor para cada producto.")
        return redirect(url_for("rfq_detail", rfq_id=rfq_id))

    with db:
        if db.execute(
            "UPDATE rfqs SET status='awarded' WHERE id=? AND buyer_id=? AND status='open'",
            (rfq_id, g.user["company_id"]),
        ).rowcount != 1:
            abort(409)
        for quote_id, group in groups.items():
            offer = group["offer"]
            line_total = sum(int((Decimal(item["quantity"]) * unit_price).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )) for item, unit_price in group["items"])
            po_id = db.execute(
                "INSERT INTO purchase_orders(rfq_id,quote_id,buyer_id,supplier_id,quantity,"
                "unit_price_cents,shipping_cents,total_cents,currency,payment_terms) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (rfq_id, quote_id, g.user["company_id"], offer["supplier_id"],
                 "1", 0, offer["shipping_cents"], line_total + offer["shipping_cents"],
                 offer["currency"], offer["payment_terms"]),
            ).lastrowid
            db.executemany(
                "INSERT INTO po_items(po_id,rfq_item_id,product,quantity,unit,unit_price_cents) "
                "VALUES(?,?,?,?,?,?)",
                [(po_id, item["id"], item["product"], item["quantity"],
                  item["unit"], unit_price) for item, unit_price in group["items"]],
            )
            audit(db, "po", po_id, "created_by_buyer")
    flash(f"Compra aprobada. Se generaron {len(groups)} órdenes de compra independientes.")
    return redirect(url_for("rfq_detail", rfq_id=rfq_id))


def accessible_po(po_id):
    po = get_db().execute(
        "SELECT p.*, r.product,r.specification,r.unit,r.destination,r.required_date,"
        "buyer.name AS buyer_name,supplier.name AS supplier_name "
        "FROM purchase_orders p JOIN rfqs r ON r.id=p.rfq_id "
        "JOIN companies buyer ON buyer.id=p.buyer_id "
        "JOIN companies supplier ON supplier.id=p.supplier_id "
        "WHERE p.id=? AND (p.buyer_id=? OR p.supplier_id=?)",
        (po_id, g.user["company_id"], g.user["company_id"]),
    ).fetchone()
    if po is None:
        abort(404)
    return po


@app.get("/ordenes/<int:po_id>")
@login_required
def po_detail(po_id):
    po = accessible_po(po_id)
    db = get_db()
    receipts = db.execute(
        "SELECT * FROM receipts WHERE po_id=? ORDER BY id", (po_id,)
    ).fetchall()
    po_items = db.execute("SELECT * FROM po_items WHERE po_id=? ORDER BY id", (po_id,)).fetchall()
    receipt_lines = {}
    line_remaining = {}
    for item in po_items:
        receipt_lines[item["id"]] = db.execute(
            "SELECT * FROM receipt_items WHERE po_item_id=? ORDER BY id", (item["id"],)
        ).fetchall()
        used = sum((Decimal(r["received_quantity"]) + Decimal(r["rejected_quantity"])
                    for r in receipt_lines[item["id"]]), Decimal(0))
        line_remaining[item["id"]] = Decimal(item["quantity"]) - used
    accounted = sum((Decimal(r["received_quantity"]) + Decimal(r["rejected_quantity"])
                     for r in receipts), Decimal(0))
    return render_template("po.html", po=po, receipts=receipts,
                           po_items=po_items, receipt_lines=receipt_lines,
                           line_remaining=line_remaining,
                           remaining=Decimal(po["quantity"]) - accounted,
                           own=po["buyer_id"] == g.user["company_id"])


@app.post("/ordenes/<int:po_id>/liberar")
@admin_required
def release(po_id):
    po = accessible_po(po_id)
    if po["supplier_id"] != g.user["company_id"] or po["status"] != "pending_release":
        abort(404)
    db = get_db()
    with db:
        db.execute("UPDATE purchase_orders SET status='released' WHERE id=? AND status='pending_release'",
                   (po_id,))
        audit(db, "po", po_id, "released_by_supplier")
    flash("Orden liberada por el proveedor.")
    return redirect(url_for("po_detail", po_id=po_id))


@app.post("/ordenes/<int:po_id>/recibir")
@admin_required
def receive(po_id):
    po = accessible_po(po_id)
    if po["buyer_id"] != g.user["company_id"] or po["status"] not in ("released", "partial"):
        abort(404)
    db = get_db()
    if db.execute("SELECT 1 FROM po_items WHERE po_id=?", (po_id,)).fetchone():
        abort(404)
    try:
        received = amount("received_quantity", allow_zero=True)
        rejected = amount("rejected_quantity", allow_zero=True)
        if received + rejected <= 0:
            raise ValueError("Indica una cantidad recibida o rechazada.")
        notes = request.form.get("notes", "").strip()[:500]
        accounted = db.execute(
            "SELECT received_quantity,rejected_quantity FROM receipts WHERE po_id=?", (po_id,)
        ).fetchall()
        previous = sum((Decimal(x["received_quantity"]) + Decimal(x["rejected_quantity"])
                        for x in accounted), Decimal(0))
        current = previous + received + rejected
        if current > Decimal(po["quantity"]):
            raise ValueError("La recepción supera la cantidad de la orden.")
        status = "received" if current == Decimal(po["quantity"]) else "partial"
        with db:
            db.execute(
                "INSERT INTO receipts(po_id,received_quantity,rejected_quantity,notes,received_by) "
                "VALUES(?,?,?,?,?)", (po_id, str(received), str(rejected), notes, g.user["id"]),
            )
            db.execute("UPDATE purchase_orders SET status=? WHERE id=?", (status, po_id))
            audit(db, "po", po_id, "receipt_recorded")
        flash("Recepción registrada.")
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for("po_detail", po_id=po_id))


@app.post("/ordenes/<int:po_id>/renglones/<int:po_item_id>/recibir")
@admin_required
def receive_line(po_id, po_item_id):
    po = accessible_po(po_id)
    if po["buyer_id"] != g.user["company_id"] or po["status"] not in ("released", "partial"):
        abort(404)
    db = get_db()
    item = db.execute("SELECT * FROM po_items WHERE id=? AND po_id=?", (po_item_id, po_id)).fetchone()
    if item is None:
        abort(404)
    try:
        received = amount("received_quantity", allow_zero=True)
        rejected = amount("rejected_quantity", allow_zero=True)
        if received + rejected <= 0:
            raise ValueError("Indica una cantidad recibida o rechazada.")
        note = request.form.get("notes", "").strip()[:500]
        with db:
            previous = db.execute(
                "SELECT received_quantity,rejected_quantity FROM receipt_items WHERE po_item_id=?",
                (po_item_id,),
            ).fetchall()
            used = sum((Decimal(x["received_quantity"]) + Decimal(x["rejected_quantity"])
                        for x in previous), Decimal(0))
            if used + received + rejected > Decimal(item["quantity"]):
                raise ValueError("La recepción supera la cantidad asignada a este producto.")
            db.execute(
                "INSERT INTO receipt_items(po_item_id,received_quantity,rejected_quantity,notes,received_by) "
                "VALUES(?,?,?,?,?)", (po_item_id, str(received), str(rejected), note, g.user["id"]),
            )
            others = db.execute("SELECT id,quantity FROM po_items WHERE po_id=?", (po_id,)).fetchall()
            complete = True
            for other in others:
                rows = db.execute(
                    "SELECT received_quantity,rejected_quantity FROM receipt_items WHERE po_item_id=?",
                    (other["id"],),
                ).fetchall()
                accounted = sum((Decimal(x["received_quantity"]) + Decimal(x["rejected_quantity"])
                                 for x in rows), Decimal(0))
                if accounted < Decimal(other["quantity"]):
                    complete = False
            db.execute("UPDATE purchase_orders SET status=? WHERE id=?",
                       ("received" if complete else "partial", po_id))
            audit(db, "po", po_id, "line_receipt_recorded")
        flash("Recepción del producto registrada.")
    except ValueError as exc:
        flash(str(exc))
    return redirect(url_for("po_detail", po_id=po_id))


init_db()

if __name__ == "__main__":
    app.run(debug=False)
