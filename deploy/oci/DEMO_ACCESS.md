# Acceso a la demo

La demo está disponible en [nuevamente.sachadev.me](https://nuevamente.sachadev.me),
con HTTPS y una página de acceso con usuario y contraseña. Se eligió este acceso para que el equipo y los
evaluadores puedan entrar desde distintas conexiones, sin una lista fija de IPs.

## Cómo entrar

La página de acceso pide las credenciales antes de mostrar la aplicación. El usuario de
la demo es `evaluador`; la contraseña se comparte por privado, nunca en el
repositorio ni en comentarios del PR.

`www.nuevamente.sachadev.me` redirige a la misma dirección. Si el navegador
conserva una sesión anterior, se puede cerrar en `/salir` o abrir una ventana privada.
La sesión dura hasta 12 horas y se invalida al cambiar la contraseña.

### Cerrar sesión desde la app

La app muestra el enlace **Cerrar sesión** en la barra lateral. Se configura con la
variable `LOGOUT_URL` del frontend: en el deploy apunta a `/salir` y, si queda vacía
(por ejemplo en local, sin el servicio de acceso), el enlace no se muestra. Al hacer
clic, el servicio de acceso borra la cookie de sesión y redirige a `/acceso`.

## Configuración

- Cloudflare: registro A `nuevamente` hacia la VM y CNAME `www.nuevamente` hacia
  `nuevamente.sachadev.me`, ambos en **Solo DNS**.
- Traefik: HTTP en 80 redirige a HTTPS en 443. El resolver `letsencrypt` emite
  certificados para ambos nombres mediante HTTP-01; requiere mantener el puerto
  80 accesible y el almacenamiento ACME persistente.
- El servicio de acceso lee un hash bcrypt de la contraseña y firma una cookie de
  sesión `Secure`, `HttpOnly` y limitada al host. Traefik verifica esa sesión con
  `ForwardAuth` antes de servir Streamlit.
- El hash y la clave de firma viven en la VM, fuera del repositorio. El frontend
  y el backend no reciben la contraseña ni la clave de firma.
- La verificación cubre toda la interfaz, incluidas cargas, descargas y WebSocket.
  Los puertos 8000 y 8501 no se publican.

Traefik se comparte con otras aplicaciones. No cambiar sus routers ni activar
redirecciones globales. Para preparar el entorno, seguir la
[guía de despliegue](README.md) y completar `.env` usando `.env.example`.

## Preparar el servicio de acceso

En la VM, copiar el hash actual sin mostrar ni volver a ingresar la contraseña.
El directorio nuevo solo será legible por root y el usuario 10003 del contenedor:

```bash
sudo install -d -m 0750 -o root -g 10003 /etc/docker-platform/apps/nuevamente/auth-secrets
sudo install -m 0640 -o root -g 10003 \
  /etc/docker-platform/apps/nuevamente/demo-auth/users.htpasswd \
  /etc/docker-platform/apps/nuevamente/auth-secrets/users.htpasswd
sudo sh -c 'umask 027; openssl rand -base64 48 > /etc/docker-platform/apps/nuevamente/auth-secrets/signing.key'
sudo chown root:10003 /etc/docker-platform/apps/nuevamente/auth-secrets/signing.key
sudo chmod 0640 /etc/docker-platform/apps/nuevamente/auth-secrets/signing.key
```

La clave de firma se genera una sola vez y se conserva entre releases. Crear la
imagen `nuevamente-auth` desde `deploy/oci/demo_auth`, indicar
`NUEVAMENTE_AUTH_IMAGE` en el entorno del release y arrancar el Compose. Primero
debe quedar saludable `demo_auth`; luego se actualiza el router de Streamlit. Si
falla el acceso, restaurar el Compose anterior y recrear solo `frontend`, sin
desactivar la autenticación ni cambiar la configuración global de Traefik.

## Cambiar la contraseña

El administrador puede actualizarla en la VM con `htpasswd` disponible
(`httpd-tools` en Oracle Linux):

```bash
sudo htpasswd -B /etc/docker-platform/apps/nuevamente/auth-secrets/users.htpasswd evaluador
sudo chown root:10003 /etc/docker-platform/apps/nuevamente/auth-secrets/users.htpasswd
sudo chmod 0640 /etc/docker-platform/apps/nuevamente/auth-secrets/users.htpasswd
sudo install -m 0600 -o root -g root \
  /etc/docker-platform/apps/nuevamente/auth-secrets/users.htpasswd \
  /etc/docker-platform/apps/nuevamente/demo-auth/users.htpasswd
```

El comando pide la contraseña sin incluirla en el historial. No usar `-c` sobre
el archivo existente: reemplazaría los demás usuarios. El servicio lee el hash
en cada solicitud, así que no necesita reinicio: las sesiones previas se
invalidan. La segunda copia conserva la opción de volver temporalmente al
acceso anterior. Verificar que la clave nueva funciona y la anterior no;
actualizar también la copia cifrada del administrador.

## Comprobaciones

Desde fuera de la VM:

```bash
# Debe redirigir a HTTPS sin pedir contraseña.
curl -I http://nuevamente.sachadev.me/
# Debe redirigir a /acceso sin ofrecer el cuadro de autenticación del navegador.
curl -I https://nuevamente.sachadev.me/
# La página de acceso debe responder 200.
curl -i https://nuevamente.sachadev.me/acceso
```

Probar en el navegador el rechazo de una clave incorrecta, el acceso con la
clave válida, la generación y la descarga. Después de visitar `/salir`, la
portada y la descarga deben volver a pedir inicio de sesión. No usar `curl -k`,
ya que omite la validación del certificado.

### Comprobación del release actual: 27 de octubre de 2026

El release activo es `18f2b415f7fa88ab0cc3c5a35e28b42f40bf28c7`, con imágenes
`develop-18f2b41` de backend, frontend y acceso. Los tres servicios quedaron
`healthy`, sin reinicios ni errores recientes de tipo traceback, al finalizar
la actualización.

- La portada HTTPS redirigió con HTTP 303 a `/acceso` y el login respondió HTTP 200.
- La ruta pública `/api/v1/health` también redirigió al acceso; no expuso la API.
- El backend respondió HTTP 200 desde el frontend y no publicó el puerto 8000;
  la conexión directa externa a ese puerto no se completó.
- La suite local aprobó 388 pruebas backend, 113 frontend y 5 del servicio de
  acceso: **506 aprobadas** y una integración OCI omitida. Una generación interna
  con Gemini y persistencia real en Object Storage se verificó por separado.

La evidencia y el objeto de prueba están en [la guía de despliegue](README.md#validaciones).
Estos controles HTTP no repitieron el inicio de sesión con credenciales, logout,
WebSocket, carga y descarga desde el navegador sobre este release. La prueba
pública del 28 de octubre, descrita más abajo, añadió carga, generación y descarga
con sesión autenticada; ese resultado no se infiere del HTTP 200 del login.

### Validación adicional de persistencia: 28 de octubre de 2026

La prueba de NM-27 con un archivo Markdown real en la API interna de la VM
confirmó ambos objetos en OCI, la integridad del original y la conservación de
`documento_id` y `objeto_origen_id` en el paquete generado y persistido. Los
detalles y nombres de objetos se registran en
[la guía de despliegue](README.md#validaciones).

Esta ejecución interna no atravesó el acceso público ni la interfaz del navegador;
la comprobación siguiente cubrió ese recorrido por separado.

### Prueba autenticada desde el navegador: 28 de octubre de 2026

Después de iniciar sesión, se cargó el archivo sintético
`nm27-validacion-20261028.md` por la URL pública, se generó un Resumen Ejecutivo
para Principiante y se descargó el JSON mediante la interfaz.

- La interfaz mostró el archivo y los parámetros aplicados, 6 ítems generados,
  anclaje del 100%, claridad Alta y confirmación de guardado en OCI.
- El JSON descargado coincide con el objeto persistido en el bucket.
- La lectura independiente de original y paquete devolvió HTTP 200; el original
  conserva sus 1571 bytes y el paquete mantiene correctamente el identificador
  del documento y el vínculo al objeto original.

La evidencia detallada y las claves de objetos están en
[la guía de despliegue](README.md#validaciones). La prueba completa NM-27 para
este archivo; no repitió el ciclo de logout, el rechazo de descargas sin sesión
ni una comprobación independiente del código HTTP del handshake WebSocket.

### Antecedente: acceso del 18 de octubre de 2026

La configuración anterior con el cuadro de autenticación del navegador se validó
el **18 de octubre de 2026**:

- Acceso sin credenciales o con clave incorrecta: 401. Con credenciales: 200.
- HTTPS válido en ambos nombres y redirección de `www` conservando ruta y consulta.
- WebSocket autenticado: 101. Carga sintética: 204. Generación exitosa y respuesta
  de persistencia OCI `completado`. Descarga del JSON: 200 con credenciales y
  401 sin ellas.
- IP directa por HTTP: 404; puertos 8000/8501 sin conexión pública. Techretai: 200.
- Suite local de esa fecha: 272 pruebas aprobadas y 1 integración OCI omitida.
  La prueba funcional real anterior se ejecutó por separado. Estos resultados
  corresponden al mecanismo anterior, no validan el formulario actual.

El release de configuración utilizado en esa validación fue
`/opt/apps/apps/nuevamente/releases/nm39-access-20261018`. Se conservaron las
imágenes de la aplicación. La prueba funcional usó el protocolo de Streamlit;
no cubre revisión visual ni documentos largos.

## Limpiar archivos de prueba

La limpieza la realiza Leandro o Miguel con acceso administrativo a OCI.
La aplicación no tiene permisos de borrado.

1. En Object Storage, confirmar el bucket `nuevamente-contenidos-educativos`.
2. Identificar los originales y JSON de prueba por nombre y fecha. Confirmar con
   su responsable cuáles se pueden eliminar y respaldar lo que deba conservarse.
3. Eliminar solo esos objetos desde la consola, sin seleccionar todo el bucket.
   Si hay versionado, revisar también las versiones y posibles retenciones.
4. Comprobar que se eliminaron los archivos previstos y se conservó el resto.

El borrado puede ser irreversible. Los archivos de la prueba funcional no se
eliminaron automáticamente. No cargar documentos privados ni credenciales en la demo.

## Costos

La protección reutiliza la VM y Traefik existentes, los certificados gratuitos
de Let's Encrypt y la zona DNS del dominio. El servicio de acceso usa recursos
de esa misma VM. No agrega recursos OCI ni servicios
de pago. La renovación del dominio corre por cuenta de su titular.

La consulta de costos del 17 de octubre de 2026 registró **0 USD** para el
período UTC del 10 al 16 de octubre. CPU, almacenamiento y tráfico siguen sujetos
a las cuotas compartidas de OCI; Gemini tiene sus propios límites. La contraseña
restringe quién entra, pero no limita cuánto consumen los usuarios autorizados.
