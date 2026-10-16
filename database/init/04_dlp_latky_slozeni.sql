CREATE TABLE dlp_latky (
    kod_latky text PRIMARY KEY,
    zdroj     text,
    nazev_inn text,
    nazev_en  text,
    nazev     text,
    zav       text,
    dop       text,
    narvla    text
);

CREATE TABLE dlp_slozeni (
    kod_sukl  text,
    kod_latky text,
    sq        text,
    s         text,
    amnt_od   text,
    amnt      text,
    un        text
);

COPY dlp_latky FROM '/vocab/dlp_latky.csv'
    WITH (FORMAT csv, DELIMITER ';', HEADER true, ENCODING 'WIN1250');

COPY dlp_slozeni FROM '/vocab/dlp_slozeni.csv'
    WITH (FORMAT csv, DELIMITER ';', HEADER true, ENCODING 'WIN1250');

CREATE INDEX idx_dlp_slozeni_kod_sukl ON dlp_slozeni (kod_sukl);
CREATE INDEX idx_dlp_slozeni_kod_latky ON dlp_slozeni (kod_latky);

ANALYZE dlp_latky;
ANALYZE dlp_slozeni;
