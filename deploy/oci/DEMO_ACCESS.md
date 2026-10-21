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

La configuración anterior con el cuadro del navegador se validó el **18 de octubre de 2026**:

- Acceso sin credenciales o con clave incorrecta: 401. Con credenciales: 200.
- HTTPS válido en ambos nombres y redirección de `www` conservando ruta y consulta.
- WebSocket autenticado: 101. Carga sintética: 204. Generación exitosa y respuesta
  de persistencia OCI `completado`. Descarga del JSON: 200 con credenciales y
  401 sin ellas.
- IP directa por HTTP: 404; puertos 8000/8501 sin conexión pública. Techretai: 200.
- Suite local: 272 pruebas aprobadas y 1 integración OCI omitida. La prueba
  funcional real anterior se ejecutó por separado. La página nueva requiere
  repetir estas comprobaciones después de desplegarla.

El release de configuración es
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
