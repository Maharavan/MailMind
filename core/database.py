from psycopg2 import sql
import psycopg2
from config.settings import settings


class Database:
    def __init__(self):
        self.table_name = "email_agent_table"
        self.db_config = {
            "dbname": settings.DB_NAME,
            "user": settings.DB_USER,
            "password": settings.DB_PASSWORD,
            "host": settings.DB_HOST,
        }
        self._create_table()
    
    def _connect(self):
        return psycopg2.connect(**self.db_config)

    def _create_table(self):
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    msgid VARCHAR(255) PRIMARY KEY,
                    status VARCHAR(20) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def try_claim_email(self, msgid: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {self.table_name} (msgid, status)
                VALUES (%s, 'PROCESSING')
                ON CONFLICT (msgid) DO NOTHING
            """, (msgid,))
            conn.commit()
            return cur.rowcount == 1
        finally:
            conn.close()

    def mark_success(self, msgid: str):
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"""
                UPDATE {self.table_name}
                SET status='SUCCESS', updated_at=NOW()
                WHERE msgid=%s
            """, (msgid,))
            conn.commit()
        finally:
            conn.close()
    
    def mark_review_needed(self, msgid: str):
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"""
                UPDATE {self.table_name}
                SET status='REVIEW', updated_at=NOW()
                WHERE msgid=%s
            """, (msgid,))
            conn.commit()
        finally:
            conn.close()

    def mark_failed(self, msgid: str):
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(f"""
                UPDATE {self.table_name}
                SET status='FAILED', updated_at=NOW()
                WHERE msgid=%s
            """, (msgid,))
            conn.commit()
        finally:
            conn.close()

    def mark_ignored(self, msgid:str):
        """Mark the email as ignored in the database"""
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                query = sql.SQL("""
                    UPDATE {}
                    SET status='IGNORED', updated_at=NOW()
                    WHERE msgid=%s
                """).format(sql.Identifier(self.table_name))
                cur.execute(query, (msgid,))
            conn.commit()
        finally:
            conn.close()
