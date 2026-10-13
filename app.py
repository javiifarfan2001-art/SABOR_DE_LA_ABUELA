#!/usr/bin/env python3
"""
=============================================================================
RESTAURANTE EL SABOR DE LA ABUELA (LORCA, ESPAÑA)
SERVIDOR EN LA NUBE 24/7 (3 PÁGINAS COMPLETAS: CLIENTE, ADMIN Y RESEÑAS)
=============================================================================
"""

import http.server
import socketserver
import os
import sys
import json
import datetime
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get("PORT", 8080))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

LIVE_DB_FILE = os.path.join(DIRECTORY, "pedidos_en_vivo.json")
HISTORY_DB_FILE = os.path.join(DIRECTORY, "registros_historicos.json")
MENU_DB_FILE = os.path.join(DIRECTORY, "menu_platos.json")
REVIEWS_DB_FILE = os.path.join(DIRECTORY, "resenas_clientes.json")

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] Error guardando {path}: {e}")

live_tables = load_json(LIVE_DB_FILE, {})
history_records = load_json(HISTORY_DB_FILE, [])
menu_dishes = load_json(MENU_DB_FILE, [])
reviews_data = load_json(REVIEWS_DB_FILE, [])

class ThreePageServerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # PÁGINA 1: CARTA DEL CLIENTE (MESA)
        if path in ['/', '/index.html', '/cliente', '/menu']:
            p = os.path.join(DIRECTORY, "cliente.html")
            if not os.path.exists(p): p = os.path.join(DIRECTORY, "menu_restaurante_ecuatoriano.html")
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers()
            with open(p, 'rb') as f: self.wfile.write(f.read())
            return

        # PÁGINA 2: PANEL DEL ADMINISTRADOR (COMANDAS, PRECIOS, AGREGAR PLATOS, VENTAS)
        if path in ['/admin', '/cocina', '/jefes', '/panel']:
            p = os.path.join(DIRECTORY, "admin.html")
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers()
            with open(p, 'rb') as f: self.wfile.write(f.read())
            return

        # PÁGINA 3: RESEÑAS Y OPINIONES DE CLIENTES
        if path in ['/resenas', '/opiniones', '/valoraciones']:
            p = os.path.join(DIRECTORY, "resenas.html")
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers()
            with open(p, 'rb') as f: self.wfile.write(f.read())
            return

        # APIS
        if path == '/api/pedidos_en_vivo':
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(live_tables).encode('utf-8'))
            return

        if path == '/api/registros_diarios':
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(history_records).encode('utf-8'))
            return

        if path == '/api/menu':
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(menu_dishes).encode('utf-8'))
            return

        if path == '/api/resenas':
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(reviews_data).encode('utf-8'))
            return

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else '{}'
        data = json.loads(body) if body else {}

        # Pedido nuevo
        if parsed.path == '/api/pedido':
            m = data.get('mesa', 'Mesa 12')
            if m not in live_tables: live_tables[m] = {"items": [], "cuenta_solicitada": False, "ultimo_pedido": data.get('timestamp', '')}
            live_tables[m]["ultimo_pedido"] = data.get('timestamp', '')
            for it in data.get('items', []):
                live_tables[m]["items"].append({**it, "despachado": False})
            save_json(LIVE_DB_FILE, live_tables)
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"status": "ok"}')
            return

        # Pedir cuenta
        if parsed.path == '/api/pedir_cuenta':
            m = data.get('mesa', 'Mesa 12')
            if m in live_tables: live_tables[m]["cuenta_solicitada"] = True; save_json(LIVE_DB_FILE, live_tables)
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"status": "ok"}')
            return

        # Marcar servido
        if parsed.path == '/api/despachar':
            m, idx = data.get('mesa'), data.get('index')
            if m in live_tables and 0 <= idx < len(live_tables[m]["items"]):
                live_tables[m]["items"][idx]["despachado"] = not live_tables[m]["items"][idx].get("despachado", False)
                save_json(LIVE_DB_FILE, live_tables)
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"status": "ok"}')
            return

        # Cerrar mesa
        if parsed.path == '/api/cerrar_mesa':
            m = data.get('mesa')
            if m in live_tables:
                rec = live_tables[m]
                tot = sum(i["price"] * i["qty"] for i in rec.get("items", []))
                now = datetime.datetime.now()
                history_records.insert(0, { "mesa": m, "fecha": now.strftime("%Y-%m-%d"), "hora": now.strftime("%H:%M"), "total": round(tot, 2), "items": rec.get("items", []) })
                save_json(HISTORY_DB_FILE, history_records)
                del live_tables[m]
                save_json(LIVE_DB_FILE, live_tables)
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"status": "ok"}')
            return

        # Actualizar menú
        if parsed.path == '/api/menu':
            global menu_dishes
            menu_dishes = data
            save_json(MENU_DB_FILE, menu_dishes)
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"status": "ok"}')
            return

        # Guardar reseña
        if parsed.path == '/api/resenas':
            reviews_data.insert(0, data)
            save_json(REVIEWS_DB_FILE, reviews_data)
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"status": "ok"}')
            return

        self.send_response(404); self.end_headers()

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), ThreePageServerHandler) as httpd:
        print(f"[✓] Servidor 3 Páginas activo en puerto {PORT}")
        httpd.serve_forever()
