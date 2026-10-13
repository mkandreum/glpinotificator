# -*- coding: utf-8 -*-
"""Prueba automatica (solo lectura) del programa. NO modifica nada en GLPI.
Uso:  python test_diagnostico.py"""
import io
import os
import sys
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avisa_glpi as A


def linea(t):
    print("\n=== %s ===" % t)


try:
    linea("CREDENCIALES")
    creds = A.cargar_credenciales()
    assert creds, "No hay credenciales guardadas"
    print("login:", creds.get("login"), "| app_token:",
          "si" if creds.get("app_token") else "NO")

    cfg = A.load_config()
    cli = A.GLPIClient(cfg["glpi_url"], creds.get("app_token", ""))
    cli.login(user_token=creds.get("user_token", ""),
              login=creds.get("login", ""), password=creds.get("password", ""))
    print("login OK, session_token:", "si" if cli.session_token else "NO")

    linea("MI USUARIO")
    uid = cli.my_id()
    print("users_id:", uid, "| nombre:", cli.user_name(uid))

    linea("BUSQUEDA TICKETS NUEVOS (estado=1)")
    ids = cli.tickets_nuevos_ids()
    print("total NUEVO encontrados:", len(ids))
    print("ids:", ids[:10])
    print("max_ticket_id:", cli.max_ticket_id())

    if ids:
        linea("DETALLE DEL MAS RECIENTE #%d" % ids[0])
        det = cli.ticket(ids[0])
        print("name     :", det.get("name"))
        print("status   :", det.get("status"))
        print("priority :", det.get("priority"))
        print("date     :", det.get("date"))
        contenido = A.strip_html(det.get("content", ""))
        print("contenido:", (contenido[:160] + "...") if len(contenido) > 160 else contenido)
        actores = cli.actores(ids[0])
        print("actores  :", [(a.get("type"), a.get("users_id")) for a in actores])
        sol = ""
        for a in actores:
            if str(a.get("type")) == "1" and a.get("users_id"):
                sol = cli.user_name(a["users_id"])
                break
        print("solicitante:", sol or "(desconocido)")
        asignados = [a for a in actores if str(a.get("type")) == "2"]
        print("ya asignado:", bool(asignados))
    else:
        print("(no hay tickets en estado Nuevo ahora mismo; no es un error)")

    cli.kill()
    print("\n>>> DIAGNOSTICO DE LECTURA: TODO OK")
except Exception as e:
    print("\n>>> FALLO:", e)
    traceback.print_exc()
