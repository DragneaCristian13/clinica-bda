#!/usr/bin/env python3
"""
Generator de fixtures pentru baza de date a clinicii (Etapa 1).

Produce sql/02_seed.sql cu date realiste și consistente:
  - CNP-uri valide (cu cifră de control corectă)
  - programări fără suprapuneri pe medic, doar în zile lucrătoare 08:00-16:00
  - consultații doar pentru programările finalizate
  - rețete + medicamente pe rețetă

Utilizare:
  python3 genereaza_fixtures.py                     # dimensiuni implicite
  python3 genereaza_fixtures.py --pacienti 5000 --programari 50000   # pt. load test (etapa 4)
"""
import argparse
import random
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------
# Date de bază
# ---------------------------------------------------------------------
NUME = ["Popescu", "Ionescu", "Popa", "Pop", "Radu", "Dumitru", "Stan", "Stoica", "Gheorghe",
        "Matei", "Constantin", "Rusu", "Munteanu", "Ciobanu", "Lazăr", "Florea", "Dragomir",
        "Tudor", "Moldovan", "Barbu", "Neagu", "Marin", "Cristea", "Ene", "Dinu", "Toma",
        "Ursu", "Mihai", "Iordache", "Nistor", "Sandu", "Voicu", "Preda", "Dobre", "Avram"]
PRENUME_M = ["Andrei", "Alexandru", "Mihai", "Ion", "Cristian", "Gabriel", "Florin", "Bogdan",
             "Adrian", "Răzvan", "Vlad", "Ștefan", "George", "Marius", "Darius", "Matei", "Radu"]
PRENUME_F = ["Maria", "Elena", "Ioana", "Andreea", "Ana", "Alexandra", "Cristina", "Mihaela",
             "Diana", "Gabriela", "Raluca", "Irina", "Bianca", "Larisa", "Sofia", "Teodora"]
ORASE = [("București", 40), ("Cluj-Napoca", 12), ("Iași", 22), ("Timișoara", 35),
         ("Constanța", 13), ("Brașov", 8), ("Craiova", 16), ("Ploiești", 29)]
STRAZI = ["Victoriei", "Libertății", "Unirii", "Mihai Eminescu", "Florilor", "Republicii",
          "Independenței", "Ștefan cel Mare", "Avram Iancu", "Primăverii"]

SPECIALIZARI = ["Medicină de familie", "Cardiologie", "Pediatrie", "Dermatologie",
                "Neurologie", "Endocrinologie", "Gastroenterologie", "Oftalmologie",
                "ORL", "Ortopedie"]

ROLURI = [
    ("admin",       "Administrator — gestionează utilizatori, medici, nomenclatoare"),
    ("medic",       "Medic — vede programările proprii, completează consultații și rețete"),
    ("receptioner", "Recepție — gestionează pacienți și programări"),
    ("pacient",     "Pacient — își vede programările și istoricul medical"),
]

MEDICAMENTE = [
    ("Paracetamol", "Paracetamol", "comprimate", "500 mg"),
    ("Nurofen", "Ibuprofen", "comprimate", "400 mg"),
    ("Augmentin", "Amoxicilină + acid clavulanic", "comprimate", "875/125 mg"),
    ("Amoxicilină", "Amoxicilină", "capsule", "500 mg"),
    ("Klacid", "Claritromicină", "comprimate", "500 mg"),
    ("Aspenter", "Acid acetilsalicilic", "comprimate", "75 mg"),
    ("Prestarium", "Perindopril", "comprimate", "5 mg"),
    ("Concor", "Bisoprolol", "comprimate", "5 mg"),
    ("Sortis", "Atorvastatină", "comprimate", "20 mg"),
    ("Siofor", "Metformin", "comprimate", "850 mg"),
    ("Euthyrox", "Levotiroxină", "comprimate", "50 mcg"),
    ("Omeran", "Omeprazol", "capsule", "20 mg"),
    ("Controloc", "Pantoprazol", "comprimate", "40 mg"),
    ("Smecta", "Diosmectită", "plic", "3 g"),
    ("Aerius", "Desloratadină", "comprimate", "5 mg"),
    ("Claritine", "Loratadină", "sirop", "1 mg/ml"),
    ("Nurofen pentru copii", "Ibuprofen", "suspensie orală", "100 mg/5 ml"),
    ("Fluimucil", "Acetilcisteină", "comprimate efervescente", "600 mg"),
    ("Bioflorin", "Enterococcus faecium", "capsule", "75 mg"),
    ("Fucidin", "Acid fusidic", "cremă", "2%"),
    ("Advantan", "Metilprednisolon aceponat", "cremă", "0,1%"),
    ("Tobradex", "Tobramicină + dexametazonă", "picături oftalmice", "3/1 mg/ml"),
    ("Otipax", "Fenazonă + lidocaină", "picături auriculare", "40/10 mg/g"),
    ("Diclofenac", "Diclofenac", "gel", "1%"),
    ("Mydocalm", "Tolperison", "comprimate", "150 mg"),
    ("Magne B6", "Magneziu + vitamina B6", "comprimate", "470/5 mg"),
    ("Vitamina D3", "Colecalciferol", "picături orale", "2000 UI/ml"),
    ("Xyzal", "Levocetirizină", "comprimate", "5 mg"),
]

