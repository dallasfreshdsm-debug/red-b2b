# Estado de la etapa Compras / Proveedores

Este archivo distingue lo probado en el prototipo de las decisiones acumuladas que aún requieren trabajo. No se ha desplegado ni conectado con Dallas Fresh App o Connector.

| Capacidad acordada | Estado actual |
| --- | --- |
| Empresa compradora y proveedora con usuarios separados | Registro inicial y acceso por empresa; falta verificación real y roles detallados |
| Perfil de proveedor y modalidad de entrega | Perfil con entrega propia, pickup o envío, zona, dirección y condiciones sugeridas; falta calendario, mínimos, tarifas por zona y validación de capacidad |
| Proveedor decide a quién cotiza | Puede aceptar nuevas invitaciones o restringirlas a relaciones aprobadas; falta verificación y política contra abuso |
| RFQ de varios productos y propuestas privadas | Funciona con hasta ocho renglones por solicitud; formulario muestra seis; cada proveedor ve únicamente su propuesta |
| Comparación y compra dividida | Se selecciona un proveedor por renglón y se generan órdenes separadas; falta dividir una misma línea y comparar monedas o transporte propio |
| Condiciones de pago y liberación | El comprador aprueba y el proveedor libera manualmente. La red no procesa pagos ni garantiza crédito |
| Chat contextual | Conversación privada por comprador/proveedor vinculada a la RFQ, accesible antes y después de la PO; falta Push y adjuntos |
| Recepción y desempeño | Se registra recibido/rechazado por renglón; faltan documentos, factura de proveedor, pagos y métricas de historial |
| Reposición predictiva inicial | Disponible desde **Compras a proveedores**: presentación compra/venta, conteo, ventas/merma/consumo manual, stock objetivo, promedio de ventas de 30 días, plazo y órdenes pendientes; sugerencia aproximada redondeada a cajas completas. Falta fuente automática de ventas/QuickBooks |
| Ofertas privadas y compra directa | La empresa compradora registra precios privados vigentes por proveedor y producto; puede elegir proveedor y cantidades y crear una orden por proveedor. El proveedor la libera y el comprador confirma recepción completa. Sin fletes, recepciones parciales ni cotización automática |
| Historial de órdenes | Filtro por fecha y proveedor para órdenes directas y órdenes derivadas de cotizaciones, limitado a la empresa compradora |
| Marketplace, oportunidades e IA | Pendiente; conservar privacidad y aprobación humana |
| Red logística y consolidación | Pendiente después de validar compras; incluye transportistas, carga parcial, temperatura, peso, etapas y POD |
| México–EE. UU. e idiomas | Pendiente; diseñar tramos y controles documentales antes de habilitar operaciones reales |
| App unificada con Dallas Fresh | Pendiente de validar la red independiente y acordar contrato de integración |

## Próxima prueba de negocio

Crear tres empresas ficticias: Dallas Fresh como comprador y dos proveedores en Texas. Solicitar Roma y Aguacate, enviar precios privados, adjudicar cada producto a un proveedor, liberar las dos órdenes y registrar un faltante o rechazo de calidad. Revisar con personas reales si los pasos, términos y datos son suficientes antes de integrar cuentas, transporte o IA.
