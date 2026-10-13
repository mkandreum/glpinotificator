#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AVISOS GLPI EN TIEMPO REAL
==========================
Vigila tu GLPI cada X segundos y, cuando entra una peticion NUEVA sin asignar,
muestra un POPUP moderno por encima de todo con el numero, TITULO y CONTENIDO,
y botones ASIGNARMELO / NO LA TRATO.

- El login se pide UNA SOLA VEZ y se guarda cifrado con Windows (DPAPI).
- Sin dependencias: solo libreria estandar de Python.

Uso:  doble clic en iniciar_avisos.bat
"""

from __future__ import annotations

import base64
import ctypes
import datetime
import html
import json
import os
import queue
import re
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

BASE_DIR = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATE_FILE = os.path.join(BASE_DIR, "estado.json")
CREDS_FILE = os.path.join(BASE_DIR, "credenciales.dat")
DEBUG_LOG = os.path.join(BASE_DIR, "debug.log")


def _ruta_icono():
    for base in (getattr(sys, "_MEIPASS", None), BASE_DIR):
        if base:
            p = os.path.join(base, "icon.ico")
            if os.path.exists(p):
                return p
    return None

DEFAULT_URL = ""

STATUS_NUEVO = 1              # GLPI: 1 = Nuevo
STATUS_EN_CURSO_ASIGNADO = 2  # GLPI: 2 = En curso (asignado)
ACTOR_ASIGNADO = 2            # Ticket_User.type: 1=solicitante, 2=asignado, 3=observador

# -- paleta brutalista minimalista -------------------------------------------
C_PAPER   = "#f2efe9"  # fondo (papel)
C_INK     = "#0d0d0d"  # tinta / bordes / texto fuerte
C_WHITE   = "#ffffff"
C_MUTED   = "#6b6b6b"  # texto secundario
C_ACCENT  = "#ff4d00"  # naranja electrico (accion principal)
C_ACCENT2 = "#1a1aff"  # azul (acento secundario)
C_GREEN   = "#0f9d58"
C_RED     = "#e01b24"
C_ORANGE  = "#e08e00"
C_DANGER_BG = "#ffe3e0"

# fuentes
F_HEAD = "Segoe UI"
F_MONO = "Consolas"


# --------------------------------------------------------------------------
# Cifrado DPAPI de Windows (solo tu usuario de Windows puede leer el fichero)
# --------------------------------------------------------------------------

def _crypt32():
    return ctypes.windll.crypt32


class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32),
                ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _to_blob(data: bytes):
    buf = ctypes.create_string_buffer(data)
    blob = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    return blob, buf  # buf debe seguir vivo durante la llamada


def dpapi_protect(plain: bytes) -> bytes:
    """Cifra bytes con DPAPI (ambito usuario actual)."""
    in_blob, in_buf = _to_blob(plain)
    out_blob = _BLOB()
    ok = _crypt32().CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None, 0x01,
        ctypes.byref(out_blob))
    if not ok:
        raise OSError("DPAPI: no se pudo cifrar")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def dpapi_unprotect(cipher: bytes) -> bytes:
    """Descifra bytes cifrados con dpapi_protect por el mismo usuario."""
    in_blob, in_buf = _to_blob(cipher)
    out_blob = _BLOB()
    ok = _crypt32().CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0x01,
        ctypes.byref(out_blob))
    if not ok:
        raise OSError("DPAPI: no se pudo descifrar")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def guardar_credenciales(secretos: dict):
    raw = json.dumps(secretos).encode("utf-8")
    blob = base64.b64encode(dpapi_protect(raw)).decode("ascii")
    with open(CREDS_FILE, "w", encoding="ascii") as f:
        f.write(blob)
    try:
        import stat
        os.chmod(CREDS_FILE, stat.S_IREAD | stat.S_IWRITE)
    except OSError:
        pass


def cargar_credenciales():
    try:
        with open(CREDS_FILE, "r", encoding="ascii") as f:
            blob = base64.b64decode(f.read().strip())
        return json.loads(dpapi_unprotect(blob).decode("utf-8"))
    except (OSError, ValueError):
        return None


def borrar_credenciales():
    try:
        os.remove(CREDS_FILE)
    except OSError:
        pass


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def log(msg):
    linea = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    print(linea, flush=True)
    try:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass


def strip_html(raw):
    if not raw:
        return "(sin descripcion)"
    text = html.unescape(raw)
    if any(tag in text for tag in ("&lt;", "&#60;", "&gt;", "&#62;")):
        text = html.unescape(text)
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</\s*(div|tr|h\d)\s*>", "\n", text)
    text = re.sub(r"(?i)<\s*li\s*>", "• ", text)
    text = re.sub(r"(?i)</\s*li\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text if text else "(sin descripcion)"


def load_config():
    cfg = {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        pass
    cfg.setdefault("glpi_url", DEFAULT_URL)
    cfg.setdefault("poll_seconds", 30)
    cfg.setdefault("solo_sin_asignar", True)
    cfg.setdefault("categoria_contiene", [])
    cfg.setdefault("sonido", True)
    cfg.setdefault("sonido_volumen", 0.5)
    cfg.setdefault("monitor_popup", "principal")
    cfg.setdefault("popup_offset_cm", 0)
    cfg.setdefault("max_popups", 5)
    return cfg


def save_config(cfg):
    public = {k: v for k, v in cfg.items() if not k.startswith("_")}
    for secreto in ("user_token", "login", "password", "app_token_guardado"):
        public.pop(secreto, None)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(public, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"last_seen_id": 0, "avisos_hoy": 0, "dia": ""}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass


# --------------------------------------------------------------------------
# Cliente API REST de GLPI (solo libreria estandar)
# --------------------------------------------------------------------------

def _decode_body(raw_bytes: bytes) -> str:
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("latin1", errors="replace")


class GLPIError(Exception):
    pass


class GLPIClient:
    def __init__(self, base_url, app_token=""):
        self.base = base_url.rstrip("/")
        self.api = self.base + "/apirest.php"
        self.app_token = (app_token or "").strip()
        self.session_token = None
        self.users_id = None
        self._user_token = ""
        self._login = ""
        self._password = ""

    def _request(self, method, path, params=None, payload=None, retry=True):
        url = self.api + path
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        data = None
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.app_token:
            headers["App-Token"] = self.app_token
        if self.session_token:
            headers["Session-Token"] = self.session_token
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = _decode_body(resp.read())
                return json.loads(body) if body.strip() else {}
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(_decode_body(e.read()))
            except ValueError:
                err = str(e)
            if e.code in (400, 401) and retry and "initSession" not in path:
                log("Sesion caducada, renovando...")
                self.login(self._user_token, self._login, self._password)
                return self._request(method, path, params, payload, retry=False)
            log("API %s %s -> HTTP %s: %s" % (method, path, e.code, str(err)[:300]))
            raise GLPIError("HTTP %s en %s: %s" % (e.code, path, err))

    def login(self, user_token="", login="", password=""):
        # Guarda credenciales para poder renovar la sesion solo
        if user_token or login or password:
            self._user_token = user_token
            self._login = login
            self._password = password
        headers = {"Content-Type": "application/json"}
        if self.app_token:
            headers["App-Token"] = self.app_token
        if user_token:
            headers["Authorization"] = "user_token %s" % user_token
        else:
            cred = ("%s:%s" % (login, password)).encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(cred).decode()
        req = urllib.request.Request(self.api + "/initSession?get_full_session=true",
                                         headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = json.loads(_decode_body(resp.read()))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise GLPIError("Usuario o contrasena incorrectos (o token no valido).")
            if e.code == 400:
                raise GLPIError("Falta el App-Token o la API no esta activada en GLPI.")
            raise GLPIError("No se pudo conectar (HTTP %s). Revisa la URL." % e.code)
        except urllib.error.URLError:
            raise GLPIError("No se pudo conectar con %s. Revisa la URL y tu red." % self.base)
        self.session_token = body.get("session_token")
        if not self.session_token:
            raise GLPIError("GLPI no devolvio sesion: %s" % body)
        # Mi id de usuario: viene como users_id (GLPI nuevos) o glpiID en la
        # sesion completa (GLPI antiguos, sin endpoint getMyInfo).
        uid = body.get("users_id")
        if not uid and isinstance(body.get("session"), dict):
            uid = body["session"].get("glpiID")
        try:
            self.users_id = int(uid) if uid else None
        except (TypeError, ValueError):
            self.users_id = None
        return True

    def kill(self):
        try:
            if self.session_token:
                self._request("GET", "/killSession", retry=False)
        except GLPIError:
            pass
        self.session_token = None

    def my_id(self):
        if self.users_id:
            return self.users_id
        # Reserva: sesion completa (funciona aunque no exista getMyInfo)
        full = self._request("GET", "/getFullSession/")
        sess = full.get("session", full) if isinstance(full, dict) else {}
        try:
            self.users_id = int(sess.get("glpiID"))
        except (TypeError, ValueError):
            raise GLPIError("No se pudo obtener mi id de usuario.")
        return self.users_id

    def user_name(self, users_id):
        try:
            u = self._request("GET", "/User/%d" % int(users_id))
            nombre = ("%s %s" % (u.get("firstname", ""), u.get("realname", ""))).strip()
            return nombre or u.get("name", "")
        except GLPIError:
            return ""

    def tickets_nuevos_ids(self, limit=50):
        params = [
            ("criteria[0][link]", "AND"),
            ("criteria[0][field]", "12"),          # 12 = Estado
            ("criteria[0][searchtype]", "equals"),
            ("criteria[0][value]", str(STATUS_NUEVO)),
            ("forcedisplay[0]", "2"),              # 2 = ID
            ("sort", "2"),
            ("order", "DESC"),
            ("range", "0-%d" % (limit - 1)),
        ]
        res = self._request("GET", "/search/Ticket/", params=params)
        ids = []
        for row in res.get("data", []) or []:
            try:
                ids.append(int(row.get("2", row.get("id", row.get("ID")))))
            except (TypeError, ValueError):
                continue
        return ids

    def max_ticket_id(self):
        params = [("sort", "2"), ("order", "DESC"), ("range", "0-0"),
                  ("forcedisplay[0]", "2")]
        res = self._request("GET", "/search/Ticket/", params=params)
        data = res.get("data", []) or []
        if not data:
            return 0
        try:
            return int(data[0].get("2", 0))
        except (TypeError, ValueError):
            return 0

    def ticket(self, ticket_id):
        return self._request("GET", "/Ticket/%d" % ticket_id,
                             params=[("expand_dropdowns", "true")])

    def actores(self, ticket_id):
        res = self._request("GET", "/Ticket/%d/Ticket_User/" % ticket_id,
                            params=[("range", "0-100")])
        return res if isinstance(res, list) else []

    def asignarme(self, ticket_id, users_id):
        self._request("POST", "/Ticket/%d/Ticket_User/" % ticket_id,
                      payload={"input": {"tickets_id": ticket_id,
                                         "users_id": users_id,
                                         "type": ACTOR_ASIGNADO}})
        self._request("PUT", "/Ticket/%d" % ticket_id,
                      payload={"input": {"id": ticket_id,
                                        "status": STATUS_EN_CURSO_ASIGNADO}})


# --------------------------------------------------------------------------
# Hilo vigilante
# --------------------------------------------------------------------------

def vigilante(app):
    cfg = app.cfg
    poll = max(10, int(cfg.get("poll_seconds", 30)))
    while not app.salir:
        try:
            creds = app.creds or {}
            app_token = creds.get("app_token", "") or cfg.get("app_token", "")
            client = GLPIClient(cfg["glpi_url"], app_token)
            client.login(user_token=creds.get("user_token", ""),
                         login=creds.get("login", ""), password=creds.get("password", ""))
            app.my_id = client.my_id()
            app.error_conexion = None
            log("Conectado a GLPI como usuario id=%s" % app.my_id)

            state = load_state()
            if state.get("last_seen_id", 0) == 0:
                state["last_seen_id"] = client.max_ticket_id()
                save_state(state)
                log("Posicion inicial: ticket #%d (solo se avisara de lo nuevo)" % state["last_seen_id"])

            while not app.salir:
                if app.pausado:
                    time.sleep(1)
                    continue
                try:
                    app.ultima_revision = time.time()
                    ids = client.tickets_nuevos_ids()
                    nuevos = [i for i in ids if i > state.get("last_seen_id", 0)]
                    if nuevos:
                        state["last_seen_id"] = max(nuevos + [state["last_seen_id"]])
                        save_state(state)
                    for tid in sorted(nuevos):
                        try:
                            det = client.ticket(tid)
                            if int(det.get("status", 0)) != STATUS_NUEVO:
                                continue
                            want = [c.lower() for c in cfg.get("categoria_contiene", []) if c]
                            if want:
                                cat = det.get("itilcategories_id", "")
                                if isinstance(cat, dict):
                                    cat = "%s %s" % (cat.get("name", ""), cat.get("completename", ""))
                                if not any(w in str(cat).lower() for w in want):
                                    continue
                            actores = client.actores(tid)
                            if cfg.get("solo_sin_asignar", True) and any(
                                    str(a.get("type")) == str(ACTOR_ASIGNADO) for a in actores):
                                continue
                            solicitante = ""
                            for a in actores:
                                if str(a.get("type")) == "1" and a.get("users_id"):
                                    solicitante = client.user_name(a["users_id"])
                                    break
                            app.avisos.put({
                                "id": tid,
                                "titulo": html.unescape(det.get("name", "(sin titulo)")),
                                "contenido": strip_html(det.get("content", "")),
                                "fecha": det.get("date", ""),
                                "solicitante": html.unescape(solicitante),
                                "prioridad": det.get("priority", ""),
                            })
                            log("Nueva peticion #%d: %s" % (tid, det.get("name", "")))
                        except GLPIError as e:
                            log("No se pudo leer el ticket #%d: %s" % (tid, e))
                except GLPIError as e:
                    log("Error consultando GLPI: %s (reintento en %ds)" % (e, poll))
                except Exception:
                    log("Error inesperado:\n" + traceback.format_exc())
                for _ in range(poll):
                    if app.salir or app.pausado:
                        break
                    time.sleep(1)
            client.kill()
            return
        except GLPIError as e:
            app.error_conexion = str(e)
            log("Vigilante sin conexion: %s. Reintento en 30 s." % e)
        except Exception:
            app.error_conexion = "Error inesperado (mira debug.log)"
            log("Error inesperado en vigilante:\n" + traceback.format_exc())
        for _ in range(30):
            if app.salir:
                return
            time.sleep(1)


# --------------------------------------------------------------------------
# Interfaz (tkinter)
# --------------------------------------------------------------------------

try:
    import tkinter as tk
    from tkinter import scrolledtext
    import winsound
    TK = True
except ImportError:
    TK = False


# -- sonido sutil (tono suave generado en memoria, sin ficheros) -------------
_SONIDO_CACHE = {}


def _generar_tono(notas, sr=44100, vol=0.22):
    """notas: lista de (freq_hz, dur_ms). Crea un WAV 16-bit mono suave."""
    import wave as _wave
    import io as _io
    import math as _math
    import struct as _struct
    frames = bytearray()
    for freq, dur_ms in notas:
        n = int(sr * dur_ms / 1000.0)
        for i in range(n):
            t = i / sr
            ataque = min(1.0, i / max(1, sr * 0.004))
            caida = _math.exp(-6.0 * t)
            v = _math.sin(2 * _math.pi * freq * t) * ataque * caida * vol
            frames += _struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767))
    buf = _io.BytesIO()
    w = _wave.open(buf, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(bytes(frames))
    w.close()
    return buf.getvalue()


def _ruta_tono():
    return os.path.join(BASE_DIR, "tono.wav")


def reproducir_sonido_sutil(volumen=0.5):
    """Reproduce un tono de aviso suave. Se genera una vez a WAV y se
    reproduce desde fichero (mas fiable que en memoria)."""
    if not TK:
        return
    try:
        clave = round(float(volumen), 2)
        ruta = _ruta_tono()
        if _SONIDO_CACHE.get("vol") != clave or not os.path.exists(ruta):
            # campanita discreta: do6 -> mi6, con cola suave
            data = _generar_tono([(1046, 130), (1318, 260)], vol=clave)
            with open(ruta, "wb") as f:
                f.write(data)
            _SONIDO_CACHE["vol"] = clave
        winsound.PlaySound(ruta, winsound.SND_FILENAME | winsound.SND_ASYNC)
        log("Sonido de aviso reproducido.")
    except Exception as e:
        log("Aviso: no se pudo reproducir el sonido (%s). Uso pitido del sistema." % e)
        try:
            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass


# -- tema de la barra de titulo (Windows 11) ---------------------------------
def _colorref(hex_rgb):
    """#RRGGBB -> COLORREF (0x00BBGGRR)."""
    h = hex_rgb.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def aplicar_tema_barra(win):
    """Tine la barra de titulo nativa (cerrar/minimizar/maximizar) con los
    colores del tema. Solo Windows 11; en otros no hace nada."""
    try:
        win.update_idletasks()
    except tk.TclError:
        return
    try:
        dwm = ctypes.windll.dwmapi
        user32 = ctypes.windll.user32
    except (AttributeError, OSError):
        return

    def _set(hwnd, attr, value):
        if not hwnd:
            return
        v = ctypes.c_int(value)
        try:
            dwm.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), attr,
                                      ctypes.byref(v), ctypes.sizeof(v))
        except Exception:
            pass

    try:
        hwnd = win.winfo_id()
        padre = user32.GetParent(hwnd) or hwnd
    except tk.TclError:
        return

    DWMWA_BORDER_COLOR = 34
    DWMWA_CAPTION_COLOR = 35
    DWMWA_TEXT_COLOR = 36
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20

    for h in (hwnd, padre):
        _set(h, DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
        _set(h, DWMWA_CAPTION_COLOR, _colorref(C_INK))
        _set(h, DWMWA_TEXT_COLOR, _colorref(C_PAPER))
        _set(h, DWMWA_BORDER_COLOR, _colorref(C_ACCENT))


# -- icono de la aplicacion --------------------------------------------------
def poner_icono(win):
    p = _ruta_icono()
    if p:
        try:
            win.iconbitmap(p)
        except tk.TclError:
            pass


# -- geometria de pantalla / multi-monitor -----------------------------------
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", _RECT),
                ("rcWork", _RECT), ("dwFlags", ctypes.c_ulong)]


