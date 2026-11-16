-- =====================================================================
--  Etapa 3: AUTENTIFICARE — parole + roluri
--  Se rulează DUPĂ 01_schema.sql și 02_seed.sql.
--  Rulare:  psql -d clinica -f sql/03_autentificare.sql
-- =====================================================================
SET search_path TO clinica, public;

-- pgcrypto oferă crypt() + gen_salt('bf') = hash bcrypt calculat în PostgreSQL
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

-- 1. Coloane noi pe utilizatori
ALTER TABLE utilizatori
    ADD COLUMN IF NOT EXISTS parola_hash          VARCHAR(100),
    ADD COLUMN IF NOT EXISTS ultima_autentificare TIMESTAMP;

-- 2. Parolă demo pentru toate conturile existente: Parola123!
--    (bcrypt cu salt aleator, cost 8 — fiecare hash e diferit)
UPDATE utilizatori
SET    parola_hash = crypt('Parola123!', gen_salt('bf', 8))
WHERE  parola_hash IS NULL;

ALTER TABLE utilizatori ALTER COLUMN parola_hash SET NOT NULL;

-- 3. Hash-ul trebuie să fie bcrypt (începe cu $2a$ / $2b$), niciodată text simplu
ALTER TABLE utilizatori DROP CONSTRAINT IF EXISTS chk_utilizator_parola_bcrypt;
ALTER TABLE utilizatori
    ADD CONSTRAINT chk_utilizator_parola_bcrypt CHECK (parola_hash ~ '^\$2[aby]\$');

-- 4. Funcție de autentificare: primește email + parolă, întoarce contul
--    (sau nimic dacă datele sunt greșite / contul e dezactivat).
--    Parola e verificată în baza de date; aplicația nu vede niciodată hash-ul.
CREATE OR REPLACE FUNCTION autentifica(p_email TEXT, p_parola TEXT)
RETURNS TABLE (
    id_utilizator INT,
    email         VARCHAR,
    rol           VARCHAR,
    id_medic      INT,
    id_pacient    INT,
    nume_afisat   TEXT
)
LANGUAGE sql
STABLE
SET search_path = clinica, public
AS $$
    SELECT u.id_utilizator,
           u.email,
           r.denumire,
           m.id_medic,
           p.id_pacient,
           COALESCE(m.prenume || ' ' || m.nume,
                    p.prenume || ' ' || p.nume,
                    u.email)
    FROM utilizatori u
    JOIN roluri r       ON r.id_rol = u.id_rol
    LEFT JOIN medici m  ON m.id_utilizator = u.id_utilizator
    LEFT JOIN pacienti p ON p.id_utilizator = u.id_utilizator
    WHERE lower(u.email) = lower(p_email)
      AND u.activ
      AND u.parola_hash = crypt(p_parola, u.parola_hash);
$$;
