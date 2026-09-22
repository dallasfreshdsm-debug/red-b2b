# Red B2B — especificación de arranque

Fecha: 22 de septiembre de 2026. Fuente: las conversaciones compartidas «Revisar Twilio Dallas Fresh» y «Actualizar productos de app». Esta especificación registra decisiones expresadas en ellas; los detalles de implementación que aún no se acordaron figuran al final.

## Identidad y separación

- **Dallas Fresh App** es el sistema existente de ventas, pedidos, clientes, productos, bodega, choferes, Push, facturación y QuickBooks. Sus correcciones acumuladas siguen su propio ciclo de estabilización. No se usarán cambios experimentales de Red B2B en la operación real.
- **Red B2B** es el nuevo proyecto de red entre empresas compradoras, proveedoras y, después, transportistas. Una empresa podrá comprar, vender y transportar según capacidades y permisos. Dallas Fresh podrá participar como primer caso de uso, sin que su sistema de ventas sea reescrito como requisito inicial.
- **MgdaYa** es un proyecto diferente de comercios pequeños y motomandados en Magdalena, Jalisco. No es el nombre de esta red.
- Desarrollo independiente: código, entorno, datos y despliegue separados. Cualquier integración futura con Dallas Fresh será explícita y controlada. Una importación inicial de datos, si se acuerda, debe poder hacerse de solo lectura.

## Propósito y criterio de diseño

Hacer viables transacciones que hoy se pierden por falta de información, confianza o transporte: una empresa publica una necesidad de compra, recibe propuestas privadas, compara costo puesto en destino y calidad de servicio, aprueba la operación y da seguimiento a la recepción. La red también permite descubrir ofertas y completar cargas parciales. La experiencia debe ser sencilla para personas sin experiencia en computadoras o teléfonos; la complejidad de optimización queda detrás de acciones claras. La IA empieza observando y recomendando. Acciones comerciales, pagos y cambios de precio requieren autorización según permisos configurados.

## Etapa 1: compras y relaciones entre empresas

1. Registro breve de empresa y contacto, con datos adicionales a medida que sean necesarios: identidad legal/comercial, ubicación, categorías, zonas atendidas, usuarios y documentos. Invitaciones a proveedores para responder solicitudes; la cuenta inicial de proveedor puede acceder al valor básico sin una venta forzada de suscripción. Presentar más adelante las funciones completas de la plataforma.
2. Una empresa configura sus capacidades: comprar, vender, transportar. Roles de usuario y permisos por empresa; un usuario solo accede a los datos que su empresa y su rol permiten.
3. Directorio de proveedores y relaciones conocidas. El comprador decide a qué proveedores invita; el proveedor decide si cotiza a clientes actuales, empresas verificadas o prospectos. Descubrimiento de nuevos contactos solo bajo reglas de visibilidad y consentimiento comercial.
4. Solicitud de cotización (RFQ) con productos, presentación/calibre, cantidad, destino, fecha, requisitos y modalidades de entrega. Cada proveedor recibe su invitación y envía una propuesta con precio, disponibilidad, calidad/origen cuando aplique, plazo, condiciones de pago y flete. Las propuestas rivales son privadas.
5. Comparación de costo total puesto en destino, disponibilidad, calidad, tiempo, historial de cumplimiento y términos de pago. Se puede repartir una compra entre proveedores. El comprador revisa y aprueba; se generan órdenes de compra (PO) individuales.
6. Flujo de PO: aceptación o liberación por proveedor, preparación, envío o pickup, recepción, faltantes, rechazo por calidad, conciliación con factura de proveedor y seguimiento del pago. Registrar diferencias entre lo pedido y lo recibido, con evidencia e historial de desempeño.
7. Modalidades del proveedor combinables: entrega propia (zona, días, mínimo y cargo), pickup en bodega (dirección, horario, cita y preparación) y envío por tercero (cobertura, plazo y costo). Comparar precio del producto más el costo logístico real. El comprador puede recoger con transporte propio, como hace Dallas Fresh en Texas.
8. Compras predictivas posteriores: demanda esperada menos inventario disponible y en tránsito; sugerir RFQ o compra. La automatización progresa por niveles: sugerencia, cotización asistida, compra con aprobación y solo después límites explícitos de autocompra.

## Privacidad, confianza y condiciones de pago

- Separación real por empresa (`company_id`) y permisos en las consultas y servicios. Costos, precios negociados, cotizaciones, proveedores, clientes, márgenes, chats y datos del ERP de una empresa no se muestran ni se usan para beneficiar comercialmente a otra.
- Tres niveles de precio: oferta pública publicada voluntariamente, catálogo privado para destinatarios autorizados y cotización privada dentro de una RFQ. Ninguna cotización rival se revela al proveedor competidor. Un prospecto no obtiene acceso a precios por registrarse.
- Verificación empresarial progresiva antes de RFQ privadas y operaciones sensibles. Permisos del proveedor para aceptar o rechazar nuevos compradores; límites y revisión de patrones de solicitudes sospechosas. Un puntaje de confianza, si se añade, debe basarse en hechos verificables sin revelar datos privados.
- La relación comercial y las condiciones de pago son entre comprador y proveedor. El comprador acepta la compra, y el proveedor decide si libera la mercancía después de verificar las condiciones que acordaron, incluidas relaciones de crédito preexistentes. La plataforma no garantiza cobros ni obliga a conceder crédito.
- Chat contextual entre las partes antes de confirmar, durante la operación y después; historial vinculado a RFQ, PO y entrega según permisos.

