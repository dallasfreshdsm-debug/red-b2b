"""Buyer-owned inventory estimates, private supplier prices and direct purchase orders."""

from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_CEILING

from flask import abort, flash, g, redirect, render_template, request, url_for


def install(app, get_db, admin_required, login_required, audit, decimal_value, cents_value):
    def owned_product(product_id):
        row = get_db().execute(
            "SELECT * FROM buyer_products WHERE id=? AND buyer_id=?",
            (product_id, g.user["company_id"]),
        ).fetchone()
        if row is None:
            abort(404)
        return row

    def recommendation(db, product):
        pid, buyer = product["id"], g.user["company_id"]
        used = db.execute(
            "SELECT kind,quantity,occurred_at FROM product_usage "
            "WHERE buyer_id=? AND product_id=? AND id>? ORDER BY id",
            (buyer, pid, product["snapshot_usage_id"]),
        ).fetchall()
        consumption = sum(((-1 if u["kind"] == "receipt" else 1) * Decimal(u["quantity"]) for u in used), Decimal(0))
        stock = max(Decimal(0), Decimal(product["stock_snapshot"]) - consumption)
        # Sales averaged over the last 30 calendar days; recorded waste is counted once.
        sales = db.execute(
            "SELECT quantity FROM product_usage WHERE buyer_id=? AND product_id=? "
            "AND kind='sale' AND date(occurred_at)>=date('now','-29 days')",
            (buyer, pid),
        ).fetchall()
        daily = sum((Decimal(x["quantity"]) for x in sales), Decimal(0)) / 30
        forecast = daily * product["lead_days"] * (1 + Decimal(product["waste_percent"]) / 100)
        pending = db.execute(
            "SELECT i.quantity,i.pack_size FROM direct_order_items i "
            "JOIN direct_orders o ON o.id=i.order_id WHERE o.buyer_id=? AND i.product_id=? "
            "AND o.status IN ('pending_release','released')",
            (buyer, pid),
        ).fetchall()
        on_order = sum((Decimal(x["quantity"]) * Decimal(x["pack_size"]) for x in pending), Decimal(0))
        shortage = max(Decimal(0), Decimal(product["stock_target"]) + forecast - stock - on_order)
        boxes = int((shortage / Decimal(product["pack_size"])).to_integral_value(rounding=ROUND_CEILING))
        return {"product": product, "stock": stock, "forecast": forecast,
                "on_order": on_order, "boxes": boxes, "daily": daily}

    @app.get("/compras")
    @login_required
    def buying_home():
        db = get_db()
        buyer = g.user["company_id"]
        products = db.execute("SELECT * FROM buyer_products WHERE buyer_id=? ORDER BY name", (buyer,)).fetchall()
        offers = db.execute(
            "SELECT o.*,c.name AS supplier_name FROM product_offers o "
            "JOIN companies c ON c.id=o.supplier_id WHERE o.buyer_id=? AND o.valid_until>=date('now') "
            "AND c.can_sell=1 AND (EXISTS(SELECT 1 FROM supplier_relationships r WHERE r.buyer_id=o.buyer_id "
            "AND r.supplier_id=o.supplier_id AND r.status='approved') OR "
            "COALESCE((SELECT accepts_new_buyers FROM supplier_profiles WHERE company_id=o.supplier_id),1)=1) "
            "ORDER BY o.product_id,o.currency,o.unit_price_cents", (buyer,),
        ).fetchall()
        by_product = defaultdict(list)
        for offer in offers:
            by_product[offer["product_id"]].append(offer)
        rows = [dict(**recommendation(db, p), offers=by_product[p["id"]]) for p in products]
        start, end, supplier = request.args.get("from", ""), request.args.get("to", ""), request.args.get("supplier", "")
        for value in (start, end):
            if value:
                try:
                    date.fromisoformat(value)
                except ValueError:
                    abort(400)
        if supplier and (not supplier.isdigit() or len(supplier) > 12):
            abort(400)
        orders = db.execute(
            "SELECT 'direct' AS order_type,o.id,o.created_at,o.status,o.currency,o.total_cents,"
            "c.name AS supplier_name FROM direct_orders o JOIN companies c ON c.id=o.supplier_id "
            "WHERE o.buyer_id=? AND (?='' OR date(o.created_at)>=?) AND (?='' OR date(o.created_at)<=?) "
            "AND (?='' OR o.supplier_id=?) UNION ALL "
            "SELECT 'rfq' AS order_type,o.id,o.created_at,o.status,o.currency,o.total_cents,"
            "c.name AS supplier_name FROM purchase_orders o JOIN companies c ON c.id=o.supplier_id "
            "WHERE o.buyer_id=? AND (?='' OR date(o.created_at)>=?) AND (?='' OR date(o.created_at)<=?) "
            "AND (?='' OR o.supplier_id=?) ORDER BY 3 DESC,2 DESC",
            (buyer, start, start, end, end, supplier, supplier,
             buyer, start, start, end, end, supplier, supplier),
        ).fetchall()
        suppliers = db.execute(
            "SELECT DISTINCT c.id,c.name FROM companies c WHERE c.id IN "
            "(SELECT supplier_id FROM direct_orders WHERE buyer_id=? UNION "
            "SELECT supplier_id FROM purchase_orders WHERE buyer_id=?) ORDER BY c.name", (buyer,buyer),
        ).fetchall()
        return render_template("buying.html", rows=rows, orders=orders, suppliers=suppliers,
                               start=start, end=end, supplier=supplier)

    @app.route("/compras/productos", methods=["GET", "POST"])
    @admin_required
    def manage_products():
        db = get_db()
        buyer = g.user["company_id"]
        if request.method == "POST":
            try:
                name = request.form.get("name", "").strip()
                purchase_unit = request.form.get("purchase_unit", "").strip()
                sale_unit = request.form.get("sale_unit", "").strip()
                if not name or len(name)>160 or not purchase_unit or len(purchase_unit)>30 or not sale_unit or len(sale_unit)>30:
                    raise ValueError("Revisa el nombre y las unidades del producto.")
                pack = decimal_value(request.form.get("pack_size"), "libras por caja")
                stock = decimal_value(request.form.get("stock_snapshot"), "existencia", allow_zero=True)
                target = decimal_value(request.form.get("stock_target"), "objetivo", allow_zero=True)
                waste = decimal_value(request.form.get("waste_percent"), "merma", allow_zero=True)
                lead = int(request.form.get("lead_days", ""))
                if lead < 0 or lead > 90 or waste > 100:
                    raise ValueError("Revisa el plazo y porcentaje de merma.")
                with db:
                    pid = db.execute(
                        "INSERT INTO buyer_products(buyer_id,name,purchase_unit,sale_unit,pack_size,stock_target,"
                        "stock_snapshot,lead_days,waste_percent) VALUES(?,?,?,?,?,?,?,?,?)",
                        (buyer,name,purchase_unit,sale_unit,str(pack),str(target),str(stock),lead,str(waste)),
                    ).lastrowid
                    audit(db,"product",pid,"configured")
                flash("Producto configurado; existencia marcada como estimada.")
                return redirect(url_for("manage_products"))
            except (ValueError, OverflowError):
                flash("Revisa cantidades, unidades y plazo del producto.")
        products = db.execute("SELECT * FROM buyer_products WHERE buyer_id=? ORDER BY name", (buyer,)).fetchall()
        suppliers = db.execute(
            "SELECT c.id,c.name FROM companies c LEFT JOIN supplier_profiles p ON p.company_id=c.id "
            "LEFT JOIN supplier_relationships r ON r.supplier_id=c.id AND r.buyer_id=? "
            "WHERE c.id<>? AND c.can_sell=1 AND (COALESCE(p.accepts_new_buyers,1)=1 OR r.status='approved') ORDER BY c.name",
            (buyer,buyer),
        ).fetchall()
        offers = db.execute(
            "SELECT o.*,c.name supplier_name FROM product_offers o JOIN companies c ON c.id=o.supplier_id "
            "WHERE o.buyer_id=? ORDER BY o.product_id,c.name", (buyer,),
        ).fetchall()
        return render_template("buying_config.html",products=products,suppliers=suppliers,offers=offers)

    @app.post("/compras/productos/<int:product_id>/conteo")
    @admin_required
    def stock_count(product_id):
        owned_product(product_id)
        try:
            qty = decimal_value(request.form.get("quantity"), "existencia", allow_zero=True)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("manage_products"))
        db=get_db()
        with db:
            db.execute("UPDATE buyer_products SET stock_snapshot=?,snapshot_at=CURRENT_TIMESTAMP,"
                       "snapshot_usage_id=COALESCE((SELECT MAX(id) FROM product_usage WHERE buyer_id=? AND product_id=?),0) "
                       "WHERE id=? AND buyer_id=?",
                       (str(qty),g.user["company_id"],product_id,product_id,g.user["company_id"]))
            audit(db,"product",product_id,"stock_count")
        flash("Conteo actualizado; se descontará el consumo posterior.")
        return redirect(url_for("manage_products"))

    @app.post("/compras/productos/<int:product_id>/consumo")
    @admin_required
    def record_usage(product_id):
        owned_product(product_id)
        kind=request.form.get("kind")
        if kind not in ("sale","waste","internal"):
            abort(400)
        try:
            qty=decimal_value(request.form.get("quantity"),"cantidad")
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("manage_products"))
        db=get_db()
        with db:
            db.execute("INSERT INTO product_usage(buyer_id,product_id,quantity,kind) VALUES(?,?,?,?)",
                       (g.user["company_id"],product_id,str(qty),kind))
            audit(db,"product",product_id,"usage_"+kind)
        flash("Consumo registrado.")
        return redirect(url_for("manage_products"))

    @app.post("/compras/productos/<int:product_id>/precios")
    @admin_required
    def set_offer(product_id):
        owned_product(product_id)
        try:
            supplier_id=int(request.form.get("supplier_id", ""))
            supplier=get_db().execute(
                "SELECT c.id FROM companies c LEFT JOIN supplier_profiles p ON p.company_id=c.id "
                "LEFT JOIN supplier_relationships r ON r.supplier_id=c.id AND r.buyer_id=? "
                "WHERE c.id=? AND c.id<>? AND c.can_sell=1 "
                "AND (COALESCE(p.accepts_new_buyers,1)=1 OR r.status='approved')",
                (g.user["company_id"],supplier_id,g.user["company_id"]),
            ).fetchone()
            price=cents_value(request.form.get("price"),"precio")
            currency=request.form.get("currency")
            valid_until=request.form.get("valid_until", "")
            if not supplier or currency not in ("USD","MXN") or date.fromisoformat(valid_until)<date.today():
                raise ValueError("Revisa proveedor, moneda y vigencia.")
        except (ValueError,OverflowError):
            flash("Revisa proveedor, moneda, precio y vigencia.")
            return redirect(url_for("manage_products"))
        db=get_db()
        with db:
            db.execute(
                "INSERT INTO product_offers(buyer_id,product_id,supplier_id,unit_price_cents,currency,valid_until) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(buyer_id,product_id,supplier_id) DO UPDATE SET "
                "unit_price_cents=excluded.unit_price_cents,currency=excluded.currency,"
                "valid_until=excluded.valid_until,updated_at=CURRENT_TIMESTAMP",
                (g.user["company_id"],product_id,supplier_id,price,currency,valid_until),
            )
            audit(db,"product",product_id,"buyer_private_offer_updated")
        flash("Precio privado guardado para tu empresa. Verifica su vigencia con el proveedor antes de comprar.")
        return redirect(url_for("manage_products"))

    @app.post("/compras/ordenar")
    @admin_required
    def create_direct_orders():
        db=get_db()
        buyer=g.user["company_id"]
        chosen=[]
        try:
            product_ids=request.form.getlist("product_id")
            if not product_ids or len(product_ids)>50 or len(product_ids)!=len(set(product_ids)):
                raise ValueError("Selecciona entre 1 y 50 productos distintos.")
            currencies=set()
            for raw in product_ids:
                product=owned_product(int(raw))
                qty=int(request.form.get("quantity_"+raw,"0"))
                if qty<0 or qty>100000:
                    raise ValueError("Cantidad inválida.")
                if not qty:
                    continue
                offer_id=int(request.form.get("offer_"+raw,"0"))
                offer=db.execute(
                    "SELECT o.* FROM product_offers o JOIN companies c ON c.id=o.supplier_id "
                    "LEFT JOIN supplier_profiles p ON p.company_id=c.id "
                    "LEFT JOIN supplier_relationships r ON r.supplier_id=c.id AND r.buyer_id=o.buyer_id "
                    "WHERE o.id=? AND o.buyer_id=? AND o.product_id=? AND o.valid_until>=date('now') "
                    "AND c.can_sell=1 AND (COALESCE(p.accepts_new_buyers,1)=1 OR r.status='approved')",
                    (offer_id,buyer,product["id"]),
                ).fetchone()
                if not offer:
                    raise ValueError("Un precio o proveedor ya no está disponible. Revisa la compra.")
                currencies.add(offer["currency"])
                chosen.append((product,qty,offer))
            if not chosen or len(currencies)>1:
                raise ValueError("Elige productos con ofertas vigentes en una sola moneda por envío.")
        except (ValueError,OverflowError) as exc:
            flash(str(exc))
            return redirect(url_for("buying_home"))
        grouped=defaultdict(list)
        for product,qty,offer in chosen:
            grouped[offer["supplier_id"],offer["currency"]].append((product,qty,offer))
        with db:
            for (supplier_id,currency),lines in grouped.items():
                total=sum(qty*offer["unit_price_cents"] for _,qty,offer in lines)
                order_id=db.execute(
                    "INSERT INTO direct_orders(buyer_id,supplier_id,currency,total_cents) VALUES(?,?,?,?)",
                    (buyer,supplier_id,currency,total),
                ).lastrowid
                db.executemany(
                    "INSERT INTO direct_order_items(order_id,product_id,product_name,purchase_unit,pack_size,quantity,unit_price_cents) "
                    "VALUES(?,?,?,?,?,?,?)",
                    [(order_id,p["id"],p["name"],p["purchase_unit"],p["pack_size"],qty,o["unit_price_cents"])
                     for p,qty,o in lines],
                )
                audit(db,"direct_order",order_id,"created")
        flash(f"Se generaron {len(grouped)} órdenes de compra, una por proveedor. Los proveedores pueden ver solo la suya.")
        return redirect(url_for("buying_home"))

    @app.get("/compras/ordenes/<int:order_id>")
    @login_required
    def direct_order_detail(order_id):
        db=get_db()
        order=db.execute(
            "SELECT o.*,b.name buyer_name,s.name supplier_name FROM direct_orders o "
            "JOIN companies b ON b.id=o.buyer_id JOIN companies s ON s.id=o.supplier_id "
            "WHERE o.id=? AND (o.buyer_id=? OR o.supplier_id=?)",
            (order_id,g.user["company_id"],g.user["company_id"]),
        ).fetchone()
        if not order:
            abort(404)
        lines=db.execute("SELECT * FROM direct_order_items WHERE order_id=? ORDER BY id",(order_id,)).fetchall()
        return render_template("direct_order.html",order=order,lines=lines)

    @app.post("/compras/ordenes/<int:order_id>/<action>")
    @admin_required
    def direct_order_transition(order_id,action):
        if action not in ("liberar","recibir"):
            abort(404)
        db=get_db()
        expected,new,party=("pending_release","released","supplier_id") if action=="liberar" else ("released","received","buyer_id")
        with db:
            updated=db.execute(
                f"UPDATE direct_orders SET status=? WHERE id=? AND status=? AND {party}=?",
                (new,order_id,expected,g.user["company_id"]),
            ).rowcount
            if not updated:
                abort(404)
            if action=="recibir":
                order=db.execute("SELECT buyer_id FROM direct_orders WHERE id=?",(order_id,)).fetchone()
                lines=db.execute("SELECT product_id,quantity,pack_size FROM direct_order_items WHERE order_id=?",(order_id,)).fetchall()
                db.executemany(
                    "INSERT INTO product_usage(buyer_id,product_id,quantity,kind) VALUES(?,?,?,'receipt')",
                    [(order["buyer_id"],line["product_id"],str(Decimal(line["quantity"])*Decimal(line["pack_size"]))) for line in lines],
                )
            audit(db,"direct_order",order_id,new)
        flash("Estado de la orden actualizado.")
        return redirect(url_for("direct_order_detail",order_id=order_id))
