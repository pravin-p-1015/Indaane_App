import ipaddress
import json
import os
import socket
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .database import LOCK, audit, connect, init_db
from .backups import automatic_backups
from .services import StoreService
from .security import AuthenticationService
from .ui import page

APPLICATION = StoreService(connect, LOCK)
AUTHENTICATION = AuthenticationService(connect, LOCK, audit)
class Handler(BaseHTTPRequestHandler):
    server_version="IndaaneLocal/1.0"
    def log_message(self,*args): pass
    def send_json(self,obj,status=200):
        b=json.dumps(obj,default=str).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(b)
    def body(self):
        n=int(self.headers.get("Content-Length",0))
        if n>5_000_000: raise ValueError("Request is too large.")
        return json.loads(self.rfile.read(n) or b"{}")
    def user(self):
        cookies={part.strip().split("=",1)[0]:part.strip().split("=",1)[1] for part in self.headers.get("Cookie","").split(";") if "=" in part}
        return AUTHENTICATION.session(cookies.get("session",""))
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/login":
            body='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in · Indaane</title><style>body{font:16px Segoe UI,Arial;background:#f3f6f9;color:#18324d}.login{background:white;border:1px solid #dce3eb;border-radius:12px;max-width:380px;margin:12vh auto;padding:28px}input{box-sizing:border-box;width:100%;padding:12px;border:1px solid #cbd6e0;border-radius:6px;margin:7px 0 15px}button{background:#245f96;color:white;border:0;border-radius:6px;padding:12px 16px;width:100%;font-weight:bold}#e{color:#a83d3d}</style></head><body><div class="login"><h1>Indaane Store</h1><p>Sign in to the local store application</p><form id="f"><label>Username<input name="username" autocomplete="username" required autofocus></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><button>Sign in</button></form><p id="e"></p></div><script>f.onsubmit=async e=>{e.preventDefault();let r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(f)))});if(r.ok)location.href='/';else document.getElementById('e').textContent=(await r.json()).error}</script></body></html>'''
            b=body.encode(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
        if path=="/":
            u=self.user()
            if not u: self.send_response(302); self.send_header("Location","/login"); self.end_headers(); return
            b=page(u).encode(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.send_header("X-Content-Type-Options","nosniff"); self.send_header("Content-Security-Policy","default-src 'self' 'unsafe-inline'; connect-src 'self'"); self.end_headers(); self.wfile.write(b); return
        self.send_error(404)
    def do_POST(self):
        try:
            if self.path=="/login":
                d=self.body()
                token=AUTHENTICATION.login(d.get("username",""),d.get("password",""))
                b=json.dumps({"ok":True}).encode(); self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Set-Cookie",f"session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
            if self.path=="/logout":
                token=next((part.strip().split("=",1)[1] for part in self.headers.get("Cookie","").split(";") if part.strip().startswith("session=")),""); AUTHENTICATION.logout(token); self.send_response(204); self.send_header("Set-Cookie","session=; Max-Age=0; HttpOnly; Path=/"); self.end_headers(); return
            if self.path.startswith("/api/"):
                user=self.user()
                if not user: self.send_json({"error":"Please sign in."},401); return
                action=self.path.removeprefix("/api/"); d=self.body()
                result=APPLICATION.execute(action,d,user)
                if isinstance(result,dict) and "pdf_data" in result:
                    b=result["pdf_data"]; self.send_response(200); self.send_header("Content-Type","application/pdf"); self.send_header("Content-Disposition",f"attachment; filename=\"{result['filename']}\""); self.send_header("Content-Length",str(len(b))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(b); return
                if isinstance(result,dict) and "csv" in result:
                    b=result["csv"].encode("utf-8-sig"); self.send_response(200); self.send_header("Content-Type","text/csv; charset=utf-8"); self.send_header("Content-Disposition",f"attachment; filename={result['filename']}"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
                self.send_json(result); return
            self.send_error(404)
        except PermissionError as e: self.send_json({"error":str(e)},403)
        except (ValueError,KeyError,sqlite3.IntegrityError) as e: self.send_json({"error":str(e)},400)
        except Exception as e: self.send_json({"error":"The request could not be completed. Check the entered data."},500)

def run():
    init_db()
    threading.Thread(target=automatic_backups,daemon=True).start()
    host=os.environ.get("INDAANE_HOST","0.0.0.0"); port=int(os.environ.get("INDAANE_PORT","8765"))
    print(f"Indaane is ready on port {port}. On this computer: http://127.0.0.1:{port}")
    if host in ("0.0.0.0","::"):
        try:
            addresses=sorted({x[4][0] for x in socket.getaddrinfo(socket.gethostname(),None) if x[0] in (socket.AF_INET,socket.AF_INET6) and not x[4][0].startswith("127.") and x[4][0]!="::1"})
            for address in addresses: print(f"LAN access: http://{address}:{port}")
        except OSError: print("Find this computer's local IP address to connect from other devices.")
    print("First sign-in: admin / admin123 — change this password in Settings immediately.")
    class LocalThreadingHTTPServer(ThreadingHTTPServer):
        daemon_threads=True
        request_queue_size=64
        def verify_request(self,request,client_address):
            try:
                peer=ipaddress.ip_address(client_address[0])
                return peer.is_private or peer.is_loopback or peer.is_link_local
            except ValueError:
                return False
    LocalThreadingHTTPServer((host,port),Handler).serve_forever()
