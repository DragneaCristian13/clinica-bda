-- =====================================================================
--  Proiect BDA — Aplicație de management pentru o clinică medicală
--  Etapa 1: MODELARE — schema bazei de date (PostgreSQL 14+)
-- =====================================================================
--  Rulare:  psql -U postgres -d clinica -f 01_schema.sql
-- =====================================================================

DROP SCHEMA IF EXISTS clinica CASCADE;
CREATE SCHEMA clinica;
SET search_path TO clinica;

-- ---------------------------------------------------------------------
--  Tipuri enumerate
-- ---------------------------------------------------------------------
CREATE TYPE status_programare AS ENUM ('programat', 'anulat', 'finalizat');
CREATE TYPE sex_pacient       AS ENUM ('M', 'F');

-- ---------------------------------------------------------------------
--  1. ROLURI  — pregătit pentru etapa 3 (autentificare, min. 3 roluri)
-- ---------------------------------------------------------------------
CREATE TABLE roluri (
    id_rol      SMALLSERIAL PRIMARY KEY,
    denumire    VARCHAR(30) NOT NULL UNIQUE,
    descriere   VARCHAR(255)
);

-- ---------------------------------------------------------------------
--  2. UTILIZATORI — conturile aplicației (parola se adaugă în etapa 3)
-- ---------------------------------------------------------------------
CREATE TABLE utilizatori (
    id_utilizator   SERIAL PRIMARY KEY,
    email           VARCHAR(120) NOT NULL UNIQUE,
    id_rol          SMALLINT     NOT NULL REFERENCES roluri(id_rol) ON DELETE RESTRICT,
    activ           BOOLEAN      NOT NULL DEFAULT TRUE,
    creat_la        TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_utilizator_email CHECK (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$')
);

-- ---------------------------------------------------------------------
--  3. SPECIALIZARI — nomenclator (evită text repetat în Medici)
-- ---------------------------------------------------------------------
CREATE TABLE specializari (
    id_specializare SMALLSERIAL PRIMARY KEY,
    denumire        VARCHAR(80) NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------
--  4. MEDICI
-- ---------------------------------------------------------------------
CREATE TABLE medici (
    id_medic        SERIAL PRIMARY KEY,
    id_utilizator   INT UNIQUE REFERENCES utilizatori(id_utilizator) ON DELETE SET NULL,
    nume            VARCHAR(50)  NOT NULL,
    prenume         VARCHAR(50)  NOT NULL,
    id_specializare SMALLINT     NOT NULL REFERENCES specializari(id_specializare) ON DELETE RESTRICT,
    cod_parafa      CHAR(6)      NOT NULL UNIQUE,
    telefon         VARCHAR(15),
    email           VARCHAR(120) NOT NULL UNIQUE,
    CONSTRAINT chk_medic_parafa  CHECK (cod_parafa ~ '^[A-Z0-9]{6}$'),
    CONSTRAINT chk_medic_telefon CHECK (telefon IS NULL OR telefon ~ '^\+?[0-9]{9,14}$')
);

-- ---------------------------------------------------------------------
--  5. PACIENTI
-- ---------------------------------------------------------------------
CREATE TABLE pacienti (
    id_pacient      SERIAL PRIMARY KEY,
    id_utilizator   INT UNIQUE REFERENCES utilizatori(id_utilizator) ON DELETE SET NULL,
    nume            VARCHAR(50)  NOT NULL,
    prenume         VARCHAR(50)  NOT NULL,
    cnp             CHAR(13)     NOT NULL UNIQUE,
    data_nasterii   DATE         NOT NULL,
    sex             sex_pacient  NOT NULL,
    telefon         VARCHAR(15),
    email           VARCHAR(120),
    adresa          VARCHAR(255),
    creat_la        TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_pacient_cnp     CHECK (cnp ~ '^[1-8][0-9]{12}$'),
    CONSTRAINT chk_pacient_nastere CHECK (data_nasterii BETWEEN DATE '1900-01-01' AND CURRENT_DATE),
    CONSTRAINT chk_pacient_telefon CHECK (telefon IS NULL OR telefon ~ '^\+?[0-9]{9,14}$')
);

-- ---------------------------------------------------------------------
--  6. PROGRAMARI  (Pacient N:M Medic, prin programări)
-- ---------------------------------------------------------------------
CREATE TABLE programari (
    id_programare   SERIAL PRIMARY KEY,
    id_pacient      INT        NOT NULL REFERENCES pacienti(id_pacient) ON DELETE CASCADE,
    id_medic        INT        NOT NULL REFERENCES medici(id_medic)     ON DELETE RESTRICT,
    data_ora        TIMESTAMP  NOT NULL,
    durata_minute   SMALLINT   NOT NULL DEFAULT 30,
    motiv           VARCHAR(255),
    status          status_programare NOT NULL DEFAULT 'programat',
    creat_la        TIMESTAMP  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_programare_durata CHECK (durata_minute BETWEEN 10 AND 180),
    -- un medic nu poate avea două programări care încep la aceeași oră
    CONSTRAINT uq_programare_medic_ora UNIQUE (id_medic, data_ora)
);

-- ---------------------------------------------------------------------
--  7. CONSULTATII  (1:1 cu Programari — o consultație per programare)
-- ---------------------------------------------------------------------
CREATE TABLE consultatii (
    id_consultatie  SERIAL PRIMARY KEY,
    id_programare   INT  NOT NULL UNIQUE REFERENCES programari(id_programare) ON DELETE CASCADE,
    simptome        TEXT,
    diagnostic      TEXT,
    recomandari     TEXT,
    creat_la        TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------
--  8. MEDICAMENTE — nomenclator
-- ---------------------------------------------------------------------
CREATE TABLE medicamente (
    id_medicament    SERIAL PRIMARY KEY,
    denumire         VARCHAR(100) NOT NULL,
    substanta_activa VARCHAR(100) NOT NULL,
    forma            VARCHAR(40)  NOT NULL,   -- comprimate, sirop, unguent...
    concentratie     VARCHAR(40)  NOT NULL,   -- 500 mg, 5 mg/ml...
    CONSTRAINT uq_medicament UNIQUE (denumire, forma, concentratie)
);

-- ---------------------------------------------------------------------
--  9. RETETE  (Consultatie 1:N Retete)
-- ---------------------------------------------------------------------
CREATE TABLE retete (
    id_reteta         SERIAL PRIMARY KEY,
    id_consultatie    INT      NOT NULL REFERENCES consultatii(id_consultatie) ON DELETE CASCADE,
    data_emiterii     DATE     NOT NULL DEFAULT CURRENT_DATE,
    valabilitate_zile SMALLINT NOT NULL DEFAULT 30,
    CONSTRAINT chk_reteta_valabilitate CHECK (valabilitate_zile BETWEEN 1 AND 365)
);

-- ---------------------------------------------------------------------
-- 10. RETETE_MEDICAMENTE — tabel asociativ (Retete N:M Medicamente)
-- ---------------------------------------------------------------------
CREATE TABLE retete_medicamente (
    id_reteta       INT          NOT NULL REFERENCES retete(id_reteta)           ON DELETE CASCADE,
    id_medicament   INT          NOT NULL REFERENCES medicamente(id_medicament)  ON DELETE RESTRICT,
    doza            VARCHAR(50)  NOT NULL,   -- ex: "1 comprimat"
    frecventa       VARCHAR(50)  NOT NULL,   -- ex: "de 3 ori pe zi"
    durata_zile     SMALLINT     NOT NULL,
    cantitate       SMALLINT     NOT NULL DEFAULT 1,  -- nr. cutii
    PRIMARY KEY (id_reteta, id_medicament),
    CONSTRAINT chk_rm_durata    CHECK (durata_zile BETWEEN 1 AND 365),
    CONSTRAINT chk_rm_cantitate CHECK (cantitate > 0)
);

-- Indecșii (de performanță) se adaugă în etapa 4.

-- Comoditate: tabelele se găsesc fără prefixul clinica.
ALTER DATABASE clinica SET search_path TO clinica, public;
