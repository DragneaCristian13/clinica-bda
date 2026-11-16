# Etapa 2 — Operații CRUD și descrierea paginilor

**Cerință:** operații CRUD + descrierea paginilor.
**Realizat:** aplicație web (Python + Flask) cu SQL scris direct pe PostgreSQL (fără ORM).
Există CRUD complet pe **8 tabele**: pacienți, medici, specializări, medicamente, programări, consultații, rețete (cu `retete_medicamente`) și utilizatori.

## Arhitectură pe scurt

```
browser ──HTTP──> Flask (app.py + routes/*.py) ──SQL──> PostgreSQL (Neon)
                     │
                     └── templates/*.html (Jinja2 + Bootstrap)
```

- `db.py` este singurul loc care vorbește cu baza de date. Expune `query`, `query_one`, `execute` și `transaction`.
- Parametrii se trimit separat (`%s`), niciodată prin concatenare de text. Asta protejează aplicația de **SQL injection**.
- Erorile venite din constrângeri (UNIQUE, CHECK, FK) sunt traduse în mesaje pe înțelesul utilizatorului. De exemplu, `pacienti_cnp_key` devine „Există deja un pacient cu acest CNP”.

## Paginile aplicației

### Pacienți — `routes/pacienti.py`

| Pagina | URL | Operație | SQL principal |
|---|---|---|---|
| Lista pacienților | `/pacienti/` | **R** | `SELECT ... ILIKE` pentru căutare după nume/CNP; paginare cu `LIMIT/OFFSET`; totalul vine din `count(*) OVER ()` |
| Fișa pacientului | `/pacienti/<id>` | **R** | datele pacientului + istoricul programărilor (JOIN cu medici, specializări, consultații); vârsta se calculează cu `age()` |
| Pacient nou | `/pacienti/nou` | **C** | `INSERT ... RETURNING id_pacient` |
| Editare pacient | `/pacienti/<id>/editare` | **U** | `UPDATE pacienti SET ...` |
| Ștergere | buton pe listă/fișă | **D** | `DELETE`; programările, consultațiile și rețetele se șterg automat prin **ON DELETE CASCADE** |

### Medici — `routes/medici.py`

| Pagina | URL | Operație | SQL principal |
|---|---|---|---|
| Lista medicilor | `/medici/` | **R** | JOIN cu specializări; numărul de programări viitoare cu `count(*) FILTER (WHERE ...)`; filtru pe specializare |
| Medic nou / editare | `/medici/nou`, `/medici/<id>/editare` | **C/U** | `INSERT` / `UPDATE`; codul de parafă e trecut automat cu majuscule |
| Ștergere | buton | **D** | un medic care are programări **nu** poate fi șters (**ON DELETE RESTRICT**); utilizatorul primește un mesaj |

### Nomenclatoare — `routes/nomenclatoare.py`

| Pagina | URL | Operație | Observații |
|---|---|---|---|
| Specializări | `/specializari` | **CRUD** | arată și câți medici are fiecare specializare; o specializare folosită nu se poate șterge |
| Medicamente | `/medicamente` | **CRUD** | căutare după denumire sau substanță activă; arată de câte ori a fost prescris; un medicament prescris nu se poate șterge |

### Programări — `routes/programari.py`

| Pagina | URL | Operație | SQL principal |
|---|---|---|---|
| Lista programărilor | `/programari/` | **R** | JOIN pe 4 tabele; filtre după pacient, medic, status și interval de date; paginare |
| Programare nouă | `/programari/nou` | **C** | `INSERT`; data trebuie să fie în viitor; dacă medicul e deja ocupat la ora aleasă, constrângerea `UNIQUE (id_medic, data_ora)` blochează programarea |
| Editare | `/programari/<id>/editare` | **U** | `UPDATE` pe toate câmpurile, inclusiv statusul |
| Schimbare status | butoanele ✓ / ✗ | **U** | `UPDATE programari SET status = ...`; după „finalizat”, medicul ajunge direct la formularul de consultație |
| Ștergere | buton | **D** | `DELETE`; consultația legată se șterge prin CASCADE |

### Consultații și rețete — `routes/consultatii.py`

| Pagina | URL | Operație | SQL principal |
|---|---|---|---|
| Lista consultațiilor | `/consultatii/` | **R** | JOIN cu programări, pacienți și medici; numărul de rețete prin subinterogare |
| Fișa consultației | `/consultatii/<id>` | **R** | consultația + rețetele, cu toate medicamentele lor (LEFT JOIN `retete` → `retete_medicamente` → `medicamente`); data expirării: `data_emiterii + valabilitate_zile` |
| Consultație nouă | `/consultatii/nou?programare=<id>` | **C** | se poate crea doar pentru o programare **finalizată** și doar una per programare (`UNIQUE id_programare`) |
| Editare consultație | `/consultatii/<id>/editare` | **U** | `UPDATE consultatii SET ...` |
| Rețetă nouă | `/consultatii/<id>/retete/nou` | **C** | rețeta și cele maximum 5 medicamente ale ei se salvează într-o **singură tranzacție**. ID-ul rețetei noi vine din `currval(pg_get_serial_sequence(...))`. Dacă o linie e greșită (de exemplu, același medicament de două ori), se face ROLLBACK și nu se salvează nimic. |
| Editare rețetă | `/consultatii/retete/<id>/editare` | **U** | în aceeași tranzacție: `UPDATE` rețetă + `DELETE` liniile vechi + `INSERT` liniile noi |
| Ștergere | butoane | **D** | rețeta: CASCADE spre `retete_medicamente`; consultația: CASCADE spre rețete |

### Utilizatori (doar admin) — `auth.py`

| Pagina | URL | Operație | Observații |
|---|---|---|---|
| Lista conturilor | `/utilizatori` | **R** | filtru după email și rol; arată persoana asociată și ultima autentificare |
| Cont nou | `/utilizatori/nou` | **C** | un singur `WITH ... INSERT ... UPDATE` (CTE) creează contul și îl leagă de medic/pacient, atomic |
| Editare cont | `/utilizatori/<id>/editare` | **U** | schimbă emailul, rolul, starea (activ/inactiv) și, opțional, parola |
| Ștergere cont | buton | **D** | persoana (medic/pacient) rămâne în baza de date, pentru că FK-ul are **ON DELETE SET NULL** |

### Alte pagini

| Pagina | URL | Descriere |
|---|---|---|
| Pagina principală | `/` | arată altceva în funcție de rol: statistici și următoarele programări (admin/recepție), agenda zilei (medic), programările viitoare (pacient) |
| Autentificare | `/login` | formularul de login |
| Schimbare parolă | `/cont/parola` | orice utilizator își poate schimba parola |

## Elemente de baze de date folosite în aplicație

- **JOIN-uri** pe 3–5 tabele (programări + pacienți + medici + specializări + consultații).
- **Funcții de agregare**: `count(*) FILTER (WHERE ...)`, `GROUP BY`, funcția fereastră `count(*) OVER ()` (totalul pentru paginare, din aceeași interogare).
- **Tranzacții** cu mai multe instrucțiuni (rețete) și **CTE-uri care modifică date** (`WITH ... INSERT ... RETURNING`).
- **Constrângerile din etapa 1 sunt folosite efectiv**: CHECK, UNIQUE, FK cu CASCADE / RESTRICT / SET NULL. Le aplică baza de date, nu doar aplicația.
- Funcții de dată: `age()`, `date_part()`, aritmetică `date + int`.
