# Etapa 3 — Autentificare și roluri

**Cerință:** autentificare, minimum 3 roluri.
**Realizat:** autentificare cu email și parolă, **4 roluri** cu drepturi diferite, parole stocate ca hash **bcrypt** și verificate direct în PostgreSQL.

## Modificări în baza de date — `sql/03_autentificare.sql`

| Element | Ce face |
|---|---|
| `CREATE EXTENSION pgcrypto` | aduce funcțiile `crypt()` și `gen_salt('bf')`, adică bcrypt calculat în PostgreSQL |
| `utilizatori.parola_hash` | hash-ul parolei; nu se stochează niciodată parola în clar |
| `utilizatori.ultima_autentificare` | data și ora ultimului login reușit |
| `CHECK chk_utilizator_parola_bcrypt` | baza de date refuză orice valoare care nu e un hash bcrypt (`$2a$...`) |
| Funcția `autentifica(email, parola)` | primește emailul și parola și întoarce contul cu rolul lui (sau 0 rânduri). Comparația `parola_hash = crypt(parola, parola_hash)` se face **în baza de date**, deci aplicația nu citește niciodată hash-ul |

Parola demo pentru toate conturile din datele de test este `Parola123!`. Fiecare cont are totuși alt hash, pentru că bcrypt folosește un salt aleator.

## Rolurile și drepturile lor

| Funcționalitate | admin | receptioner | medic | pacient |
|---|:-:|:-:|:-:|:-:|
| Pacienți — listă / fișă | toți | toți | doar pacienții lui | doar propria fișă |
| Pacienți — adăugare / editare / ștergere | ✔ | ✔ | ✘ | ✘ |
| Medici — listă | ✔ | ✔ | ✔ | ✔ |
| Medici — adăugare / editare / ștergere | ✔ | ✘ | ✘ | ✘ |
| Specializări / Medicamente — modificare | ✔ | ✘ | ✘ | ✘ |
| Medicamente — listă | ✔ | ✔ | ✔ | ✘ |
| Programări — listă | toate | toate | doar ale lui | doar ale lui |
| Programare nouă | pentru oricine | pentru oricine | ✘ | doar pentru el |
| Programări — editare / ștergere | ✔ | ✔ | ✘ | ✘ |
| Finalizare programare | ✔ | ✔ | doar ale lui | ✘ |
| Anulare programare | ✔ | ✔ | doar ale lui | doar ale lui, viitoare |
| Consultații și rețete — citire | toate | **✘ (date medicale)** | doar ale lui | doar ale lui |
| Consultații și rețete — scriere | ✔ | ✘ | doar ale lui | ✘ |
| Gestionare conturi (Utilizatori) | ✔ | ✘ | ✘ | ✘ |

Recepția nu vede diagnosticele și rețetele. Asta e o decizie de confidențialitate: recepția gestionează doar partea administrativă.

## Cum funcționează

1. **Login** (`POST /login`): aplicația rulează `SELECT * FROM autentifica(%s, %s)`.
   - Dacă primește un rând, salvează în sesiune `id_utilizator`, `rol`, `id_medic`/`id_pacient` și actualizează `ultima_autentificare`.
   - Dacă nu primește nimic, răspunde cu codul 401 și mesajul „Email sau parolă greșită”. Nu spune care dintre cele două e greșit.
2. **Verificarea pe fiecare pagină** se face cu doi decoratori din `auth.py`:
   - `@login_required`: dacă nu ești logat, te trimite la `/login`;
   - `@role_required('admin', 'receptioner')`: dacă rolul tău nu e în listă, primești **403 – Nu ai drepturi**.
3. **Filtrarea datelor după rol** se face direct în SQL, nu doar prin ascunderea butoanelor. Exemple:
   - un medic care cere `/programari/?medic=2` vede tot programările lui; filtrul trimis este ignorat;
   - un pacient care trimite `id_pacient` al altcuiva în formular își face tot o programare pentru el;
   - accesul la fișa altui pacient sau la o consultație străină întoarce 403.
4. **Logout** (`POST /logout`) golește sesiunea.

## Măsuri de securitate

- Parolele sunt bcrypt cu salt aleator (`gen_salt('bf', 8)`). Hash-ul nu iese niciodată din baza de date.
- Toate interogările sunt parametrizate, deci aplicația e protejată de SQL injection.
- Cookie-ul de sesiune e semnat cu `SECRET_KEY` și marcat `HttpOnly` și `SameSite=Lax`.
- Acțiunile care modifică date (ștergeri, schimbări de status, logout) sunt doar **POST**, niciodată simple link-uri.
- Un cont dezactivat (`activ = false`) nu se mai poate loga.
- Adminul nu își poate șterge propriul cont, nu se poate dezactiva și nu își poate scoate rolul de admin.
- Parolele noi trebuie să aibă minimum 8 caractere. Ca să-ți schimbi parola, trebuie să o introduci și pe cea veche.

## Conturi demo

| Rol | Email | Parolă |
|---|---|---|
| admin | `admin@clinica.ro` | `Parola123!` |
| receptioner | `receptie1@clinica.ro` | `Parola123!` |
| medic | `dr.adrian.ionescu@clinica.ro` (sau oricare alt `dr....@clinica.ro`) | `Parola123!` |
| pacient | `radu.dragomir1@exemplu.ro` (sau oricare cont cu rolul „pacient”) | `Parola123!` |
