# QuickBooks en Compras: lectura únicamente

**Estado actual:** este paquete no incluye OAuth, credenciales ni conexión activa con QuickBooks o Dallas Fresh App. Productos, ventas, existencias y precios se capturan en el piloto dentro de cada empresa. No se debe presentar la predicción como alimentada por ventas de QuickBooks mientras no exista una lectura autorizada y comprobada.

**Contrato para la siguiente integración:** cada empresa autoriza por separado su compañía QuickBooks mediante OAuth 2.0 de solo lectura. El adaptador leerá productos, ventas pertinentes, unidades e inventario si existen y mapeará identificadores externos por `company_id`; registrará origen, fecha de sincronización y errores. Debe conciliar ventas por libra, cajas recibidas, mermas y ajustes sin duplicarlos. No reutilizar credenciales del Connector de Dallas Fresh ni consultar los datos de otra empresa.

La orden de compra creada aquí es **interna a Red B2B**; QuickBooks no recibe PurchaseOrder, Bill, Invoice ni actualización de inventario. Al integrarse con la vista de Dallas Fresh para clientes, el pedido del cliente seguirá su flujo de surtido propio, y la compra a proveedores conservará su propio estado y permisos.

Para activar una conexión real hacen falta las credenciales de la aplicación QuickBooks, la autorización OAuth de la compañía correspondiente, mapeo de unidades e identificadores y prueba de solo lectura en sandbox antes de tocar datos activos. Los secretos se guardan únicamente como variables de entorno, nunca en GitHub.
