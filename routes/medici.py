"""CRUD Medici."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

import db
from auth import login_required, role_required
from routes.util import gol_la_null

bp = Blueprint("medici", __name__, url_prefix="/medici")


@bp.route("/")
@login_required
def lista():
    id_spec = request.args.get("specializare", "")
    rows = db.query(
        """SELECT m.id_medic, m.nume, m.prenume, m.cod_parafa, m.telefon, m.email,
                  s.denumire AS specializare,
                  count(pr.id_programare) FILTER (WHERE pr.status = 'programat'
                                                  AND pr.data_ora >= NOW()) AS programari_viitoare
           FROM medici m
           JOIN specializari s USING (id_specializare)
           LEFT JOIN programari pr USING (id_medic)
           WHERE (%(spec)s::int IS NULL OR m.id_specializare = %(spec)s)
           GROUP BY m.id_medic, s.denumire
           ORDER BY s.denumire, m.nume""", {"spec": id_spec or None})
    specializari = db.query("SELECT id_specializare, denumire FROM specializari ORDER BY denumire")
    return render_template("medici_list.html", rows=rows, specializari=specializari,
                           id_spec=id_spec)


def _din_formular(form):
    item = {c: gol_la_null(form.get(c)) for c in ("nume", "prenume", "cod_parafa", "telefon", "email")}
    item["id_specializare"] = form.get("id_specializare") or None
    if item["cod_parafa"]:
        item["cod_parafa"] = item["cod_parafa"].upper()
    return item


@bp.route("/nou", methods=["GET", "POST"])
@role_required("admin")
def creare():
    item = {}
    if request.method == "POST":
        item = _din_formular(request.form)
        try:
            db.execute(
                """INSERT INTO medici (nume, prenume, id_specializare, cod_parafa, telefon, email)
                   VALUES (%(nume)s, %(prenume)s, %(id_specializare)s, %(cod_parafa)s,
                           %(telefon)s, %(email)s)""", item)
            flash("Medicul a fost adăugat.", "success")
            return redirect(url_for("medici.lista"))
        except db.DBError as err:
            flash(db.mesaj_eroare(err), "danger")
    specializari = db.query("SELECT id_specializare, denumire FROM specializari ORDER BY denumire")
    return render_template("medic_form.html", item=item, specializari=specializari, nou=True)


@bp.route("/<int:id>/editare", methods=["GET", "POST"])
@role_required("admin")
def editare(id):
    item = db.query_one("SELECT * FROM medici WHERE id_medic = %s", (id,))
    if not item:
        abort(404)
    if request.method == "POST":
        item = {**_din_formular(request.form), "id_medic": id}
        try:
            db.execute(
                """UPDATE medici SET nume = %(nume)s, prenume = %(prenume)s,
                          id_specializare = %(id_specializare)s, cod_parafa = %(cod_parafa)s,
                          telefon = %(telefon)s, email = %(email)s
                   WHERE id_medic = %(id_medic)s""", item)
            flash("Datele medicului au fost actualizate.", "success")
            return redirect(url_for("medici.lista"))
        except db.DBError as err:
            flash(db.mesaj_eroare(err), "danger")
    specializari = db.query("SELECT id_specializare, denumire FROM specializari ORDER BY denumire")
    return render_template("medic_form.html", item=item, specializari=specializari, nou=False)


@bp.route("/<int:id>/stergere", methods=["POST"])
@role_required("admin")
def stergere(id):
    try:
        # ON DELETE RESTRICT pe programari: un medic cu programări nu poate fi șters
        db.execute("DELETE FROM medici WHERE id_medic = %s", (id,))
        flash("Medicul a fost șters.", "success")
    except db.DBError as err:
        flash(db.mesaj_eroare(err), "danger")
    return redirect(url_for("medici.lista"))