## Marketplace y oportunidades

- Publicación voluntaria de promociones, excedentes y disponibilidad con cantidad, precio, vigencia, ubicación y entrega/pickup. Audiencias elegibles: clientes propios, grupos seleccionados, empresas verificadas o Marketplace de la red. Los precios privados por cliente permanecen privados.
- Un comprador puede descubrir un proveedor, conversar, comprar y mantener una relación futura. Un proveedor pequeño puede encontrar compradores nuevos. Las oportunidades se pueden distribuir mediante Push a destinatarios compatibles y autorizados.
- IA puede detectar excedentes y sugerir precio u oferta, pero la publicación o modificación requiere aprobación. Conectar ofertas con disponibilidad de transporte y mostrar costo total puesto en destino.

## Etapa 2: red logística

- Incorporar transportistas después de que el flujo de compras funcione. Una empresa puede aportar transporte propio además de comprar y vender. Compradores, proveedores o transportistas pueden iniciar búsquedas de carga o capacidad compatible.
- Consolidar cargas parciales por origen, destino/corredor, ventanas de tiempo, equipo, temperatura, producto, peso legal, dimensiones y posiciones de pallet. Una coincidencia propuesta requiere confirmación de las partes. Mostrar a cada comprador solo su mercancía y precio.
- Cotizaciones privadas de transportistas y recomendación basada en costo, puntualidad, seguro, equipo, historial y cumplimiento. Aprovechar capacidad disponible de viajes ya planeados y admitir múltiples recogidas y entregas.
- Seguimiento por tramo con hitos, ETA y Push; prueba de entrega, firma, fotos, temperatura, faltantes y daños cuando correspondan. No exponer ubicación ni datos de otras cargas sin autorización.
- Diseño para movimientos de varios tramos: transporte en México, consolidación, frontera, transfer/cruce, transporte en Estados Unidos y posible cross-dock. Costo y responsables por tramo; vista única de la mercancía para el comprador. Las operaciones transfronterizas exigirán validar documentación, agentes, requisitos sanitarios y responsabilidades antes de habilitarlas.
- Posibilidad futura de varios idiomas, países y monedas; no asumir que toda carga pertenece a un solo camión o transportista.

## Experiencia e integraciones

- Interfaz en lenguaje sencillo con pasos cortos, botones de acción claros, estado visible, ayuda contextual y confirmación antes de acciones irreversibles. Funcionar bien en teléfono y web.
- Integraciones futuras con QuickBooks, Choco y otros ERP como fuentes o destinos de datos, con autorización y trazabilidad. No hacer depender el núcleo de un proveedor específico. Dallas Fresh App sigue operando durante la construcción.
- Notificaciones por eventos pertinentes, evitando ruido. IA activada por datos o eventos necesarios, con auditoría de recomendaciones y acciones humanas.

## Orden de construcción

1. **Base independiente:** repositorio, entorno, identidad de empresa, usuarios/roles, separación de datos, auditoría, esquema de productos y ubicaciones. Datos de demostración ficticios; ninguna conexión de escritura a Dallas Fresh.
2. **Primer ciclo verificable:** proveedor invitado → RFQ → propuesta privada → comparación → aprobación → PO → proveedor libera → recepción con diferencias. Validar manualmente con un caso como compra de Tomate Roma desde Texas para Dallas Fresh.
3. **Relaciones y Marketplace:** verificación, perfiles, chat contextual, ofertas con audiencias y Push autorizado.
4. **Inteligencia asistida:** recomendación de compras, comparación de costo puesto en destino, seguimiento de precisión y sugerencias de excedente sin ejecución automática.
5. **Logística:** capacidad publicada, coincidencias, consolidación, cotizaciones privadas, seguimiento y POD. Luego corredores piloto Texas–Oklahoma–Kansas–Iowa/Midwest; expandir según densidad de participantes.
6. **Internacionalización:** múltiples idiomas y moneda, rutas de varios tramos y operación México–EE. UU. después de validar requisitos reales.

## Situación actual de los proyectos

El usuario proporcionó dos paquetes acumulados separados de Dallas Fresh App y su Connector, y confirmó que ya están en fase de pruebas. Ninguno se modifica en este proyecto. En la conversación anterior se solicitaron además controles de órdenes aprobadas, reporte de ventas, alertas de clientes recurrentes y opciones de contraseña. Esos requisitos pertenecen a Dallas Fresh App; no se implementan como parte de la Red B2B. La presente Red B2B se desarrolla de manera independiente y solo se unirá a la app de ventas después de validar los flujos y acordar un contrato de integración.

## Decisiones de implementación aún abiertas

Nombre comercial de la Red B2B; infraestructura y repositorio definitivos; forma de identidad compartida o separada con Dallas Fresh; taxonomía de productos; criterios y documentos de verificación; política de retención de chat/documentos; reglas detalladas de precio y visibilidad; interfaz inicial e idiomas prioritarios; alcance de integraciones. Se pueden tomar decisiones reversibles para el prototipo y registrar cada supuesto, sin bloquear el desarrollo independiente.

Fuentes: https://chatgpt.com/share/6ab2c539-ce4c-83ea-879f-1613d3f30640 y https://chatgpt.com/share/6ab2d01c-b658-83ea-8800-f7472814ca38