def _enum_monitores():
    """Lista de areas de trabajo (l,t,r,b,es_principal) de cada monitor,
    ordenadas de izquierda a derecha."""
    infos = []
    try:
        u = ctypes.windll.user32
        u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MONITORINFO)]
        u.GetMonitorInfoW.restype = ctypes.c_int
        CMP = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                 ctypes.POINTER(_RECT), ctypes.c_ssize_t)

        def _cb(hmon, hdc, lprc, lparam):
            mi = _MONITORINFO()
            mi.cbSize = ctypes.sizeof(_MONITORINFO)
            if u.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcWork
                infos.append((r.left, r.top, r.right, r.bottom,
                              bool(mi.dwFlags & 1)))  # 1 = MONITORINFOF_PRIMARY
            return 1

        u.EnumDisplayMonitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                          CMP, ctypes.c_ssize_t]
        u.EnumDisplayMonitors(None, None, CMP(_cb), 0)
    except Exception:
        pass
    infos.sort(key=lambda m: m[0])
    return infos


def _area_monitor_principal():
    """Obtiene el area de trabajo del monitor principal segun Windows API."""
    try:
        u = ctypes.windll.user32
        # Monitor 0 con MONITOR_DEFAULTTOPRIMARY = 1
        hmon = u.MonitorFromWindow(0, 1)
        if hmon:
            mi = _MONITORINFO()
            mi.cbSize = ctypes.sizeof(_MONITORINFO)
            u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MONITORINFO)]
            u.GetMonitorInfoW.restype = ctypes.c_int
            if u.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(mi)):
                r = mi.rcWork
                return (r.left, r.top, r.right, r.bottom)
    except Exception:
        pass
    try:
        from ctypes import wintypes
        rect = wintypes.RECT()
        # SPI_GETWORKAREA = 0x0030: area util del monitor principal
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        pass
    return None