# (motiv, simptome, diagnostic, recomandari, [indici medicamente posibile])
CAZURI = [
    ("Febră și dureri în gât", "Febră 38.5°C, odinofagie, adenopatie cervicală",
     "Angină pultacee", "Repaus, hidratare abundentă, control la 7 zile", [0, 2, 3]),
    ("Tuse persistentă", "Tuse productivă de 10 zile, subfebrilitate",
     "Bronșită acută", "Hidratare, evitarea fumatului", [17, 0, 4]),
    ("Control tensiune", "Cefalee occipitală, TA 160/95 mmHg",
     "Hipertensiune arterială esențială gr. II", "Dietă hiposodată, mișcare zilnică 30 min", [6, 7, 5]),
    ("Palpitații", "Palpitații la efort, AV 105/min",
     "Tahicardie sinusală", "Reducerea cafeinei, EKG Holter", [7, 25]),
    ("Analize colesterol", "Asimptomatic, LDL 185 mg/dl",
     "Dislipidemie mixtă", "Dietă hipolipidică, reevaluare la 3 luni", [8]),
    ("Glicemie mare", "Poliurie, polidipsie, glicemie à jeun 142 mg/dl",
     "Diabet zaharat tip 2", "Dietă, HbA1c la 3 luni", [9]),
    ("Oboseală cronică", "Astenie, creștere în greutate, TSH 7.8",
     "Hipotiroidism", "Control endocrinologic la 6 săptămâni", [10]),
    ("Arsuri epigastrice", "Pirozis postprandial, regurgitații acide",
     "Boală de reflux gastroesofagian", "Mese mici, fără alimente picante seara", [11, 12]),
    ("Diaree", "Scaune diareice 4-5/zi de 2 zile",
     "Gastroenterită acută", "Rehidratare orală, regim alimentar", [13, 18]),
    ("Alergie sezonieră", "Rinoree, strănut, prurit ocular",
     "Rinită alergică sezonieră", "Evitarea alergenilor", [14, 26]),
    ("Erupție cutanată", "Leziuni eritematoase pruriginoase pe antebrațe",
     "Dermatită de contact", "Evitarea agentului iritant", [20, 14]),
    ("Leziune infectată", "Leziune crustoasă perinazală",
     "Impetigo", "Igienă locală riguroasă", [19]),
    ("Ochi roșu", "Hiperemie conjunctivală, secreție purulentă",
     "Conjunctivită bacteriană", "Igiena ochilor, nu purtați lentile", [21]),
    ("Durere de ureche", "Otalgie dreaptă, timpan congestionat",
     "Otită medie acută", "Control ORL la 7 zile", [22, 0]),
    ("Durere lombară", "Lombalgie după efort, contractură paravertebrală",
     "Lombalgie acută mecanică", "Evitarea efortului, kinetoterapie", [23, 24, 1]),
    ("Durere de genunchi", "Gonalgie la mers, crepitații",
     "Gonartroză", "Scădere ponderală, kinetoterapie", [23, 1]),
    ("Cefalee", "Cefalee pulsatilă, fotofobie",
     "Migrenă fără aură", "Jurnal al crizelor, somn regulat", [1, 25]),
    ("Control copil", "Febră 38°C, rinoree",
     "Rinofaringită acută", "Dezobstrucție nazală, hidratare", [16, 15]),
    ("Control de rutină", "Asimptomatic",
     "Stare de sănătate bună", "Control anual", [26]),
]
MOTIVE_VIITOARE = [c[0] for c in CAZURI] + ["Rezultate analize", "Consult preventiv", "Reevaluare tratament"]
FRECVENTE = ["o dată pe zi", "de 2 ori pe zi", "de 3 ori pe zi", "la nevoie, max. 3/zi", "seara"]


