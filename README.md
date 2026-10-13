# GLPI Notificator

**Avisos de GLPI en tiempo real para Windows.** Vigila tu GLPI cada X segundos
y, cuando entra una **petición nueva sin asignar**, muestra un popup por encima
de todo con el número, el título y el contenido, y dos botones:
**Asignármelo** y **No la trato**.

Sin dependencias externas: solo la librería estándar de Python (interfaz
tkinter). El login se pide **una sola vez** y se guarda **cifrado con Windows
(DPAPI)**: solo tu usuario de Windows puede leerlo.

> *About (EN): Real-time GLPI ticket notifications for Windows. Polls your GLPI
> REST API and shows a top-most popup for each new unassigned ticket, with
> one-click self-assign. Single login, credentials stored encrypted via Windows
> DPAPI. Pure standard-library Python (tkinter), no third-party packages.*

---

## Características

- Popup por encima de todas las ventanas con número, título, prioridad,
  solicitante y contenido de la petición.
- Botón **Asignármelo**: te pone como técnico y pasa la petición a
  *En curso (asignada)*.
- Botón **No la trato**: cierra el aviso sin tocar nada.
- Botón **Abrir en GLPI**: abre la petición en el navegador.
- Sonido discreto de aviso y animación de entrada (ambos configurables).
- Interfaz brutalista minimalista, con la barra de título a juego (Windows 11).
- Vigilancia en segundo plano con reconexión automática.

## Requisitos

- Windows 10/11.
- GLPI con la **API REST activada**.
- Para usar el código fuente: **Python 3.8+** (probado en 3.9). El `.exe` no
  requiere Python.

## Instalación

### Opción A — Automática (recomendada, plug and play)

1. Ve a la sección **[Releases](https://github.com/mkandreum/glpinotificator/releases)**
   y descarga `GLPI-Notificator.zip`.
2. Descomprime el ZIP en cualquier carpeta.
3. Doble clic en **`instalar.bat`**.

El instalador copia la app a `%LOCALAPPDATA%\Programs\GlpiNotificator`, crea los
accesos directos en el **Escritorio** y el **Menú Inicio**, te pregunta si quieres
que arranque solo al encender el PC y lanza la aplicación. Para desinstalar:
doble clic en `desinstalar.bat`.

> La app guarda `config.json` y `credenciales.dat` **junto al ejecutable**.

### Opción B — Desde el código fuente

1. Instala [Python 3.9+](https://www.python.org/downloads/).
2. Descarga este repositorio.
3. Doble clic en `iniciar_avisos.bat` (o `python avisa_glpi.py`).

## Uso

1. La **primera vez** te pedirá la dirección de tu GLPI, tu **usuario** y
   **contraseña**, y (si tu servidor lo exige) el **App-Token**.
2. Pulsa **Conectar y guardar**. No volverá a pedírtelo.
3. La ventana principal muestra el estado, la última revisión, los avisos del
   día y un registro de actividad. Botones: **Probar aviso**, **Pausar**,
   **Cambiar cuenta**.
4. Minimiza la ventana y sigue trabajando: los popups aparecerán solos.

> La primera vez **no** avisa de los tickets antiguos: solo de los que entren a
> partir de ese momento.

## Configuración (`config.json`)

El programa crea `config.json` junto al `.exe` (o al `.py`) tras el primer
login. Puedes editarlo con el Bloc de notas. Ver `config.example.json`:

| Clave               | Por defecto   | Descripción |
|---------------------|---------------|-------------|
| `glpi_url`          | *(vacío)*     | URL base de tu GLPI, p. ej. `https://glpi.miempresa.com` |
| `poll_seconds`      | `30`          | Cada cuántos segundos consulta GLPI (mínimo 10) |
| `solo_sin_asignar`  | `true`        | `true` = solo avisa de peticiones sin técnico asignado |
| `categoria_contiene`| `[]`          | Lista de textos; solo avisa si la categoría los contiene. `[]` = todas |
| `sonido`            | `true`        | Reproduce un tono al mostrar el popup |
| `sonido_volumen`    | `0.5`         | Volumen del tono, de `0.0` a `1.0` |
| `monitor_popup`     | `"principal"` | Monitor donde sale el popup: `"principal"`, `"raton"` o un número `"1"`, `"2"`, ... (1 = el más a la izquierda) |
| `popup_offset_cm`   | `0`           | Desplaza el popup hacia la **izquierda** N cm (acepta decimales; negativo = hacia la derecha) |
| `max_popups`        | `5`           | Máximo de popups apilados a la vez |

> Los secretos (usuario, contraseña, App-Token) **no** se guardan en
> `config.json`, sino cifrados en `credenciales.dat`.

## App-Token y API REST

El programa usa la **API REST oficial** de GLPI con tu usuario y contraseña.
Si tu servidor exige **App-Token obligatorio**, aparecerá el error
`ERROR_APP_TOKEN_PARAMETERS_MISSING`: pídele a tu administrador el App-Token
del cliente API (*Configuración > General > API*) y rellena el campo opcional
del login.

## Arranque automático al encender el PC

1. Pulsa `Win+R`, escribe `shell:startup` y pulsa Enter.
2. Copia ahí un **acceso directo** al `.exe` (o a `iniciar_avisos.bat`).

## Compilar el ejecutable

```bat
build_exe.bat
```

Genera `dist\GlpiNotificator\GlpiNotificator.exe` en **modo carpeta**
(`--onedir`), que **arranca al instante**. Requiere conexión a internet la
primera vez, para instalar PyInstaller.

Para generar el **ZIP de distribución** (con el instalador incluido):

```bat
crear_release.bat
```

Crea `dist\GLPI-Notificator.zip`, que es lo que se sube a un Release.

> **Publicación automática:** el flujo `.github/workflows/release.yml` compila y
> publica el ZIP solo, al subir una etiqueta `v*` (por ejemplo `git tag v1.0.0`
> y `git push --tags`).

> ¿Un solo archivo portable? Cambia `--onedir` por `--onefile` en el script.
> Aviso: el modo de un solo archivo **extrae todo a `%TEMP%` en cada arranque**,
> por lo que tarda bastante más en abrir (y el antivirus lo escanea cada vez).

## Privacidad y seguridad

- La contraseña se cifra con la **DPAPI de Windows** (`credenciales.dat`); sin
  tu sesión de Windows no se puede descifrar.
- La comunicación con GLPI usa HTTPS.
- El programa solo hace peticiones a tu GLPI. No envía nada a terceros.

## Problemas típicos

- **Usuario o contraseña incorrectos**: usa el mismo usuario que en el navegador.
- **Falta el App-Token / API no activada**: pide al administrador que active la
  API REST y/o te dé el App-Token.
- **No se pudo conectar**: revisa la URL y tu red/VPN.
- **Asignármelo da error**: tu usuario necesita permiso para actualizar tickets
  (perfil Técnico o similar).
- **El popup sale en el monitor equivocado**: cambia `monitor_popup` en
  `config.json` (`"principal"`, `"raton"`, `"1"`, `"2"`, ...).

## Licencia

MIT. Ver [LICENSE](LICENSE).
