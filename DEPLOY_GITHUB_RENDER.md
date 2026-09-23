# Publicar Red B2B para pruebas

1. Descomprime el ZIP. En GitHub, crea un repositorio **privado** llamado `red-b2b` sin README.
2. En el repositorio, **Add file → Upload files**. Arrastra **el contenido** de la carpeta descomprimida, incluidas `templates`, `statics`, `docs`, `app.py`, `procurement.py`, `schema.sql`, `requirements.txt` y `render.yaml`. Comprueba que `render.yaml` esté en la raíz; confirma con **Commit changes**. No subas el ZIP como único archivo.
3. En Render, **New → Blueprint**. Conecta ese repositorio privado, selecciona la rama principal y `render.yaml`.
4. Render pedirá `B2B_DEMO_PASSWORD`: crea una contraseña larga y guárdala fuera de GitHub. Revisa el costo del servicio **Starter** y el **disco persistente de 1 GB** antes de elegir **Deploy Blueprint**.
5. Abre el enlace `.onrender.com`. La primera ventana pide usuario `demo` y esa contraseña. Luego crea empresas ficticias con correos diferentes para probar compras y proveedores.

Este despliegue crea un servicio y un disco separados. No conecta Dallas Fresh App ni su Connector. El disco guarda los datos de este piloto en SQLite. El acceso compartido sirve para pruebas con un grupo pequeño; no invites clientes reales ni cargues información sensible. La siguiente etapa para uso real requiere registro controlado, verificación de empresas y migración a PostgreSQL.

### Actualizar un repositorio ya conectado a Render

Carga los archivos modificados del ZIP **en la raíz del mismo repositorio** y confirma los cambios en la rama que Render observa. Si GitHub Upload files no reemplaza algún archivo existente, usa su botón de edición o Git para reemplazarlo conservando las rutas. Incluye las carpetas completas `templates` y `statics` y el nuevo `procurement.py`. Render reconstruirá el servicio al recibir el commit. No elimines el disco persistente ni cambies `B2B_DATABASE`: `schema.sql` crea las tablas nuevas en la base existente sin borrar las anteriores. Verifica `/compras` y `/compras/productos` tras el despliegue.

La lectura de productos y ventas también requiere actualizar **por separado** el Connector, con cambios sobre la versión correcta de su repositorio. Si el código actual en GitHub ya difiere de los ZIP de referencia de septiembre, compara y combina los cambios antes de reemplazar `app.py`; subir directamente un paquete antiguo podría revertir mejoras posteriores. Consulta `docs/ACTIVAR_CONECTOR_DE_LECTURA.md`. La primera conexión se limita a una empresa piloto; para varios clientes hace falta la arquitectura universal multiempresa.
