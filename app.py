"""
Clinică medicală — aplicația web (Flask + PostgreSQL).

Pornire:
    python app.py            -> http://127.0.0.1:5000
"""
import os
from datetime import date, datetime

from flask import Flask, g, render_template

import db
from auth import are_rol, bp as auth_bp, load_user, login_required


def create_app():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "schimba-ma-in-env")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    app.before_request(load_user)
    app.teardown_appcontext(db.close_conn)

    from routes import consultatii, medici, nomenclatoare, pacienti, programari
    app.register_blueprint(auth_bp)
    for module in (pacienti, medici, nomenclatoare, programari, consultatii):
        app.register_blueprint(module.bp)

    # ---------------- filtre și funcții disponibile în șabloane ----------------
    @app.template_filter("dt")
    def format_dt(value, fmt="%d.%m.%Y %H:%M"):
        if not value:
            return "—"
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        if isinstance(value, datetime):
            return value.strftime(fmt)
        if isinstance(value, date):
            return value.strftime("%d.%m.%Y")
        return value

    @app.template_filter("d")
    def format_d(value):
        return format_dt(value, "%d.%m.%Y")

    @app.template_filter("input_dt")
    def input_dt(value):
        """Valoare pentru <input type=datetime-local>."""
        if not value:
            return ""
        if isinstance(value, str):
            return value.replace(" ", "T")[:16]
        return value.strftime("%Y-%m-%dT%H:%M")

    @app.template_filter("input_d")
    def input_d(value):
        if not value:
            return ""
        return str(value)[:10]

    app.jinja_env.globals["are_rol"] = are_rol

    # ---------------- pagina principală (diferită pe rol) ----------------
    @app.route("/")
    @login_required
    def index():
        rol = g.user["rol"]
        if rol in ("admin", "receptioner"):
            stats = db.query_one(
                """SELECT (SELECT count(*) FROM pacienti) AS pacienti,
                          (SELECT count(*) FROM medici) AS medici,
                          (SELECT count(*) FROM programari
                             WHERE status = 'programat' AND data_ora >= NOW()) AS viitoare,
                          (SELECT count(*) FROM programari
                             WHERE data_ora::date = CURRENT_DATE) AS azi,
                          (SELECT count(*) FROM consultatii) AS consultatii""")
            urmatoare = db.query(
                """SELECT pr.id_programare, pr.data_ora, pr.status,
                          p.nume || ' ' || p.prenume AS pacient,
                          m.nume || ' ' || m.prenume AS medic, s.denumire AS specializare
                   FROM programari pr
                   JOIN pacienti p USING (id_pacient)
                   JOIN medici m USING (id_medic)
                   JOIN specializari s USING (id_specializare)
                   WHERE pr.status = 'programat' AND pr.data_ora >= NOW()
                   ORDER BY pr.data_ora LIMIT 10""")
            return render_template("index_staff.html", stats=stats, urmatoare=urmatoare)

        if rol == "medic":
            urmatoare = db.query(
                """SELECT pr.id_programare, pr.data_ora, pr.status, pr.motiv,
                          p.nume || ' ' || p.prenume AS pacient, p.id_pacient
                   FROM programari pr JOIN pacienti p USING (id_pacient)
                   WHERE pr.id_medic = %s AND pr.status = 'programat' AND pr.data_ora >= CURRENT_DATE
                   ORDER BY pr.data_ora LIMIT 15""", (g.user["id_medic"],))
            stats = db.query_one(
                """SELECT count(*) FILTER (WHERE status = 'finalizat') AS finalizate,
                          count(*) FILTER (WHERE status = 'programat' AND data_ora >= NOW()) AS viitoare
                   FROM programari WHERE id_medic = %s""", (g.user["id_medic"],))
            return render_template("index_medic.html", urmatoare=urmatoare, stats=stats)

        # pacient
        urmatoare = db.query(
            """SELECT pr.id_programare, pr.data_ora, pr.status, pr.motiv,
                      m.nume || ' ' || m.prenume AS medic, s.denumire AS specializare
               FROM programari pr
               JOIN medici m USING (id_medic)
               JOIN specializari s USING (id_specializare)
               WHERE pr.id_pacient = %s AND pr.data_ora >= NOW() AND pr.status = 'programat'
               ORDER BY pr.data_ora""", (g.user["id_pacient"],))
        return render_template("index_pacient.html", urmatoare=urmatoare)

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("eroare.html", cod=403,
                               mesaj="Nu ai drepturi pentru această pagină."), 403

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("eroare.html", cod=404, mesaj="Pagina nu există."), 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
