"""CRUD Programări."""
from datetime import datetime

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

import db
from auth import login_required, role_required
from routes.util import gol_la_null, nr_pagini, paginare

bp = Blueprint("programari", __name__, url_prefix="/programari")

STATUSURI = ("programat", "anulat", "finalizat")


@bp.route("/")
@login_required
def lista():
    rol = g.user["rol"]
    f = {
        "status": request.args.get("status", ""),
        "medic": request.args.get("medic", ""),
        "de_la": request.args.get("de_la", ""),
        "pana_la": request.args.get("pana_la", ""),
        "q": request.args.get("q", "").strip(),
    }
    # fiecare rol vede doar ce îi aparține
    if rol == "medic":
        f["medic"] = str(g.user["id_medic"])
    pacient = g.user["id_pacient"] if rol == "pacient" else None
    pagina, limit, offset = paginare()
    rows = db.query(
        """SELECT pr.id_programare, pr.data_ora, pr.durata_minute, pr.status, pr.motiv,
                  p.id_pacient, p.nume || ' ' || p.prenume AS pacient,
                  m.id_medic, m.nume || ' ' || m.prenume AS medic, s.denumire AS specializare,
                  c.id_consultatie,
                  count(*) OVER () AS total
           FROM programari pr
           JOIN pacienti p USING (id_pacient)
           JOIN medici m USING (id_medic)
           JOIN specializari s USING (id_specializare)
           LEFT JOIN consultatii c USING (id_programare)
           WHERE (%(status)s::status_programare IS NULL OR pr.status = %(status)s)
             AND (%(medic)s::int IS NULL OR pr.id_medic = %(medic)s)
             AND (%(pacient)s::int IS NULL OR pr.id_pacient = %(pacient)s)
             AND (%(de_la)s::date IS NULL OR pr.data_ora >= %(de_la)s)
             AND (%(pana_la)s::date IS NULL OR pr.data_ora < %(pana_la)s::date + 1)
             AND (%(q)s = '' OR p.nume ILIKE %(like)s OR p.prenume ILIKE %(like)s)
           ORDER BY pr.data_ora DESC
           LIMIT %(limit)s OFFSET %(offset)s""",
        {**{k: (v or None) for k, v in f.items() if k != "q"}, "q": f["q"],
         "pacient": pacient, "like": f"%{f['q']}%", "limit": limit, "offset": offset})
    total = rows[0]["total"] if rows else 0
    medici = db.query("SELECT id_medic, nume || ' ' || prenume AS nume FROM medici ORDER BY nume")
    return render_template("programari_list.html", rows=rows, f=f, medici=medici,
                           statusuri=STATUSURI, pagina=pagina, pagini=nr_pagini(total), total=total)


def _optiuni():
    medici = db.query(
        """SELECT m.id_medic, m.nume || ' ' || m.prenume || ' — ' || s.denumire AS eticheta
           FROM medici m JOIN specializari s USING (id_specializare)
           ORDER BY s.denumire, m.nume""")
    pacienti = []
    if g.user["rol"] in ("admin", "receptioner"):
        pacienti = db.query(
            """SELECT id_pacient, nume || ' ' || prenume || ' (' || cnp || ')' AS eticheta
               FROM pacienti ORDER BY nume, prenume""")
    return medici, pacienti


def _din_formular(form):
    item = {
        "id_medic": form.get("id_medic") or None,
        "data_ora": gol_la_null(form.get("data_ora")),
        "durata_minute": form.get("durata_minute") or 30,
        "motiv": gol_la_null(form.get("motiv")),
    }
    if g.user["rol"] == "pacient":
        item["id_pacient"] = g.user["id_pacient"]
    else:
        item["id_pacient"] = form.get("id_pacient") or None
    return item


def _in_viitor(data_ora):
    try:
        return datetime.fromisoformat(data_ora) > datetime.now()
    except (TypeError, ValueError):
        return False


@bp.route("/nou", methods=["GET", "POST"])
@role_required("admin", "receptioner", "pacient")
def creare():
    item = {"durata_minute": 30, "id_pacient": request.args.get("pacient")}
    if request.method == "POST":
        item = _din_formular(request.form)
        if not _in_viitor(item["data_ora"]):
            flash("Programarea trebuie făcută pentru o dată din viitor.", "danger")
        else:
            try:
                db.execute(
                    """INSERT INTO programari (id_pacient, id_medic, data_ora, durata_minute, motiv)
                       VALUES (%(id_pacient)s, %(id_medic)s, %(data_ora)s, %(durata_minute)s,
                               %(motiv)s)""", item)
                flash("Programarea a fost creată.", "success")
                return redirect(url_for("programari.lista"))
            except db.DBError as err:
                flash(db.mesaj_eroare(err), "danger")
    medici, pacienti = _optiuni()
    return render_template("programare_form.html", item=item, medici=medici, pacienti=pacienti,
                           statusuri=STATUSURI, nou=True)


@bp.route("/<int:id>/editare", methods=["GET", "POST"])
@role_required("admin", "receptioner")
def editare(id):
    item = db.query_one("SELECT * FROM programari WHERE id_programare = %s", (id,))
    if not item:
        abort(404)
    if request.method == "POST":
        item = {**_din_formular(request.form), "id_programare": id,
                "status": request.form.get("status", "programat")}
        try:
            db.execute(
                """UPDATE programari SET id_pacient = %(id_pacient)s, id_medic = %(id_medic)s,
                          data_ora = %(data_ora)s, durata_minute = %(durata_minute)s,
                          motiv = %(motiv)s, status = %(status)s
                   WHERE id_programare = %(id_programare)s""", item)
            flash("Programarea a fost actualizată.", "success")
            return redirect(url_for("programari.lista"))
        except db.DBError as err:
            flash(db.mesaj_eroare(err), "danger")
    medici, pacienti = _optiuni()
    return render_template("programare_form.html", item=item, medici=medici, pacienti=pacienti,
                           statusuri=STATUSURI, nou=False)


@bp.route("/<int:id>/status", methods=["POST"])
@login_required
def schimba_status(id):
    """Medicul finalizează/anulează, pacientul își poate anula programarea viitoare."""
    nou = request.form.get("status")
    pr = db.query_one("SELECT *, data_ora > NOW() AS viitoare FROM programari WHERE id_programare = %s",
                      (id,))
    if not pr or nou not in STATUSURI:
        abort(404)
    rol = g.user["rol"]
    permis = (
        rol in ("admin", "receptioner")
        or (rol == "medic" and pr["id_medic"] == g.user["id_medic"] and nou in ("finalizat", "anulat"))
        or (rol == "pacient" and pr["id_pacient"] == g.user["id_pacient"] and nou == "anulat"
            and pr["status"] == "programat" and pr["viitoare"])
    )
    if not permis:
        abort(403)
    db.execute("UPDATE programari SET status = %s WHERE id_programare = %s", (nou, id))
    flash(f"Programarea este acum „{nou}”.", "success")
    if nou == "finalizat" and rol in ("medic", "admin"):
        return redirect(url_for("consultatii.creare", programare=id))
    return redirect(request.referrer or url_for("programari.lista"))


@bp.route("/<int:id>/stergere", methods=["POST"])
@role_required("admin", "receptioner")
def stergere(id):
    db.execute("DELETE FROM programari WHERE id_programare = %s", (id,))
    flash("Programarea a fost ștearsă.", "success")
    return redirect(url_for("programari.lista"))