def _area_monitor_raton():
    try:
        u = ctypes.windll.user32
        u.GetCursorPos.argtypes = [ctypes.POINTER(_POINT)]
        u.GetCursorPos.restype = ctypes.c_int
        u.MonitorFromPoint.argtypes = [_POINT, ctypes.c_ulong]
        u.MonitorFromPoint.restype = ctypes.c_void_p
        u.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MONITORINFO)]
        u.GetMonitorInfoW.restype = ctypes.c_int
        pt = _POINT()
        u.GetCursorPos(ctypes.byref(pt))
        hmon = u.MonitorFromPoint(pt, 2)  # MONITOR_DEFAULTTONEAREST
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(_MONITORINFO)
        if hmon and u.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(mi)):
            r = mi.rcWork
            return (r.left, r.top, r.right, r.bottom)
    except Exception:
        pass
    return None


def area_trabajo(win=None, modo="principal"):
    """Area util (sin barra de tareas) del monitor elegido.
    modo: 'principal' (por defecto), 'raton', o un numero 1..N (1=izquierda)."""
    modo = (str(modo).strip().lower() if modo is not None else "principal")

    # Si se pide el monitor principal de Windows, consultar directamente la API de Windows
    if modo in ("principal", "primario", "primary", "main", "default", ""):
        ap = _area_monitor_principal()
        if ap:
            return ap

    monitores = _enum_monitores()
    if monitores:
        if modo == "raton":
            m = _area_monitor_raton()
            if m:
                return m
        elif modo.isdigit():
            i = int(modo) - 1
            if 0 <= i < len(monitores):
                return monitores[i][:4]
        # 'principal' o fallback
        for m in monitores:
            if m[4]:
                return m[:4]
        return monitores[0][:4]

    if modo == "raton":
        m = _area_monitor_raton()
        if m:
            return m
    ap = _area_monitor_principal()
    if ap:
        return ap
    if win is not None:
        try:
            return (0, 0, win.winfo_screenwidth(), win.winfo_screenheight())
        except tk.TclError:
            pass
    return (0, 0, 1920, 1080)


