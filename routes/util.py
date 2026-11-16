"""Funcții ajutătoare comune paginilor."""
from flask import request

PE_PAGINA = 20


def paginare():
    """Întoarce (pagina, limit, offset) din ?page=N."""
    try:
        pagina = max(1, int(request.args.get("page", 1)))
    except ValueError:
        pagina = 1
    return pagina, PE_PAGINA, (pagina - 1) * PE_PAGINA


def nr_pagini(total):
    return max(1, -(-total // PE_PAGINA))


def gol_la_null(value):
    """Câmpurile goale din formular devin NULL în baza de date."""
    if value is None:
        return None
    value = value.strip()
    return value or None
