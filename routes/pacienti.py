"""CRUD Pacienți."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

import db
from auth import login_required, role_required
from routes.util import gol_la_null, nr_pagini, paginare

bp = Blueprint("pacienti", __name__, url_prefix="/pacienti")

CAMPURI = ("nume", "prenume", "cnp", "data_nasterii", "sex", "telefon", "email", "adresa")


@bp.route("/")
@role_required("admin", "receptioner", "medic")
def lista():
    q = request.args.get("q", "").strip()
    pagina, limit, offset = paginare()
    # medicul vede doar pacienții care au avut/au programări la el
    id_medic = g.user["id_medic"] if g.user["rol"] == "medic" else None
    rows = db.query(
        """SELECT p.id_pacient, p.nume, p.prenume, p.cnp, p.data_nasterii, p.telefon, p.email,
                  date_part('year', age(p.data_nasterii))::int AS varsta,
                  count(*) OVER () AS total
           FROM pacienti p
           WHERE (%(q)s = '' OR p.nume ILIKE %(like)s OR p.prenume ILIKE %(like)s
                  OR p.cnp LIKE %(q)s || '%%')
             AND (%(id_medic)s::int IS NULL OR EXISTS (
                    SELECT 1 FROM programari pr
                    WHERE pr.id_pacient = p.id_pacient AND pr.id_medic = %(id_medic)s))
           ORDER BY p.nume, p.prenume
           LIMIT %(limit)s OFFSET %(offset)s""",
        {"q": q, "like": f"%{q}%", "id_medic": id_medic, "limit": limit, "offset": offset})
    total = rows[0]["total"] if rows else 0
    return render_template("pacienti_list.html", rows=rows, q=q, pagina=pagina,
                           pagini=nr_pagini(total), total=total)


def _poate_vedea(id_pacient):
    rol = g.user["rol"]
    if rol in ("admin", "receptioner"):
        return True
    if rol == "pacient":
        return g.user["id_pacient"] == id_pacient
    if rol == "medic":
        return db.query_one("SELECT 1 FROM programari WHERE id_pacient = %s AND id_medic = %s LIMIT 1",
                            (id_pacient, g.user["id_medic"])) is not None
    return False


@bp.route("/<int:id>")
@login_required
def detalii(id):
    if not _poate_vedea(id):
        abort(403)
    p = db.query_one(
        """SELECT p.*, date_part('year', age(p.data_nasterii))::int AS varsta, u.email AS cont
           FROM pacienti p LEFT JOIN utilizatori u USING (id_utilizator)
           WHERE p.id_pacient = %s""", (id,))
    if not p:
        abort(404)
    programari = db.query(
        """SELECT pr.id_programare, pr.data_ora, pr.status, pr.motiv,
                  m.nume || ' ' || m.prenume AS medic, s.denumire AS specializare,
                  c.id_consultatie, c.diagnostic
           FROM programari pr
           JOIN medici m USING (id_medic)
           JOIN specializari s USING (id_specializare)
           LEFT JOIN consultatii c USING (id_programare)
           WHERE pr.id_pacient = %s
           ORDER BY pr.data_ora DESC""", (id,))
    return render_template("pacient_detalii.html", p=p, programari=programari)


@bp.route("/profil")
@role_required("pacient")
def profil():
    return redirect(url_for("pacienti.detalii", id=g.user["id_pacient"]))


def _din_formular(form):
    return {c: gol_la_null(form.get(c)) for c in CAMPURI}


@bp.route("/nou", methods=["GET", "POST"])
@role_required("admin", "receptioner")
def creare():
    item = {}
    if request.method == "POST":
        item = _din_formular(request.form)
        try:
            row = db.execute(
                """INSERT INTO pacienti (nume, prenume, cnp, data_nasterii, sex, telefon, email, adresa)
                   VALUES (%(nume)s, %(prenume)s, %(cnp)s, %(data_nasterii)s, %(sex)s,
                           %(telefon)s, %(email)s, %(adresa)s)
                   RETURNING id_pacient""", item)
            flash("Pacientul a fost adăugat.", "success")
            return redirect(url_for("pacienti.detalii", id=row["id_pacient"]))
        except db.DBError as err:
            flash(db.mesaj_eroare(err), "danger")
    return render_template("pacient_form.html", item=item, nou=True)


@bp.route("/<int:id>/editare", methods=["GET", "POST"])
@role_required("admin", "receptioner")
def editare(id):
    item = db.query_one("SELECT * FROM pacienti WHERE id_pacient = %s", (id,))
    if not item:
        abort(404)
    if request.method == "POST":
        item = {**_din_formular(request.form), "id_pacient": id}
        try:
            db.execute(
                """UPDATE pacienti SET nume = %(nume)s, prenume = %(prenume)s, cnp = %(cnp)s,
                          data_nasterii = %(data_nasterii)s, sex = %(sex)s, telefon = %(telefon)s,
                          email = %(email)s, adresa = %(adresa)s
                   WHERE id_pacient = %(id_pacient)s""", item)
            flash("Datele pacientului au fost actualizate.", "success")
            return redirect(url_for("pacienti.detalii", id=id))
        except db.DBError as err:
            flash(db.mesaj_eroare(err), "danger")
    return render_template("pacient_form.html", item=item, nou=False)


@bp.route("/<int:id>/stergere", methods=["POST"])
@role_required("admin", "receptioner")
def stergere(id):
    # ON DELETE CASCADE: se șterg și programările, consultațiile și rețetele pacientului
    db.execute("DELETE FROM pacienti WHERE id_pacient = %s", (id,))
    flash("Pacientul și istoricul lui au fost șterse.", "success")
    return redirect(url_for("pacienti.lista"))