def centrar_en_pantalla(win, W, H, modo="principal"):
    """Coloca win (WxH) centrada en el area util del monitor elegido."""
    l, t, r, b = area_trabajo(win, modo)
    an, al = r - l, b - t
    W = min(W, an - 20)
    H = min(H, al - 20)
    x = l + max(0, (an - W) // 2)
    y = t + max(0, (al - H) // 2)
    win.geometry("%dx%d+%d+%d" % (W, H, x, y))


def _fuente_entrada():
    return (F_MONO, 11)


def estilo_entrada(entry):
    entry.configure(bg=C_WHITE, fg=C_INK, insertbackground=C_INK,
                    relief="flat", bd=0, highlightthickness=2,
                    highlightbackground=C_INK, highlightcolor=C_ACCENT,
                    font=_fuente_entrada())


def boton_brutal(parent, texto, comando, primario=True, ancho=None, shadow=True):
    """Boton estilo brutalista: borde grueso de tinta + sombra dura solida."""
    if primario:
        bg, abg, fg = C_ACCENT, "#ff6a26", C_INK
    else:
        bg, abg, fg = C_WHITE, "#ffe9df", C_INK
    marco = tk.Frame(parent, bg=C_INK if shadow else bg)
    b = tk.Button(marco, text=texto, command=comando, bg=bg, fg=fg,
                  activebackground=abg, activeforeground=fg,
                  font=(F_HEAD, 10, "bold"), relief="flat", bd=0,
                  cursor="hand2", pady=8, padx=14,
                  highlightthickness=0)
    if ancho:
        b.configure(width=ancho)
    pad = (3, 3) if shadow else (0, 0)
    b.pack(padx=pad, pady=pad)
    b.bind("<Enter>", lambda e: b.configure(bg=abg))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    b._marco = marco
    return marco, b


def panel(parent, bg=C_WHITE, pad=0):
    """Panel con borde grueso de tinta (bloque brutalista)."""
    return tk.Frame(parent, bg=bg, highlightthickness=2,
                    highlightbackground=C_INK, highlightcolor=C_INK,
                    padx=pad, pady=pad)


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        self.creds = cargar_credenciales()
        self.avisos = queue.Queue()
        self.abiertos = []
        self.pausado = False
        self.salir = False
        self.my_id = None
        self.error_conexion = None
        self.ultima_revision = None
        self.loglineas = []
        self._hilo = None

    # -- arranque ----------------------------------------------------------
    def arrancar(self):
        if not self.creds:
            if not self.ventana_login():
                return False  # usuario cerro el login
        self.ventana_control()
        self._hilo = threading.Thread(target=vigilante, args=(self,), daemon=True)
        self._hilo.start()
        log("Vigilando %s cada %ss." % (self.cfg.get("glpi_url"),
                                        self.cfg.get("poll_seconds", 30)))
        self.root.after(500, self.procesar_cola)
        self.root.after(1000, self.refrescar_estado)
        return True

    # -- ventana de login (una sola vez) ------------------------------------
    def ventana_login(self):
        ok = {"valor": False}
        res = queue.Queue()

        win = tk.Toplevel(self.root)
        win.title("AVISOS GLPI")
        win.configure(bg=C_PAPER)
        win.resizable(True, True)
        win.minsize(430, 620)
        W, H = 430, 720
        centrar_en_pantalla(win, W, H, self.cfg.get("monitor_popup", "principal"))
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.attributes("-topmost", True)
        try:
            win.focus_force()
        except tk.TclError:
            pass

        cont = tk.Frame(win, bg=C_PAPER)
        cont.pack(fill="both", expand=True, padx=30, pady=26)

        # cabecera brutalista: bloque de tinta con titulo
        cab = tk.Frame(cont, bg=C_INK)
        cab.pack(fill="x")
        tk.Label(cab, text="AVISOS GLPI", bg=C_INK, fg=C_PAPER,
                 font=(F_HEAD, 20, "bold")).pack(anchor="w", padx=14, pady=(12, 0))
        tk.Label(cab, text="AVERIAS EN TIEMPO REAL", bg=C_INK, fg=C_ACCENT,
                 font=(F_MONO, 9, "bold")).pack(anchor="w", padx=14, pady=(0, 12))

        tk.Label(cont, text="INICIA SESION UNA SOLA VEZ. EL ACCESO SE GUARDA CIFRADO EN ESTE EQUIPO.",
                 bg=C_PAPER, fg=C_MUTED, font=(F_MONO, 8, "bold"),
                 wraplength=W - 80, justify="left").pack(anchor="w", pady=(12, 14))

        def campo(etiqueta, mostrar=None):
            tk.Label(cont, text=etiqueta.upper(), bg=C_PAPER, fg=C_INK,
                     font=(F_MONO, 9, "bold")).pack(anchor="w", pady=(0, 3))
            e = tk.Entry(cont, show=mostrar) if mostrar else tk.Entry(cont)
            estilo_entrada(e)
            e.pack(fill="x", ipady=7, pady=(0, 12))
            return e

        e_url = campo("Direccion de tu GLPI")
        e_url.insert(0, self.cfg.get("glpi_url") or DEFAULT_URL)
        e_user = campo("Usuario de GLPI")
        e_pass = campo("Contrasena", mostrar="\u25CF")
        e_app = campo("App-Token (obligatorio en tu servidor)")
        tk.Label(cont, text="PIDESELO AL ADMIN: CONFIGURACION > GENERAL > API > CLIENTES API.",
                 bg=C_PAPER, fg=C_MUTED, font=(F_MONO, 7, "bold"),
                 wraplength=W - 80, justify="left").pack(anchor="w")

        err = tk.Label(cont, text="", bg=C_PAPER, fg=C_RED,
                       font=(F_MONO, 9, "bold"), wraplength=W - 80, justify="left")
        err.pack(anchor="w", pady=(10, 4))

        def conectar():
            url = e_url.get().strip().rstrip("/")
            user = e_user.get().strip()
            pwd = e_pass.get()
            app_token = e_app.get().strip()
            if not url or not user or not pwd:
                err.configure(text="> Rellena direccion, usuario y contrasena.")
                return
            btn.configure(state="disabled", text="CONECTANDO...")
            err.configure(text="")
            log("Intento de login: url=%s usuario=%s app_token=%s" % (
                url, user, "si" if app_token else "NO (vacio)"))
            threading.Thread(target=self._probar_login,
                             args=(res, url, user, pwd, app_token),
                             daemon=True).start()

        marco, btn = boton_brutal(cont, "CONECTAR Y GUARDAR", conectar, primario=True)
        marco.pack(anchor="w", pady=(12, 0))
        for e in (e_url, e_user, e_pass, e_app):
            e.bind("<Return>", lambda ev: conectar())

        aplicar_tema_barra(win)
        poner_icono(win)
        win.grab_set()

        def revisar():
            if not win.winfo_exists():
                return
            try:
                tipo, dato = res.get_nowait()
            except queue.Empty:
                win.after(120, revisar)
                return
            if tipo == "err":
                try:
                    err.configure(text="> " + dato)
                    btn.configure(state="normal", text="CONECTAR Y GUARDAR")
                except tk.TclError:
                    return
                win.after(120, revisar)
            else:
                ok["valor"] = True
                win.destroy()

        win.after(120, revisar)
        self.root.wait_window(win)
        return ok["valor"]

    def _probar_login(self, res, url, user, pwd, app_token):
        try:
            cli = GLPIClient(url, app_token)
            cli.login(login=user, password=pwd)
            cli.my_id()
            cli.kill()
        except Exception as e:
            msg = str(e)
            log("Login fallido: %s" % msg)
            res.put(("err", msg))
            return
        guardar_credenciales({"login": user, "password": pwd,
                              "user_token": "", "app_token": app_token})
        self.creds = cargar_credenciales()
        self.cfg["glpi_url"] = url
        save_config(self.cfg)
        log("Login correcto. Credenciales cifradas y guardadas.")
        res.put(("ok", None))

    # -- ventana principal de control ---------------------------------------
    def ventana_control(self):
        r = self.root
        r.title("AVISOS GLPI")
        r.configure(bg=C_PAPER)
        r.resizable(True, True)
        r.minsize(400, 540)
        centrar_en_pantalla(r, 400, 600, self.cfg.get("monitor_popup", "principal"))
        r.protocol("WM_DELETE_WINDOW", self.cerrar)

        host = urllib.parse.urlparse(self.cfg.get("glpi_url", "")).netloc or self.cfg.get("glpi_url", "")

        # cabecera: bloque de tinta
        cab = tk.Frame(r, bg=C_INK)
        cab.pack(fill="x")
        tk.Label(cab, text="AVISOS GLPI", bg=C_INK, fg=C_PAPER,
                 font=(F_HEAD, 17, "bold")).pack(anchor="w", padx=16, pady=(12, 0))
        tk.Label(cab, text=host.upper(), bg=C_INK, fg=C_ACCENT,
                 font=(F_MONO, 8, "bold")).pack(anchor="w", padx=16, pady=(0, 12))

        # panel de estado
        est = panel(r, bg=C_WHITE)
        est.pack(fill="x", padx=16, pady=16)
        fila = tk.Frame(est, bg=C_WHITE)
        fila.pack(fill="x", padx=14, pady=(12, 6))
        self.dot = tk.Frame(fila, bg=C_ORANGE, width=14, height=14,
                            highlightthickness=2, highlightbackground=C_INK)
        self.dot.pack(side="left")
        self.dot.pack_propagate(False)
        self.lbl_estado = tk.Label(fila, text="CONECTANDO...", bg=C_WHITE, fg=C_INK,
                                   font=(F_HEAD, 12, "bold"))
        self.lbl_estado.pack(side="left", padx=(10, 0))

        self.lbl_revision = tk.Label(est, text="", bg=C_WHITE, fg=C_MUTED,
                                     font=(F_MONO, 8, "bold"))
        self.lbl_revision.pack(anchor="w", padx=14)
        self.lbl_avisos = tk.Label(est, text="", bg=C_WHITE, fg=C_MUTED,
                                   font=(F_MONO, 8, "bold"))
        self.lbl_avisos.pack(anchor="w", padx=14, pady=(0, 12))

        # botones de accion
        fbot = tk.Frame(r, bg=C_PAPER)
        fbot.pack(pady=(0, 16))
        m1, self.btn_pausa = boton_brutal(fbot, "PAUSAR", self.alternar_pausa, primario=False)
        m1.pack(side="left", padx=(0, 14))
        m2, b2 = boton_brutal(fbot, "PROBAR AVISO", self.aviso_prueba, primario=True)
        m2.pack(side="left")

        tk.Label(r, text="ACTIVIDAD", bg=C_PAPER, fg=C_INK,
                 font=(F_MONO, 9, "bold")).pack(anchor="w", padx=18, pady=(0, 4))
        marco_log = panel(r, bg=C_WHITE)
        marco_log.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self.txt_log = scrolledtext.ScrolledText(marco_log, wrap="word", bg=C_WHITE,
            fg=C_MUTED, font=(F_MONO, 8), relief="flat", height=9,
            highlightthickness=0, padx=8, pady=8)
        self.txt_log.pack(fill="both", expand=True, padx=2, pady=2)
        self.txt_log.configure(state="disabled")

        fpie = tk.Frame(r, bg=C_PAPER)
        fpie.pack(pady=(0, 14))
        l1 = tk.Label(fpie, text="[ CAMBIAR CUENTA ]", bg=C_PAPER, fg=C_ACCENT,
                      font=(F_MONO, 9, "bold"), cursor="hand2")
        l1.pack(side="left", padx=10)
        l1.bind("<Button-1>", lambda e: self.cambiar_cuenta())
        l2 = tk.Label(fpie, text="[ SALIR ]", bg=C_PAPER, fg=C_MUTED,
                      font=(F_MONO, 9, "bold"), cursor="hand2")
        l2.pack(side="left", padx=10)
        l2.bind("<Button-1>", lambda e: self.cerrar())

        aplicar_tema_barra(r)
        poner_icono(r)

    def alternar_pausa(self):
        self.pausado = not self.pausado
        self.btn_pausa.configure(text="REANUDAR" if self.pausado else "PAUSAR")
        self.anotar("Vigilancia %s." % ("en pausa" if self.pausado else "reanudada"))

    def aviso_prueba(self):
        self.avisos.put({
            "id": 0,
            "titulo": "Esto es un aviso de prueba",
            "contenido": ("Asi se vera el popup cuando entre una peticion real.\n\n"
                          "Aqui aparecera la descripcion de la averia tal como "
                          "la escriba el solicitante en GLPI."),
            "fecha": time.strftime("%d-%m-%Y %H:%M"),
            "solicitante": "Usuario de prueba",
            "prioridad": 3,
            "prueba": True,
        })

    def cambiar_cuenta(self):
        borrar_credenciales()
        self.anotar("Cuenta borrada. Vuelve a abrir el programa para iniciar sesion.")
        self.cerrar()

    def cerrar(self):
        self.salir = True
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def anotar(self, msg):
        linea = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
        log(msg)
        try:
            self.txt_log.configure(state="normal")
            self.txt_log.insert("end", linea + "\n")
            self.txt_log.see("end")
            self.txt_log.configure(state="disabled")
        except tk.TclError:
            pass

    def refrescar_estado(self):
        try:
            if self.pausado:
                self.dot.configure(bg=C_ORANGE)
                self.lbl_estado.configure(text="EN PAUSA", fg=C_INK)
            elif self.my_id:
                self.dot.configure(bg=C_GREEN)
                self.lbl_estado.configure(text="VIGILANDO GLPI", fg=C_INK)
            elif self.error_conexion:
                self.dot.configure(bg=C_RED)
                self.lbl_estado.configure(text="ERROR DE CONEXION", fg=C_RED)
            if self.ultima_revision:
                hace = int(time.time() - self.ultima_revision)
                self.lbl_revision.configure(text="ULTIMA REVISION: HACE %d S" % hace)
            st = load_state()
            hoy = datetime.date.today().isoformat()
            n = st.get("avisos_hoy", 0) if st.get("dia") == hoy else 0
            self.lbl_avisos.configure(text="AVISOS HOY: %d" % n)
            self.root.after(1000, self.refrescar_estado)
        except tk.TclError:
            pass

    # -- cola de popups ------------------------------------------------------
    def procesar_cola(self):
        try:
            while not self.avisos.empty():
                if len(self.abiertos) >= int(self.cfg.get("max_popups", 5)):
                    break
                aviso = self.avisos.get()
                self.mostrar_popup(aviso)
                if not aviso.get("prueba"):
                    st = load_state()
                    hoy = datetime.date.today().isoformat()
                    if st.get("dia") != hoy:
                        st["dia"] = hoy
                        st["avisos_hoy"] = 0
                    st["avisos_hoy"] = st.get("avisos_hoy", 0) + 1
                    save_state(st)
            self.root.after(500, self.procesar_cola)
        except tk.TclError:
            pass

    # -- popup brutalista -----------------------------------------------------
    def mostrar_popup(self, aviso):
        if self.cfg.get("sonido", True):
            reproducir_sonido_sutil(float(self.cfg.get("sonido_volumen", 0.5)))

        win = tk.Toplevel(self.root)
        win.withdraw()  # Ocultar mientras se construye para evitar parpadeos en posicion incorrecta
        win.title("PETICION GLPI #%d" % aviso["id"] if aviso["id"] else "AVISO DE PRUEBA")
        win.configure(bg=C_INK)
        win.attributes("-topmost", True)
        win.resizable(False, False)
        win.highlightthickness = 0

        l, t, rr, bb = area_trabajo(win, self.cfg.get("monitor_popup", "principal"))
        margen = 20
        ancho_monitor = max(200, rr - l)
        alto_monitor = max(200, bb - t)

        es_prueba = aviso.get("prueba")
        try:
            pr = int(aviso.get("prioridad") or 0)
        except (TypeError, ValueError):
            pr = 0
        if pr >= 5:
            pbg, ptxt = C_RED, C_WHITE
        elif pr == 4:
            pbg, ptxt = C_ORANGE, C_INK
        elif pr == 3:
            pbg, ptxt = C_ACCENT2, C_WHITE
        else:
            pbg, ptxt = C_MUTED, C_WHITE

        # -- cabecera (bloque de tinta) --
        cab = tk.Frame(win, bg=C_INK)
        cab.pack(fill="x")
        row = tk.Frame(cab, bg=C_INK)
        row.pack(fill="x", padx=14, pady=10)
        left = tk.Frame(row, bg=C_INK)
        left.pack(side="left", anchor="n")
        fila_num = tk.Frame(left, bg=C_INK)
        fila_num.pack(anchor="w")
        tk.Label(fila_num, text="#", bg=C_INK, fg=C_ACCENT,
                 font=(F_HEAD, 15, "bold")).pack(side="left")
        tk.Label(fila_num, text=str(aviso["id"]) if aviso["id"] else "---",
                 bg=C_INK, fg=C_PAPER, font=(F_HEAD, 19, "bold")).pack(side="left")
        tk.Label(left, text="PRUEBA" if es_prueba else "NUEVA PETICION",
                 bg=C_INK, fg=C_ACCENT, font=(F_MONO, 8, "bold")).pack(anchor="w")
        if not es_prueba:
            tk.Label(row, text="PRIORIDAD %d" % pr if pr else "SIN PRIORIDAD",
                     bg=pbg, fg=ptxt, font=(F_MONO, 8, "bold"),
                     padx=8, pady=4).pack(side="right", anchor="n")

        # -- cuerpo (papel) --
        cuerpo = tk.Frame(win, bg=C_PAPER)
        cuerpo.pack(fill="both", expand=True)

        tk.Label(cuerpo, text=aviso["titulo"], bg=C_PAPER, fg=C_INK,
                 font=(F_HEAD, 12, "bold"), wraplength=420,
                 justify="left").pack(anchor="w", padx=14, pady=(10, 3))

        meta = "ABIERTA %s" % (aviso["fecha"] or "?")
        if aviso.get("solicitante"):
            meta += "   ·   %s" % aviso["solicitante"].upper()
        tk.Label(cuerpo, text=meta, bg=C_PAPER, fg=C_MUTED,
                 font=(F_MONO, 8, "bold")).pack(anchor="w", padx=14)

        caja = panel(cuerpo, bg=C_WHITE)
        caja.pack(fill="both", expand=True, padx=14, pady=10)
        txt = scrolledtext.ScrolledText(caja, wrap="word", bg=C_WHITE, fg=C_INK,
                                        font=(F_MONO, 9), relief="flat",
                                        width=36, height=5, padx=9, pady=9,
                                        highlightthickness=0)
        txt.pack(fill="both", expand=True, padx=2, pady=2)
        txt.insert("1.0", aviso["contenido"][:3000])
        txt.configure(state="disabled")

        estado = tk.Label(cuerpo, text="", bg=C_PAPER, fg=C_GREEN,
                          font=(F_MONO, 8, "bold"))
        estado.pack(anchor="w", padx=14)

        def cerrar():
            if win in self.abiertos:
                self.abiertos.remove(win)
            try:
                win.destroy()
            except tk.TclError:
                pass

        def asignar():
            for b in btns:
                try:
                    b.configure(state="disabled")
                except tk.TclError:
                    pass
            estado.configure(text="> ASIGNANDO LA PETICION A TI...")
            threading.Thread(target=self._hacer_asignar,
                             args=(aviso["id"], estado, cerrar), daemon=True).start()

        pie = tk.Frame(win, bg=C_INK)
        pie.pack(fill="x")
        interior = tk.Frame(pie, bg=C_INK)
        interior.pack(fill="x", padx=14, pady=10)
        btns = []
        if es_prueba:
            m, b = boton_brutal(interior, "CERRAR", cerrar, primario=True)
            m.pack(side="right")
            btns.append(b)
        else:
            m1, b1 = boton_brutal(interior, "NO LA TRATO", cerrar, primario=False)
            m1.pack(side="right", padx=(12, 0))
            m2, b2 = boton_brutal(interior, "ASIGNARMELO", asignar, primario=True)
            m2.pack(side="right")
            btns.extend([b1, b2])
            link = tk.Label(interior, text="ABRIR EN GLPI \u2192", bg=C_INK, fg=C_ACCENT,
                            font=(F_MONO, 8, "bold"), cursor="hand2")
            link.pack(side="left")
            url = self.cfg["glpi_url"].rstrip("/") + "/front/ticket.form.php?id=%d" % aviso["id"]
            link.bind("<Button-1>", lambda e: webbrowser.open(url))

        # Medir dimensiones reales solicitadas por los widgets
        win.update_idletasks()
        req_w = win.winfo_reqwidth()
        req_h = win.winfo_reqheight()

        # Dimensiones finales: ni excesivas ni menores que los widgets, nunca desbordando el monitor
        W = max(460, min(req_w, ancho_monitor - 2 * margen))
        H = max(370, min(req_h, alto_monitor - 2 * margen))
        W = min(W, ancho_monitor - 2 * margen)
        H = min(H, alto_monitor - 2 * margen)

        n = len(self.abiertos)
        try:
            desplaz_x = int(round(float(self.cfg.get("popup_offset_cm", 0) or 0)
                                  * win.winfo_fpixels("1c")))
        except (TypeError, ValueError, tk.TclError):
            desplaz_x = int(round(float(self.cfg.get("popup_offset_cm", 0) or 0) * 37.8))

        fx = rr - W - margen - (n % 3) * 26 - desplaz_x
        fy = bb - H - margen - (n % 3) * 26

        # CLAMPING ESTRICTO: garantiza que el popup NUNCA invada monitores vecinos
        fx = max(l + margen, min(fx, rr - W - margen))
        fy = max(t + margen, min(fy, bb - H - margen))

        self.abiertos.append(win)
        win.protocol("WM_DELETE_WINDOW", cerrar)
        aplicar_tema_barra(win)
        poner_icono(win)
        self._animar_entrada(win, W, H, fx, fy, bb)

    def _animar_entrada(self, win, W, H, fx, fy, bb):
        """Entrada suave: deslizamiento vertical ascendente y fundido alfa.
        Se mantiene estrictamente dentro de la pantalla asignada."""
        dy = min(30, max(0, bb - H - fy))
        pasos = {"i": 0, "n": 14, "dy": dy}
        try:
            win.geometry("%dx%d+%d+%d" % (W, H, fx, fy + dy))
            win.attributes("-alpha", 0.0)
            win.deiconify()
        except tk.TclError:
            return

        def ease_out(k):
            return 1 - (1 - k) ** 3

        def paso():
            try:
                pasos["i"] += 1
                k = pasos["i"] / pasos["n"]
                e = ease_out(k)
                cur_y = int(fy + pasos["dy"] * (1 - e))
                win.geometry("%dx%d+%d+%d" % (W, H, fx, cur_y))
                win.attributes("-alpha", min(1.0, e * 1.25))
                if pasos["i"] < pasos["n"]:
                    win.after(14, paso)
                else:
                    win.geometry("%dx%d+%d+%d" % (W, H, fx, fy))
                    win.attributes("-alpha", 1.0)
            except tk.TclError:
                pass
        paso()

    def _hacer_asignar(self, ticket_id, estado_label, cerrar_cb):
        try:
            creds = self.creds or {}
            client = GLPIClient(self.cfg["glpi_url"], creds.get("app_token", ""))
            client.login(user_token=creds.get("user_token", ""),
                         login=creds.get("login", ""), password=creds.get("password", ""))
            my_id = self.my_id or client.my_id()
            client.asignarme(ticket_id, my_id)
            client.kill()
            self.anotar("Peticion #%d asignada a ti." % ticket_id)
            self.root.after(0, lambda: estado_label.configure(
                text="\u2713 ASIGNADA A TI. CERRANDO...", fg=C_GREEN))
            self.root.after(2000, cerrar_cb)
        except Exception as e:
            self.anotar("Fallo al asignar #%d: %s" % (ticket_id, e))
            self.root.after(0, lambda: estado_label.configure(
                text="\u2716 ERROR AL ASIGNAR: %s" % e, fg=C_RED))


# --------------------------------------------------------------------------

def main():
    if not TK:
        print("ERROR: tkinter no disponible.")
        return
    root = tk.Tk()
    root.withdraw()
    app = App(root)
    if not app.arrancar():
        try:
            root.destroy()
        except tk.TclError:
            pass
        return
    root.deiconify()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
