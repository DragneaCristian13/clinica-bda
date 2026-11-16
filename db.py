"""
Acces la baza de date (PostgreSQL) — SQL scris direct, fără ORM.

Toate interogările din aplicație trec prin funcțiile de aici:
  query(sql, params)        -> listă de dicționare (SELECT)
  query_one(sql, params)    -> un dicționar sau None
  execute(sql, params)      -> INSERT/UPDATE/DELETE; întoarce primul rând dacă are RETURNING
  transaction([(sql, params), ...]) -> mai multe instrucțiuni într-o singură tranzacție

Parametrii se trimit separat (%s), niciodată prin concatenare de string-uri,
deci aplicația e protejată împotriva SQL injection.
"""
import os

from flask import g

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # permite importul modulului fără driver (ex. la teste)
    psycopg = None


class DBError(Exception):
    """Eroare de bază de date tradusă într-un mesaj ușor de afișat."""

    def __init__(self, message, constraint=None, code=None):
        super().__init__(message)
        self.constraint = constraint
        self.code = code


# Mesaje prietenoase pentru constrângerile din schemă
MESAJE_CONSTRANGERI = {
    "pacienti_cnp_key": "Există deja un pacient cu acest CNP.",
    "chk_pacient_cnp": "CNP-ul trebuie să aibă 13 cifre și să înceapă cu 1-8.",
    "chk_pacient_nastere": "Data nașterii nu este validă.",
    "chk_pacient_telefon": "Numărul de telefon nu este valid.",
    "medici_cod_parafa_key": "Există deja un medic cu acest cod de parafă.",
    "chk_medic_parafa": "Codul de parafă are exact 6 caractere (litere mari / cifre).",
    "chk_medic_telefon": "Numărul de telefon nu este valid.",
    "medici_email_key": "Există deja un medic cu acest email.",
    "utilizatori_email_key": "Există deja un cont cu acest email.",
    "chk_utilizator_email": "Adresa de email nu este validă.",
    "specializari_denumire_key": "Specializarea există deja.",
    "uq_medicament": "Medicamentul (denumire + formă + concentrație) există deja.",
    "uq_programare_medic_ora": "Medicul are deja o programare la această oră.",
    "chk_programare_durata": "Durata trebuie să fie între 10 și 180 de minute.",
    "consultatii_id_programare_key": "Programarea are deja o consultație.",
    "chk_reteta_valabilitate": "Valabilitatea trebuie să fie între 1 și 365 de zile.",
    "retete_medicamente_pkey": "Același medicament apare de două ori pe rețetă.",
    "chk_rm_durata": "Durata tratamentului trebuie să fie între 1 și 365 de zile.",
    "chk_rm_cantitate": "Cantitatea trebuie să fie mai mare decât 0.",
    "programari_id_medic_fkey": "Medicul are programări și nu poate fi șters.",
    "medici_id_specializare_fkey": "Specializarea este folosită de medici și nu poate fi ștearsă.",
    "retete_medicamente_id_medicament_fkey": "Medicamentul apare pe rețete și nu poate fi șters.",
    "utilizatori_id_rol_fkey": "Rolul este folosit de utilizatori.",
}


def mesaj_eroare(err: DBError) -> str:
    if err.constraint and err.constraint in MESAJE_CONSTRANGERI:
        return MESAJE_CONSTRANGERI[err.constraint]
    return f"Operația nu a putut fi efectuată: {err}"


# ---------------------------------------------------------------------------
# Conexiune: una per request, închisă automat la final
# ---------------------------------------------------------------------------
def get_conn():
    if "db" not in g:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("Lipsește DATABASE_URL (vezi fișierul .env).")
        g.db = psycopg.connect(url, row_factory=dict_row)
        with g.db.cursor() as cur:
            cur.execute("SET search_path TO clinica, public")
        g.db.commit()
    return g.db


def close_conn(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _wrap(exc):
    diag = getattr(exc, "diag", None)
    constraint = getattr(diag, "constraint_name", None) if diag else None
    code = getattr(exc, "sqlstate", None)
    primary = getattr(diag, "message_primary", None) if diag else None
    return DBError(primary or str(exc), constraint=constraint, code=code)


def query(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.commit()
        return rows
    except psycopg.Error as exc:
        conn.rollback()
        raise _wrap(exc) from exc


def query_one(sql, params=None):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone() if cur.description else None
        conn.commit()
        return row
    except psycopg.Error as exc:
        conn.rollback()
        raise _wrap(exc) from exc


def transaction(statements):
    """Rulează mai multe instrucțiuni atomic: ori toate reușesc, ori niciuna."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for sql, params in statements:
                cur.execute(sql, params)
        conn.commit()
    except psycopg.Error as exc:
        conn.rollback()
        raise _wrap(exc) from exc
