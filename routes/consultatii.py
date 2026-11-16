"""CRUD Consultații și Rețete (date medicale — recepția NU are acces)."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

import db
from auth import login_required, role_required
from routes.util import gol_la_null, nr_pagini, paginare

bp = Blueprint("consultatii", __name__, url_prefix="/consultatii")

LINII_RETETA = 5  # câte medicamente se pot trece pe o rețetă din formular


def _consultatie(id):
    c = db.query_one(
        """SELECT c.*, pr.data_ora, pr.motiv, pr.id_medic, pr.id_pacient,
                  p.nume || ' ' || p.prenume AS pacient, p.cnp,
                  m.nume || ' ' || m.prenume AS medic, m.cod_parafa, s.denumire AS specializare
           FROM consultatii c
           JOIN programari pr USING (id_programare)
           JOIN pacienti p USING (id_pacient)
           JOIN medici m USING (id_medic)
           JOIN specializari s USING (id_specializare)
           WHERE c.id_consultatie = %s""", (id,))
    if not c:
        abort(404)
    return c


def _verifica_acces(c, scriere=False):
    rol = g.user["rol"]
    if rol == "admin":
        return
    if rol == "medic" and c["id_medic"] == g.user["id_medic"]:
        return
    if rol == "pacient" and not scriere and c["id_pacient"] == g.user["id_pacient"]:
        return
    abort(403)


# ============================ CONSULTAȚII ============================
@bp.route("/")
@role_required("admin", "medic", "pacient")
def lista():
    rol = g.user["rol"]
    q = request.args.get("q", "").strip()
    pagina, limit, offset = paginare()
    rows = db.query(
        """SELECT c.id_consultatie, pr.data_ora, c.diagnostic,
                  p.nume || ' ' || p.prenume AS pacient,
                  m.nume || ' ' || m.prenume AS medic,
                  (SELECT count(*) FROM retete r WHERE r.id_consultatie = c.id_consultatie) AS retete,
                  count(*) OVER () AS total
           FROM consultatii c
           JOIN programari pr USING (id_programare)
           JOIN pacienti p USING (id_pacient)
           JOIN medici m USING (id_medic)
           WHERE (%(medic)s::int IS NULL OR pr.id_medic = %(medic)s)
             AND (%(pacient)s::int IS NULL OR pr.id_pacient = %(pacient)s)
             AND (%(q)s = '' OR c.diagnostic ILIKE %(like)s
                  OR p.nume ILIKE %(like)s OR p.prenume ILIKE %(like)s)
           ORDER BY pr.data_ora DESC
           LIMIT %(limit)s OFFSET %(offset)s""",
        {"medic": g.user["id_medic"] if rol == "medic" else None,
         "pacient": g.user["id_pacient"] if rol == "pacient" else None,
         "q": q, "like": f"%{q}%", "limit": limit, "offset": offset})
    total = rows[0]["total"] if rows else 0
    return render_template("consultatii_list.html", rows=rows, q=q, pagina=pagina,
                           pagini=nr_pagini(total), total=total)


@bp.route("/<int:id>")
@login_required
def detalii(id):
    c = _consultatie(id)
    _verifica_acces(c)
    retete = db.query(
        """SELECT r.id_reteta, r.data_emiterii, r.valabilitate_zile,
                  r.data_emiterii + r.valabilitate_zile AS valabila_pana,
                  md.denumire, md.concentratie, md.forma,
                  rm.doza, rm.frecventa, rm.durata_zile, rm.cantitate
           FROM retete r
           LEFT JOIN retete_medicamente rm USING (id_reteta)
           LEFT JOIN medicamente md USING (id_medicament)
           WHERE r.id_consultatie = %s
           ORDER BY r.id_reteta, md.denumire""", (id,))
    # grupăm liniile pe rețete
    grupate = {}
    for row in retete:
        r = grupate.setdefault(row["id_reteta"], {**row, "linii": []})
        if row["denumire"]:
            r["linii"].append(row)
    return render_template("consultatie_detalii.html", c=c, retete=list(grupate.values()))


@bp.route("/nou", methods=["GET", "POST"])
@role_required("admin", "medic")
def creare():
    id_prog = request.values.get("programare", type=int)
    pr = db.query_one(
        """SELECT pr.*, p.nume || ' ' || p.prenume AS pacient, c.id_consultatie
           FROM programari pr JOIN pacienti p USING (id_pacient)
           LEFT JOIN consultatii c USING (id_programare)
           WHERE pr.id_programare = %s""", (id_prog,))
    if not pr:
        abort(404)
    if g.user["rol"] == "medic" and pr["id_medic"] != g.user["id_medic"]:
        abort(403)
    if pr["id_consultatie"]:
        return redirect(url_for("consultatii.editare", id=pr["id_consultatie"]))
    if pr["status"] != "finalizat":
        flash("Consultația se completează doar pentru programări finalizate.", "warning")
        return redirect(url_for("programari.lista"))
    item = {"simptome": "", "diagnostic": "", "recomandari": ""}
    if request.method == "POST":
        item = {c: gol_la_null(request.form.get(c)) for c in ("simptome", "diagnostic", "recomandari")}
        try:
            row = db.execute(
                """INSERT INTO consultatii (id_programare, simptome, diagnostic, recomandari)
                   VALUES (%s, %s, %s, %s) RETURNING id_consultatie""",
                (id_prog, item["simptome"], item["diagnostic"], item["recomandari"]))
            flash("Consultația a fost salvată.", "success")
            return redirect(url_for("consultatii.detalii", id=row["id_consultatie"]))
        except db.DBError as err:
            flash(db.mesaj_eroare(err), "danger")
    return render_template("consultatie_form.html", item=item, pr=pr, nou=True)


@bp.route("/<int:id>/editare", methods=["GET", "POST"])
@role_required("admin", "medic")
def editare(id):
    c = _consultatie(id)
    _verifica_acces(c, scriere=True)
    item = c
    if request.method == "POST":
        item = {**c, **{k: gol_la_null(request.form.get(k))
                        for k in ("simptome", "diagnostic", "recomandari")}}
        db.execute(
            """UPDATE consultatii SET simptome = %s, diagnostic = %s, recomandari = %s
               WHERE id_consultatie = %s""",
            (item["simptome"], item["diagnostic"], item["recomandari"], id))
        flash("Consultația a fost actualizată.", "success")
        return redirect(url_for("consultatii.detalii", id=id))
    pr = {"pacient": c["pacient"], "data_ora": c["data_ora"], "motiv": c["motiv"]}
    return render_template("consultatie_form.html", item=item, pr=pr, nou=False)


@bp.route("/<int:id>/stergere", methods=["POST"])
@role_required("admin", "medic")
def stergere(id):
    c = _consultatie(id)
    _verifica_acces(c, scriere=True)
    db.execute("DELETE FROM consultatii WHERE id_consultatie = %s", (id,))  # CASCADE -> rețete
    flash("Consultația (și rețetele ei) au fost șterse.", "success")
    return redirect(url_for("consultatii.lista"))


# ============================ REȚETE ============================
def _linii_din_formular(form):
    """Citește liniile med_1..med_5 din formular; ignoră rândurile goale."""
    linii = []
    for i in range(1, LINII_RETETA + 1):
        id_med = form.get(f"med_{i}")
        if not id_med:
            continue
        linii.append({
            "id_medicament": int(id_med),
            "doza": gol_la_null(form.get(f"doza_{i}")) or "1 comprimat",
            "frecventa": gol_la_null(form.get(f"frecventa_{i}")) or "o dată pe zi",
            "durata_zile": form.get(f"durata_{i}") or 7,
            "cantitate": form.get(f"cantitate_{i}") or 1,
        })
    return linii


INSERT_LINIE = """INSERT INTO retete_medicamente
                  (id_reteta, id_medicament, doza, frecventa, durata_zile, cantitate)
                  VALUES (%s, %s, %s, %s, %s, %s)"""

# la o rețetă nouă, id-ul ei îl dă currval() — valoarea tocmai generată în aceeași sesiune
INSERT_LINIE_RETETA_NOUA = """INSERT INTO retete_medicamente
                  (id_reteta, id_medicament, doza, frecventa, durata_zile, cantitate)
                  VALUES (currval(pg_get_serial_sequence('clinica.retete', 'id_reteta')),
                          %s, %s, %s, %s, %s)"""


@bp.route("/<int:id>/retete/nou", methods=["GET", "POST"])
@role_required("admin", "medic")
def reteta_creare(id):
    c = _consultatie(id)
    _verifica_acces(c, scriere=True)
    reteta = {"valabilitate_zile": 30}
    linii = []
    if request.method == "POST":
        reteta = {"valabilitate_zile": request.form.get("valabilitate_zile") or 30}
        linii = _linii_din_formular(request.form)
        if not linii:
            flash("Adaugă cel puțin un medicament pe rețetă.", "danger")
        else:
            # rețeta + toate liniile ei într-o singură tranzacție
            stmts = [("INSERT INTO retete (id_consultatie, valabilitate_zile) VALUES (%s, %s)",
                      (id, reteta["valabilitate_zile"]))]
            for l in linii:
                stmts.append((INSERT_LINIE_RETETA_NOUA,
                              (l["id_medicament"], l["doza"], l["frecventa"],
                               l["durata_zile"], l["cantitate"])))
            try:
                db.transaction(stmts)
                flash("Rețeta a fost emisă.", "success")
                return redirect(url_for("consultatii.detalii", id=id))
            except db.DBError as err:
                flash(db.mesaj_eroare(err), "danger")
    medicamente = db.query(
        "SELECT id_medicament, denumire || ' ' || concentratie || ' (' || forma || ')' AS eticheta "
        "FROM medicamente ORDER BY denumire")
    return render_template("reteta_form.html", c=c, reteta=reteta, linii=linii,
                           medicamente=medicamente, n=LINII_RETETA, nou=True)


@bp.route("/retete/<int:id_reteta>/editare", methods=["GET", "POST"])
@role_required("admin", "medic")
def reteta_editare(id_reteta):
    reteta = db.query_one("SELECT * FROM retete WHERE id_reteta = %s", (id_reteta,))
    if not reteta:
        abort(404)
    c = _consultatie(reteta["id_consultatie"])
    _verifica_acces(c, scriere=True)
    if request.method == "POST":
        valab = request.form.get("valabilitate_zile") or 30
        linii = _linii_din_formular(request.form)
        if not linii:
            flash("Rețeta trebuie să aibă cel puțin un medicament.", "danger")
        else:
            # înlocuim liniile: ștergem tot și reinserăm — atomic
            stmts = [("UPDATE retete SET valabilitate_zile = %s WHERE id_reteta = %s", (valab, id_reteta)),
                     ("DELETE FROM retete_medicamente WHERE id_reteta = %s", (id_reteta,))]
            for l in linii:
                stmts.append((INSERT_LINIE, (id_reteta, l["id_medicament"], l["doza"],
                                             l["frecventa"], l["durata_zile"], l["cantitate"])))
            try:
                db.transaction(stmts)
                flash("Rețeta a fost actualizată.", "success")
                return redirect(url_for("consultatii.detalii", id=c["id_consultatie"]))
            except db.DBError as err:
                flash(db.mesaj_eroare(err), "danger")
        reteta = {**reteta, "valabilitate_zile": valab}
    else:
        linii = db.query("SELECT * FROM retete_medicamente WHERE id_reteta = %s ORDER BY id_medicament",
                         (id_reteta,))
    medicamente = db.query(
        "SELECT id_medicament, denumire || ' ' || concentratie || ' (' || forma || ')' AS eticheta "
        "FROM medicamente ORDER BY denumire")
    return render_template("reteta_form.html", c=c, reteta=reteta, linii=linii,
                           medicamente=medicamente, n=LINII_RETETA, nou=False)


@bp.route("/retete/<int:id_reteta>/stergere", methods=["POST"])
@role_required("admin", "medic")
def reteta_stergere(id_reteta):
    reteta = db.query_one("SELECT * FROM retete WHERE id_reteta = %s", (id_reteta,))
    if not reteta:
        abort(404)
    c = _consultatie(reteta["id_consultatie"])
    _verifica_acces(c, scriere=True)
    db.execute("DELETE FROM retete WHERE id_reteta = %s", (id_reteta,))
    flash("Rețeta a fost ștearsă.", "success")
    return redirect(url_for("consultatii.detalii", id=c["id_consultatie"]))
