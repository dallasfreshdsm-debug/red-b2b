# Cómo unir la Red B2B con Dallas Fresh cuando esté probada

Esta versión no toca Dallas Fresh App ni Dallas Fresh Connector. Tampoco contiene credenciales, rutas de conexión o copias de sus datos. La unión futura será una decisión de producto y un proyecto de migración verificado, no una mezcla directa de archivos o tablas.

## Contrato propuesto

1. **Identidad de empresa.** Asignar una correspondencia explícita entre Dallas Fresh y una empresa verificada de Red B2B. Las cuentas de cliente y proveedor se vinculan solo después de validar su titular y consentimiento; no deducir identidades por nombre.
2. **Catálogo.** Importación inicial de productos autorizados, con identificadores externos, unidad y presentación. Los precios de venta, costos y condiciones comerciales permanecen privados en su sistema de origen.
3. **Lectura piloto.** Un adaptador separado consume eventos o una API de solo lectura del sistema de ventas en un entorno de pruebas. No accede directamente a la base productiva ni realiza escrituras.
4. **Eventos versionados.** Cuando exista una necesidad real, publicar `product.changed`, `purchase_order.approved`, `purchase_order.released` y `receipt.recorded`, cada uno con versión, empresa, id externo, fecha e idempotency key. El consumidor confirma y registra errores sin bloquear la operación principal.
5. **Acciones de retorno.** Una recepción podría proponer actualizar disponibilidad en Dallas Fresh, pero inicialmente requiere revisión humana; activar escritura solo después de reconciliación, pruebas y permisos. Nunca crear facturas en QuickBooks desde una coincidencia logística no confirmada.
6. **App unificada.** Un inicio de sesión y navegación comunes pueden presentar ventas, compras y transporte por capacidades, manteniendo el aislamiento lógico y los controles de precio. Unificar interfaz no obliga a fusionar bases de datos de golpe.

## Antes de cualquier conexión

Verificar los paquetes reales de Dallas Fresh App y Connector, contratos de sus API, autenticación, base de datos y flujo de QuickBooks. Probar pedidos y facturas reales en una copia aislada; comparar resultados y preparar reversión. Ninguna de estas verificaciones está cubierta por el prototipo inicial.
