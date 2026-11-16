"""
Etapa 3 — Autentificare și roluri.

Roluri (tabelul `roluri`):
  admin        — acces total + gestionarea conturilor
  receptioner  — pacienți, programări, vede medicii
  medic        — programările proprii, consultații și rețete pentru pacienții lui
  pacient      — doar propriile programări, consultații și rețete

Parola NU se verifică în Python: funcția SQL autentifica() compară
crypt(parola, hash) direct în PostgreSQL (bcrypt, extensia pgcrypto).
"""
from functools import wraps

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, session, url_for)

import db

bp = Blueprint("auth", __name__)

ROLURI = ("admin", "receptioner", "medic", "pacient")


# ---------------------------------------------------------------------------
# Utilizatorul curent + decoratori
# ---------------------------------------------------------------------------
def load_user():
    """Rulează înaintea fiecărui request: pune utilizatorul logat în g.user."""
    g.user = session.get("user")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash("Autentifică-te pentru a continua.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roluri):
    """@role_required('admin', 'receptioner') — 403 pentru celelalte roluri."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["rol"] not in roluri:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def are_rol(*roluri):
    return bool(g.user) and g.user["rol"] in roluri


# ---------------------------------------------------------------------------
# Login / logout / schimbare parolă
# ---------------------------------------------------------------------------
@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        parola = request.form.get("parola", "")
        cont = db.query_one("SELECT * FROM autentifica(%s, %s)", (email, parola))
        if cont is None:
            flash("Email sau parolă greșită (sau cont dezactivat).", "danger")
            return render_template("login.html", email=email), 401
        db.execute("UPDATE utilizatori SET ultima_autentificare = NOW() WHERE id_utilizator = %s",
                   (cont["id_utilizator"],))
        session.clear()
        session["user"] = {
            "id_utilizator": cont["id_utilizator"],
            "email": cont["email"],
            "rol": cont["rol"],
            "id_medic": cont["id_medic"],
            "id_pacient": cont["id_pacient"],
            "nume": cont["nume_afisat"],
        }
        flash(f"Bine ai venit, {cont['nume_afisat']}!", "success")
        nxt = request.args.get("next")
        return redirect(nxt if nxt and nxt.startswith("/") else url_for("index"))
    return render_template("login.html", email="")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Te-ai deconectat.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/cont/parola", methods=["GET", "POST"])
@login_required
def schimba_parola():
    if request.method == "POST":
        veche = request.form.get("parola_veche", "")
        noua = request.form.get("parola_noua", "")
        confirmare = request.form.get("confirmare", "")
        if len(noua) < 8:
            flash("Parola nouă trebuie să aibă cel puțin 8 caractere.", "danger")
        elif noua != confirmare:
            flash("Confirmarea nu coincide cu parola nouă.", "danger")
        else:
            row = db.execute(
                """UPDATE utilizatori
                   SET parola_hash = crypt(%s, gen_salt('bf', 8))
                   WHERE id_utilizator = %s AND parola_hash = crypt(%s, parola_hash)
                   RETURNING id_utilizator""",
                (noua, g.user["id_utilizator"], veche))
            if row:
                flash("Parola a fost schimbată.", "success")
                return redirect(url_for("index"))
            flash("Parola veche este greșită.", "danger")
    return render_template("schimba_parola.html")


# ---------------------------------------------------------------------------
# Administrare conturi (doar admin) — CRUD pe `utilizatori`
# ---------------------------------------------------------------------------
@bp.route("/utilizatori")
@role_required("admin")
def utilizatori_list():
    q = request.args.get("q", "").strip()
    rol = request.args.get("rol", "")
    rows = db.query(
        """SELECT u.id_utilizator, u.email, r.denumire AS rol, u.activ,
                  COALESCE(m.prenume || ' ' || m.nume, p.prenume || ' ' || p.nume, '—') AS persoana,
                  u.ultima_autentificare
           FROM utilizatori u
           JOIN roluri r USING (id_rol)
           LEFT JOIN medici m   ON m.id_utilizator = u.id_utilizator
           LEFT JOIN pacienti p ON p.id_utilizator = u.id_utilizator
           WHERE (%(q)s = '' OR u.email ILIKE '%%' || %(q)s || '%%')
             AND (%(rol)s = '' OR r.denumire = %(rol)s)
           ORDER BY r.id_rol, u.email""",
        {"q": q, "rol": rol})
    return render_template("utilizatori_list.html", rows=rows, q=q, rol=rol, roluri=ROLURI)


def _optiuni_cont(id_utilizator=None):
    roluri = db.query("SELECT id_rol, denumire FROM roluri ORDER BY id_rol")
    medici = db.query(
        """SELECT id_medic, nume || ' ' || prenume || ' (' || cod_parafa || ')' AS eticheta
           FROM medici WHERE id_utilizator IS NULL OR id_utilizator = %s ORDER BY nume""",
        (id_utilizator,))
    pacienti = db.query(
        """SELECT id_pacient, nume || ' ' || prenume || ' (' || cnp || ')' AS eticheta
           FROM pacienti WHERE id_utilizator IS NULL OR id_utilizator = %s ORDER BY nume""",
        (id_utilizator,))
    return roluri, medici, pacienti


def _int_or_none(value):
    return int(value) if value not in (None, "") else None


def _valideaza_asociere(rol_nume, id_medic, id_pacient):
    if rol_nume == "medic" and not id_medic:
        return "Un cont de medic trebuie asociat cu un medic."
    if rol_nume == "pacient" and not id_pacient:
        return "Un cont de pacient trebuie asociat cu un pacient."
    return None


@bp.route("/utilizatori/nou", methods=["GET", "POST"])
@role_required("admin")
def utilizatori_create():
    roluri, medici, pacienti = _optiuni_cont()
    form = request.form
    if request.method == "POST":
        id_rol = int(form["id_rol"])
        rol_nume = next(r["denumire"] for r in roluri if r["id_rol"] == id_rol)
        id_medic = _int_or_none(form.get("id_medic")) if rol_nume == "medic" else None
        id_pacient = _int_or_none(form.get("id_pacient")) if rol_nume == "pacient" else None
        eroare = _valideaza_asociere(rol_nume, id_medic, id_pacient)
        if len(form.get("parola", "")) < 8:
            eroare = "Parola trebuie să aibă cel puțin 8 caractere."
        if eroare:
            flash(eroare, "danger")
        else:
            try:
                # Un singur statement: creează contul și îl leagă de medic/pacient (atomic)
                db.execute(
                    """WITH u AS (
                           INSERT INTO utilizatori (email, parola_hash, id_rol, activ)
                           VALUES (%s, crypt(%s, gen_salt('bf', 8)), %s, %s)
                           RETURNING id_utilizator),
                       m AS (UPDATE medici   SET id_utilizator = (SELECT id_utilizator FROM u)
                             WHERE id_medic = %s),
                       p AS (UPDATE pacienti SET id_utilizator = (SELECT id_utilizator FROM u)
                             WHERE id_pacient = %s)
                       SELECT id_utilizator FROM u""",
                    (form["email"].strip(), form["parola"], id_rol, "activ" in form,
                     id_medic, id_pacient))
                flash("Contul a fost creat.", "success")
                return redirect(url_for("auth.utilizatori_list"))
            except db.DBError as err:
                flash(db.mesaj_eroare(err), "danger")
    return render_template("utilizator_form.html", item=form or {"activ": True},
                           roluri=roluri, medici=medici, pacienti=pacienti, nou=True)


@bp.route("/utilizatori/<int:id>/editare", methods=["GET", "POST"])
@role_required("admin")
def utilizatori_edit(id):
    item = db.query_one(
        """SELECT u.id_utilizator, u.email, u.id_rol, u.activ, m.id_medic, p.id_pacient
           FROM utilizatori u
           LEFT JOIN medici m   ON m.id_utilizator = u.id_utilizator
           LEFT JOIN pacienti p ON p.id_utilizator = u.id_utilizator
           WHERE u.id_utilizator = %s""", (id,))
    if not item:
        abort(404)
    roluri, medici, pacienti = _optiuni_cont(id)
    if request.method == "POST":
        form = request.form
        id_rol = int(form["id_rol"])
        rol_nume = next(r["denumire"] for r in roluri if r["id_rol"] == id_rol)
        id_medic = _int_or_none(form.get("id_medic")) if rol_nume == "medic" else None
        id_pacient = _int_or_none(form.get("id_pacient")) if rol_nume == "pacient" else None
        eroare = _valideaza_asociere(rol_nume, id_medic, id_pacient)
        if id == g.user["id_utilizator"] and (rol_nume != "admin" or "activ" not in form):
            eroare = "Nu îți poți scoate singur rolul de admin sau dezactiva propriul cont."
        if eroare:
            flash(eroare, "danger")
            item = {**item, **form.to_dict(), "activ": "activ" in form}
        else:
            stmts = [
                ("UPDATE utilizatori SET email = %s, id_rol = %s, activ = %s WHERE id_utilizator = %s",
                 (form["email"].strip(), id_rol, "activ" in form, id)),
                # refacem asocierea cu medic / pacient
                ("UPDATE medici   SET id_utilizator = NULL WHERE id_utilizator = %s", (id,)),
                ("UPDATE pacienti SET id_utilizator = NULL WHERE id_utilizator = %s", (id,)),
                ("UPDATE medici   SET id_utilizator = %s WHERE id_medic = %s", (id, id_medic)),
                ("UPDATE pacienti SET id_utilizator = %s WHERE id_pacient = %s", (id, id_pacient)),
            ]
            if form.get("parola"):
                if len(form["parola"]) < 8:
                    flash("Parola trebuie să aibă cel puțin 8 caractere.", "danger")
                    return render_template("utilizator_form.html", item=item, roluri=roluri,
                                           medici=medici, pacienti=pacienti, nou=False)
                stmts.append(("UPDATE utilizatori SET parola_hash = crypt(%s, gen_salt('bf', 8)) "
                              "WHERE id_utilizator = %s", (form["parola"], id)))
            try:
                db.transaction(stmts)
                flash("Contul a fost actualizat.", "success")
                return redirect(url_for("auth.utilizatori_list"))
            except db.DBError as err:
                flash(db.mesaj_eroare(err), "danger")
                item = {**item, **form.to_dict(), "activ": "activ" in form}
    return render_template("utilizator_form.html", item=item, roluri=roluri,
                           medici=medici, pacienti=pacienti, nou=False)


@bp.route("/utilizatori/<int:id>/stergere", methods=["POST"])
@role_required("admin")
def utilizatori_delete(id):
    if id == g.user["id_utilizator"]:
        flash("Nu îți poți șterge propriul cont.", "danger")
    else:
        # medici/pacienti.id_utilizator au ON DELETE SET NULL: persoana rămâne, doar contul dispare
        db.execute("DELETE FROM utilizatori WHERE id_utilizator = %s", (id,))
        flash("Contul a fost șters.", "success")
    return redirect(url_for("auth.utilizatori_list"))
