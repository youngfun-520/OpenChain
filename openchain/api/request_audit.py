"""Request audit logging for OpenChain API."""
import uuid
import os

async def log_audit(key_label: str, endpoint: str, method: str, status_code: int, client_ip: str, request_id: str):
    """Log an authenticated request to audit_logs table."""
    from openchain.db import Database

    try:
        db_path = os.environ.get("OPENCHAIN_DB_PATH", "~/.openchain/data/openchain.db")
        async with Database(db_path) as db:
            log_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO audit_logs
                   (log_id, key_label, endpoint, method, status_code, client_ip, request_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (log_id, key_label, endpoint, method, status_code, client_ip, request_id)
            )
            await db.commit()
    except Exception:
        # Audit logging should never break the request
        pass