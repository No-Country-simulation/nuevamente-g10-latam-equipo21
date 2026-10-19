# Acceso a la demo

La demo está disponible en [nuevamente.sachadev.me](https://nuevamente.sachadev.me),
con HTTPS y usuario y contraseña. Se eligió este acceso para que el equipo y los
evaluadores puedan entrar desde distintas conexiones, sin una lista fija de IPs.

## Cómo entrar

El navegador pide las credenciales antes de mostrar la aplicación. El usuario de
la demo es `evaluador`; la contraseña se comparte por privado, nunca en el
repositorio ni en comentarios del PR.

`www.nuevamente.sachadev.me` redirige a la misma dirección. Si el navegador
conserva una contraseña anterior, abrir una ventana privada.

## Configuración

- Cloudflare: registro A `nuevamente` hacia la VM y CNAME `www.nuevamente` hacia
  `nuevamente.sachadev.me`, ambos en **Solo DNS**.
- Traefik: HTTP en 80 redirige a HTTPS en 443. El resolver `letsencrypt` emite
  certificados para ambos nombres mediante HTTP-01; requiere mantener el puerto
  80 accesible y el almacenamiento ACME persistente.
- El archivo `/etc/docker-platform/apps/nuevamente/demo-auth/users.htpasswd`
  contiene los hashes bcrypt, con propietario root y permisos `0600`.
- Solo Traefik monta ese directorio en `/run/secrets/nuevamente-demo`, en modo
  lectura (`:ro,Z`). El frontend y el backend no reciben la contraseña.
- La autenticación cubre toda la interfaz, incluidas cargas, descargas y WebSocket.
  Los puertos 8000 y 8501 no se publican.

La VM y Traefik se comparten con Techretai. No cambiar sus routers ni activar
redirecciones globales. Para preparar el entorno, seguir la
[guía de despliegue](README.md) y completar `.env` usando `.env.example`.

## Cambiar la contraseña

El administrador puede actualizarla en la VM con `htpasswd` disponible
(`httpd-tools` en Oracle Linux):

```bash
sudo htpasswd -B /etc/docker-platform/apps/nuevamente/demo-auth/users.htpasswd evaluador
sudo chmod 600 /etc/docker-platform/apps/nuevamente/demo-auth/users.htpasswd
```

El comando pide la contraseña sin incluirla en el historial. No usar `-c` sobre
el archivo existente: reemplazaría los demás usuarios.

Desde el directorio del release, con su `.env` y las mismas imágenes:

```bash
sudo docker compose --env-file .env -f compose.backend.yml config --quiet
sudo docker compose --env-file .env -f compose.backend.yml stop frontend
sleep 5
sudo docker compose --env-file .env -f compose.backend.yml up -d --no-deps --pull never --force-recreate frontend
```

Esto interrumpe brevemente NuevaMente, cierra las sesiones abiertas y permite
recargar la autenticación sin reiniciar el proxy compartido. Verificar que la
clave nueva funciona y la anterior devuelve 401; actualizar también la copia
cifrada del administrador. Si falla, mantener el frontend detenido hasta
corregirlo, sin retirar la protección.

## Comprobaciones

Desde fuera de la VM:

```bash
# Debe redirigir a HTTPS sin pedir contraseña.
curl -I http://nuevamente.sachadev.me/
# Debe responder 401.
curl -I https://nuevamente.sachadev.me/
# Pide la contraseña; debe responder "ok".
curl --fail --user evaluador https://nuevamente.sachadev.me/_stcore/health
```

No usar `-k`, ya que omite la validación del certificado.

Validado el **18 de octubre de 2026**:

- Acceso sin credenciales o con clave incorrecta: 401. Con credenciales: 200.
- HTTPS válido en ambos nombres y redirección de `www` conservando ruta y consulta.
- WebSocket autenticado: 101. Carga sintética: 204. Generación exitosa y respuesta
  de persistencia OCI `completado`. Descarga del JSON: 200 con credenciales y
  401 sin ellas.
- IP directa por HTTP: 404; puertos 8000/8501 sin conexión pública. Techretai: 200.
- Suite local: 272 pruebas aprobadas y 1 integración OCI omitida. La prueba
  funcional real anterior se ejecutó por separado.

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
de Let's Encrypt y la zona DNS del dominio. No agrega recursos OCI ni servicios
de pago. La renovación del dominio corre por cuenta de su titular.

La consulta de costos del 17 de octubre de 2026 registró **0 USD** para el
período UTC del 10 al 16 de octubre. CPU, almacenamiento y tráfico siguen sujetos
a las cuotas compartidas de OCI; Gemini tiene sus propios límites. La contraseña
restringe quién entra, pero no limita cuánto consumen los usuarios autorizados.
