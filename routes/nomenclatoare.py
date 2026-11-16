"""CRUD pentru nomenclatoare: Specializări și Medicamente (le modifică doar adminul)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import db
from auth import role_required
from routes.util import gol_la_null

bp = Blueprint("nomenclatoare", __name__)


# ============================ SPECIALIZĂRI ============================
@bp.route("/specializari")
@role_required("admin", "receptioner")
def specializari_lista():
    rows = db.query(
        """SELECT s.id_specializare, s.denumire, count(m.id_medic) AS medici
           FROM specializari s LEFT JOIN medici m USING (id_specializare)
           GROUP BY s.id_specializare ORDER BY s.denumire""")
    return render_template("specializari_list.html", rows=rows)


@bp.route("/specializari/nou", methods=["GET", "POST"])
@bp.route("/specializari/<int:id>/editare", methods=["GET", "POST"])
@role_required("admin")
def specializari_form(id=None):
    item = {}
    if id is not None:
        item = db.query_one("SELECT * FROM specializari WHERE id_specializare = %s", (id,))
        if not item:
            abort(404)
    if request.method == "POST":
        denumire = gol_la_null(request.form.get("denumire"))
        item = {**item, "denumire": denumire}
        try:
            if id is None:
                db.execute("INSERT INTO specializari (denumire) VALUES (%s)", (denumire,))
            else:
                db.execute("UPDATE specializari SET denumire = %s WHERE id_specializare = %s",
                           (denumire, id))
            flash("Specializarea a fost salvată.", "success")
            return redirect(url_for("nomenclatoare.specializari_lista"))
        except db.DBError as err:
            flash(db.mesaj_eroare(err), "danger")
    return render_template("specializare_form.html", item=item, nou=id is None)


@bp.route("/specializari/<int:id>/stergere", methods=["POST"])
@role_required("admin")
def specializari_stergere(id):
    try:
        db.execute("DELETE FROM specializari WHERE id_specializare = %s", (id,))
        flash("Specializarea a fost ștearsă.", "success")
    except db.DBError as err:
        flash(db.mesaj_eroare(err), "danger")
    return redirect(url_for("nomenclatoare.specializari_lista"))


# ============================ MEDICAMENTE ============================
@bp.route("/medicamente")
@role_required("admin", "receptioner", "medic")
def medicamente_lista():
    q = request.args.get("q", "").strip()
    rows = db.query(
        """SELECT md.*, count(rm.id_reteta) AS prescrieri
           FROM medicamente md LEFT JOIN retete_medicamente rm USING (id_medicament)
           WHERE %(q)s = '' OR md.denumire ILIKE %(like)s OR md.substanta_activa ILIKE %(like)s
           GROUP BY md.id_medicament ORDER BY md.denumire""",
        {"q": q, "like": f"%{q}%"})
    return render_template("medicamente_list.html", rows=rows, q=q)


@bp.route("/medicamente/nou", methods=["GET", "POST"])
@bp.route("/medicamente/<int:id>/editare", methods=["GET", "POST"])
@role_required("admin")
def medicamente_form(id=None):
    item = {}
    if id is not None:
        item = db.query_one("SELECT * FROM medicamente WHERE id_medicament = %s", (id,))
        if not item:
            abort(404)
    if request.method == "POST":
        date = {c: gol_la_null(request.form.get(c))
                for c in ("denumire", "substanta_activa", "forma", "concentratie")}
        item = {**item, **date}
        try:
            if id is None:
                db.execute(
                    """INSERT INTO medicamente (denumire, substanta_activa, forma, concentratie)
                       VALUES (%(denumire)s, %(substanta_activa)s, %(forma)s, %(concentratie)s)""",
                    date)
            else:
                db.execute(
                    """UPDATE medicamente SET denumire = %(denumire)s,
                              substanta_activa = %(substanta_activa)s, forma = %(forma)s,
                              concentratie = %(concentratie)s
                       WHERE id_medicament = %(id)s""", {**date, "id": id})
            flash("Medicamentul a fost salvat.", "success")
            return redirect(url_for("nomenclatoare.medicamente_lista"))
        except db.DBError as err:
            flash(db.mesaj_eroare(err), "danger")
    return render_template("medicament_form.html", item=item, nou=id is None)


@bp.route("/medicamente/<int:id>/stergere", methods=["POST"])
@role_required("admin")
def medicamente_stergere(id):
    try:
        db.execute("DELETE FROM medicamente WHERE id_medicament = %s", (id,))
        flash("Medicamentul a fost șters.", "success")
    except db.DBError as err:
        flash(db.mesaj_eroare(err), "danger")
    return redirect(url_for("nomenclatoare.medicamente_lista"))
