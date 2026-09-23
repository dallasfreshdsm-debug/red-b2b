# Red B2B — etapa proveedores y compras

Prototipo funcional separado de Dallas Fresh App y Dallas Fresh Connector. No importa, modifica ni sincroniza datos de esos sistemas. Incluye registro de empresas, perfiles de proveedor, modalidades de entrega, solicitudes de relación comercial, RFQ de varios productos, propuestas y conversaciones privadas, selección de proveedor por producto, órdenes de compra individuales, liberación y recepción por producto. La base del primer ciclo se actualiza sin borrar sus órdenes anteriores.

## Compras a proveedores

La nueva opción **Compras a proveedores** mantiene el patrón del pedido que ve el cliente de Dallas Fresh, con un encabezado y color propios para reconocer que ahora la empresa compra a *sus* proveedores. En **Configurar productos**, registra nombre, caja y unidad de venta, unidades por caja (por ejemplo 25 lb), conteo, stock objetivo, días para surtir, merma adicional y precios privados vigentes por proveedor. Ingresa ventas, merma o consumo interno en la unidad de venta. La pantalla **Mi compra** muestra una estimación de cajas, deja corregir cantidades y elegir otro proveedor aunque cueste más; al confirmar crea órdenes internas agrupadas por proveedor. El proveedor ve la suya en Inicio, la libera y el comprador confirma la recepción completa. El historial del comprador permite filtrar todas las órdenes por fecha y proveedor.

La estimación toma un conteo inicial, descuenta los consumos registrados desde ese conteo, incluye órdenes abiertas y ventas medias de los últimos 30 días para el plazo configurado, y redondea la necesidad a cajas. La predicción solo conoce los consumos ingresados aquí; **QuickBooks está previsto como fuente de solo lectura pero aún no está conectado**. Las órdenes internas tampoco escriben en QuickBooks. Consulta `docs/QUICKBOOKS_COMPRAS.md` antes de activar una integración real. No mezcles monedas en una misma confirmación ni interpretes los precios introducidos por el comprador como cotizaciones confirmadas por el proveedor.

## Ejecutar localmente

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export B2B_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python app.py
```

Abre `http://127.0.0.1:5000`. Registra primero una empresa compradora y dos proveedoras con correos diferentes. Cada empresa puede comprar y vender en este piloto. Los proveedores completan **Mi perfil**; el comprador consulta **Proveedores** y crea una solicitud con varios productos. Cada proveedor cotiza en privado; el comprador asigna un proveedor por producto y se genera una orden para cada empresa seleccionada. Para uso local, la base SQLite se crea en `instance/red_b2b.sqlite3` y puede configurarse con `B2B_DATABASE`. `B2B_SECRET_KEY` debe ser fijo y secreto entre reinicios. No uses el servidor de desarrollo como servicio público.

Para ejecutar las pruebas desde esta carpeta: `python -m unittest discover -s tests -v`.

## Alcance y límites

- La RFQ puede tener varios productos y seleccionar un proveedor por producto; aún no divide una misma línea entre proveedores. Cada proveedor elegido carga el flete que ofreció una sola vez, incluso si ganó varios productos. No se convierten automáticamente USD y MXN ni se suma el costo del transporte propio del comprador; esos cálculos requieren datos y reglas adicionales antes de recomendar una compra como la más barata.
- El chat está vinculado a la solicitud y aislado por pareja comprador/proveedor; no envía notificaciones fuera de la app. Pagos, inventario, facturas, Push, verificación empresarial, Marketplace y transporte quedan para ciclos siguientes.
- El registro está abierto para facilitar pruebas aisladas. Antes de abrirlo a usuarios reales se requiere verificación empresarial, recuperación de acceso, políticas de abuso y una base de datos PostgreSQL independiente con migraciones y copias de seguridad.
- Los precios y cotizaciones quedan restringidos al comprador de la solicitud y al proveedor que presentó cada propuesta. Las otras empresas invitadas no ven propuestas rivales.
- El comprador acepta la orden, pero el proveedor conserva la decisión de liberarla según sus propias condiciones de pago. Esta app no procesa pagos.
- La integración posterior con Dallas Fresh requerirá contrato de datos versionado, permisos explícitos, lectura inicial sin escritura y validación en un entorno de pruebas. Nunca se conectará a la base activa por defecto.

Consulta `docs/ESPECIFICACION.md` para la visión completa, `docs/ESTADO.md` para saber qué está implementado y `docs/INTEGRACION_FUTURA.md` para el plan de unión.
