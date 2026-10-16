CREATE TABLE dlp_lecivepripravky (
    kod_sukl                 text PRIMARY KEY,
    h                        text,
    nazev                    text,
    sila                     text,
    forma                    text,
    baleni                   text,
    cesta                    text,
    doplnek                  text,
    obal                     text,
    drz                      text,
    zemdrz                   text,
    akt_drz                  text,
    akt_zem                  text,
    reg                      text,
    v_platdo                 text,
    neomez                   text,
    uvadenido                text,
    is_                      text,
    atc_who                  text,
    rc                       text,
    sdov                     text,
    sdov_dod                 text,
    sdov_zem                 text,
    reg_proc                 text,
    dddamnt_who              text,
    dddun_who                text,
    dddp_who                 text,
    zdroj_who                text,
    ll                       text,
    vydej                    text,
    zav                      text,
    doping                   text,
    narvla                   text,
    dodavky                  text,
    ean                      text,
    braillovo_pismo          text,
    exp                      text,
    exp_t                    text,
    nazev_reg                text,
    mrp_cislo                text,
    pravni_zaklad_registrace text,
    ochranny_prvek           text,
    omezeni_preskripce_smp   text,
    typ_lp                   text
);

COPY dlp_lecivepripravky FROM '/vocab/dlp_lecivepripravky.csv'
    WITH (FORMAT csv, DELIMITER ';', HEADER true, ENCODING 'WIN1250');

CREATE INDEX idx_dlp_lecivepripravky_atc_who ON dlp_lecivepripravky (atc_who);

ANALYZE dlp_lecivepripravky;
