import sqlite3
import threading
from datetime import datetime

from .config import BACKUPS
from .database import LOCK, connect
def create_backup(db, prefix="store"):
    BACKUPS.mkdir(exist_ok=True)
    target=BACKUPS/(prefix+"-"+datetime.now().strftime("%Y%m%d-%H%M%S-%f")+".db")
    dest=sqlite3.connect(target)
    try: db.backup(dest)
    finally: dest.close()
    return target

def automatic_backups():
    # Backups run only while the local application is running.
    while True:
        threading.Event().wait(24*60*60)
        try:
            from . import database
            with LOCK,connect() as db: create_backup(db,prefix="demo" if database.DEMO_MODE else "store")
        except Exception as exc:
            print("Automatic backup failed:",exc)

