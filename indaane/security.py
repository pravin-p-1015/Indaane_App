import hashlib
import hmac
import secrets
import time

SESSIONS: dict[str, dict] = {}

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310000).hex(), salt


class AuthenticationService:
    """Owns credential checks and the lifetime of in-memory login sessions."""

    SESSION_SECONDS = 12 * 60 * 60

    def __init__(self, connection_factory, transaction_lock, audit_writer):
        self._connection_factory = connection_factory
        self._transaction_lock = transaction_lock
        self._audit = audit_writer

    def login(self, username, password):
        with self._transaction_lock, self._connection_factory() as db:
            account=db.execute("SELECT * FROM users WHERE username=? AND active=1",(username,)).fetchone()
            if not account: raise PermissionError("Incorrect username or password.")
            actual,_=password_hash(password,account["salt"])
            if not hmac.compare_digest(actual,account["password"]): raise PermissionError("Incorrect username or password.")
            link=db.execute("SELECT employee_id FROM user_employee_links WHERE user_id=?",(account["id"],)).fetchone()
            self._audit(db,account["username"],"login","user",account["id"])
            session={"id":account["id"],"username":account["username"],"role":account["role"],"employee_id":link[0] if link else None,"expires":time.time()+self.SESSION_SECONDS}
        token=secrets.token_urlsafe(32)
        SESSIONS[token]=session
        return token

    def session(self, token):
        session=SESSIONS.get(token)
        if session and session.get("expires",0)>time.time():
            session["expires"]=time.time()+self.SESSION_SECONDS
            return session
        if token: SESSIONS.pop(token,None)
        return None

    def logout(self, token):
        SESSIONS.pop(token,None)