def q(s):
    """Literal SQL sigur (sau NULL)."""
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def fara_diacritice(s):
    tabel = str.maketrans("ăâîșşțţĂÂÎȘŞȚŢ", "aaissttAAISSTT")
    return s.translate(tabel).lower().replace(" ", "").replace("-", "")


def cnp_valid(sex, nastere, judet):
    """CNP românesc cu cifra de control calculată."""
    if nastere.year >= 2000:
        s = 5 if sex == "M" else 6
    else:
        s = 1 if sex == "M" else 2
    baza = f"{s}{nastere:%y%m%d}{judet:02d}{random.randint(1, 999):03d}"
    cheie = "279146358279"
    rest = sum(int(a) * int(b) for a, b in zip(baza, cheie)) % 11
    return baza + ("1" if rest == 10 else str(rest))


def telefon():
    return "07" + "".join(str(random.randint(0, 9)) for _ in range(8))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pacienti", type=int, default=60)
    ap.add_argument("--programari", type=int, default=300)
    ap.add_argument("--azi", default="2026-11-01", help="data de referință (trecut/viitor)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="sql/02_seed.sql")
    a = ap.parse_args()
    random.seed(a.seed)
    azi = datetime.fromisoformat(a.azi)

    out = []
    w = out.append
    w("-- =====================================================================")
    w("--  Etapa 1: FIXTURES — date de test (generat de genereaza_fixtures.py)")
    w(f"--  pacienți={a.pacienti}, programări={a.programari}, data de referință={a.azi}")
    w("-- =====================================================================")
    w("SET search_path TO clinica;")
    w("BEGIN;\n")

    # --- roluri ------------------------------------------------------------
    w("-- Roluri")
    w("INSERT INTO roluri (id_rol, denumire, descriere) VALUES")
    w(",\n".join(f"  ({i}, {q(n)}, {q(d)})" for i, (n, d) in enumerate(ROLURI, 1)) + ";\n")
    ROL = {n: i for i, (n, _) in enumerate(ROLURI, 1)}

    # --- specializari --------------------------------------------------------
    w("-- Specializări")
    w("INSERT INTO specializari (id_specializare, denumire) VALUES")
    w(",\n".join(f"  ({i}, {q(s)})" for i, s in enumerate(SPECIALIZARI, 1)) + ";\n")

    # --- utilizatori ---------------------------------------------------------
    utilizatori = []  # (id, email, rol)
    emails = set()

    def adauga_user(email, rol):
        uid = len(utilizatori) + 1
        utilizatori.append((uid, email, ROL[rol]))
        emails.add(email)
        return uid

    adauga_user("admin@clinica.ro", "admin")
    adauga_user("receptie1@clinica.ro", "receptioner")
    adauga_user("receptie2@clinica.ro", "receptioner")

    # --- medici --------------------------------------------------------------
    medici = []
    parafe = set()
    # cel puțin 2 medici de familie, apoi câte unul pe celelalte specializări + câțiva extra
    spec_medici = [1, 1, 2, 3, 3, 4, 5, 6, 7, 8, 9, 10, 2]
    for idm, spec in enumerate(spec_medici, 1):
        sex = random.choice("MF")
        nume = random.choice(NUME)
        pren = random.choice(PRENUME_M if sex == "M" else PRENUME_F)
        email = f"dr.{fara_diacritice(pren)}.{fara_diacritice(nume)}@clinica.ro"
        while email in emails:
            email = email.replace("@", f"{random.randint(1, 9)}@", 1)
        uid = adauga_user(email, "medic")
        while True:
            p = random.choice("ABCDEFGHKLMNPRSTVZ") + f"{random.randint(0, 99999):05d}"
            if p not in parafe:
                parafe.add(p)
                break
        medici.append((idm, uid, nume, pren, spec, p, telefon(), email))

    # --- pacienti ------------------------------------------------------------
    pacienti = []
    cnpuri = set()
    for idp in range(1, a.pacienti + 1):
        sex = random.choice("MF")
        nume = random.choice(NUME)
        pren = random.choice(PRENUME_M if sex == "M" else PRENUME_F)
        # ~15% copii, restul adulți
        if random.random() < 0.15:
            nastere = date(random.randint(2010, 2024), random.randint(1, 12), random.randint(1, 28))
        else:
            nastere = date(random.randint(1940, 2007), random.randint(1, 12), random.randint(1, 28))
        oras, judet = random.choice(ORASE)
        cnp = cnp_valid(sex, nastere, judet)
        while cnp in cnpuri:
            cnp = cnp_valid(sex, nastere, judet)
        cnpuri.add(cnp)
        email = f"{fara_diacritice(pren)}.{fara_diacritice(nume)}{idp}@exemplu.ro"
        # ~60% din pacienți au cont în aplicație
        uid = adauga_user(email, "pacient") if random.random() < 0.6 else None
        adresa = f"Str. {random.choice(STRAZI)} nr. {random.randint(1, 120)}, {oras}"
        pacienti.append((idp, uid, nume, pren, cnp, nastere, sex, telefon(), email, adresa))

    w("-- Utilizatori")
    w("INSERT INTO utilizatori (id_utilizator, email, id_rol) VALUES")
    w(",\n".join(f"  ({u}, {q(e)}, {r})"
                 for u, e, r in utilizatori) + ";\n")

    w("-- Medici")
    w("INSERT INTO medici (id_medic, id_utilizator, nume, prenume, id_specializare, cod_parafa, telefon, email) VALUES")
    w(",\n".join(f"  ({m[0]}, {m[1]}, {q(m[2])}, {q(m[3])}, {m[4]}, {q(m[5])}, {q(m[6])}, {q(m[7])})"
                 for m in medici) + ";\n")

    w("-- Pacienți")
    w("INSERT INTO pacienti (id_pacient, id_utilizator, nume, prenume, cnp, data_nasterii, sex, telefon, email, adresa) VALUES")
    w(",\n".join(f"  ({p[0]}, {p[1] if p[1] else 'NULL'}, {q(p[2])}, {q(p[3])}, {q(p[4])}, "
                 f"{q(p[5].isoformat())}, {q(p[6])}, {q(p[7])}, {q(p[8])}, {q(p[9])})"
                 for p in pacienti) + ";\n")

    # --- medicamente ---------------------------------------------------------
    w("-- Medicamente")
    w("INSERT INTO medicamente (id_medicament, denumire, substanta_activa, forma, concentratie) VALUES")
    w(",\n".join(f"  ({i}, {q(d)}, {q(s)}, {q(f)}, {q(c)})"
                 for i, (d, s, f, c) in enumerate(MEDICAMENTE, 1)) + ";\n")

    # --- programari ----------------------------------------------------------
    # interval: ultimele 6 luni + următoarele 6 săptămâni, zile lucrătoare, sloturi de 30 min
    ocupat = set()
    programari = []
    start = azi - timedelta(days=180)
    zile_total = 180 + 42
    zile_lucratoare = sum(1 for d in range(zile_total + 1) if (start + timedelta(days=d)).weekday() < 5)
    max_programari = int(zile_lucratoare * 16 * len(medici) * 0.9)
    if a.programari > max_programari:
        raise SystemExit(f"Prea multe programări: maxim ~{max_programari} pentru {len(medici)} medici "
                         f"(16 sloturi/zi). Folosește o valoare mai mică pentru --programari.")
    while len(programari) < a.programari:
        zi = start + timedelta(days=random.randint(0, zile_total))
        if zi.weekday() >= 5:
            continue
        slot = zi.replace(hour=8, minute=0, second=0) + timedelta(minutes=30 * random.randint(0, 15))
        m = random.choice(medici)
        if (m[0], slot) in ocupat:
            continue
        ocupat.add((m[0], slot))
        p = random.choice(pacienti)
        if slot < azi:
            status = random.choices(["finalizat", "anulat"], [85, 15])[0]
        else:
            status = random.choices(["programat", "anulat"], [92, 8])[0]
        caz = random.randrange(len(CAZURI)) if status == "finalizat" else None
        motiv = CAZURI[caz][0] if caz is not None else random.choice(MOTIVE_VIITOARE)
        creat = slot - timedelta(days=random.randint(1, 30), hours=random.randint(0, 8))
        programari.append([None, p[0], m[0], slot, 30, motiv, status, creat, caz])
    programari.sort(key=lambda x: x[3])
    for i, pr in enumerate(programari, 1):
        pr[0] = i

    w("-- Programări")
    w("INSERT INTO programari (id_programare, id_pacient, id_medic, data_ora, durata_minute, motiv, status, creat_la) VALUES")
    w(",\n".join(f"  ({p[0]}, {p[1]}, {p[2]}, '{p[3]:%Y-%m-%d %H:%M}', {p[4]}, {q(p[5])}, '{p[6]}', '{p[7]:%Y-%m-%d %H:%M}')"
                 for p in programari) + ";\n")

    # --- consultatii, retete, retete_medicamente -------------------------------
    consultatii, retete, rm = [], [], []
    for pr in programari:
        if pr[6] != "finalizat":
            continue
        _, simpt, diag, rec, meds = CAZURI[pr[8]]
        idc = len(consultatii) + 1
        consultatii.append((idc, pr[0], simpt, diag, rec, pr[3] + timedelta(minutes=25)))
        if random.random() < 0.8 and meds:
            idr = len(retete) + 1
            retete.append((idr, idc, pr[3].date(), random.choice([7, 14, 30, 90])))
            for idx in random.sample(meds, k=random.randint(1, min(3, len(meds)))):
                rm.append((idr, idx + 1, "1 " + ("comprimat" if "compr" in MEDICAMENTE[idx][2] else "doză"),
                           random.choice(FRECVENTE), random.choice([5, 7, 10, 14, 30]), random.randint(1, 3)))

    w("-- Consultații (doar pentru programările finalizate)")
    w("INSERT INTO consultatii (id_consultatie, id_programare, simptome, diagnostic, recomandari, creat_la) VALUES")
    w(",\n".join(f"  ({c[0]}, {c[1]}, {q(c[2])}, {q(c[3])}, {q(c[4])}, '{c[5]:%Y-%m-%d %H:%M}')"
                 for c in consultatii) + ";\n")

    w("-- Rețete")
    w("INSERT INTO retete (id_reteta, id_consultatie, data_emiterii, valabilitate_zile) VALUES")
    w(",\n".join(f"  ({r[0]}, {r[1]}, '{r[2]}', {r[3]})" for r in retete) + ";\n")

    w("-- Medicamente pe rețetă")
    w("INSERT INTO retete_medicamente (id_reteta, id_medicament, doza, frecventa, durata_zile, cantitate) VALUES")
    w(",\n".join(f"  ({x[0]}, {x[1]}, {q(x[2])}, {q(x[3])}, {x[4]}, {x[5]})" for x in rm) + ";\n")

    # resincronizare secvențe după inserare cu ID-uri explicite
    w("-- Resincronizare secvențe (am inserat ID-uri explicite)")
    for t, col in [("roluri", "id_rol"), ("utilizatori", "id_utilizator"),
                   ("specializari", "id_specializare"), ("medici", "id_medic"),
                   ("pacienti", "id_pacient"), ("programari", "id_programare"),
                   ("consultatii", "id_consultatie"), ("medicamente", "id_medicament"),
                   ("retete", "id_reteta")]:
        w(f"SELECT setval(pg_get_serial_sequence('clinica.{t}', '{col}'), (SELECT MAX({col}) FROM {t}));")
    w("\nCOMMIT;")

    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"{a.out}: {len(utilizatori)} utilizatori, {len(medici)} medici, {len(pacienti)} pacienți, "
          f"{len(programari)} programări, {len(consultatii)} consultații, {len(retete)} rețete, "
          f"{len(rm)} linii rețetă")


if __name__ == "__main__":
    main()
