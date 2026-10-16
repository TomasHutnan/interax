CREATE INDEX idx_dlp_lecivepripravky_nazev_trgm
    ON dlp_lecivepripravky USING gist (lower(nazev) gist_trgm_ops);

CREATE VIEW medication_substances AS
SELECT p.kod_sukl,
       p.nazev,
       p.sila,
       p.forma,
       s.sq,
       s.s,
       l.kod_latky,
       COALESCE(NULLIF(l.nazev_en, ''), NULLIF(l.nazev_inn, ''), l.nazev) AS substance_name_en,
       s.amnt,
       s.un
FROM dlp_lecivepripravky p
JOIN dlp_slozeni s ON s.kod_sukl = p.kod_sukl
JOIN dlp_latky l   ON l.kod_latky = s.kod_latky;

CREATE FUNCTION match_medication_substances(p_query text, p_min_score real DEFAULT 0.2)
RETURNS TABLE (
    kod_sukl          text,
    nazev             text,
    sila              text,
    forma             text,
    match_score       real,
    s                 text,
    kod_latky         text,
    substance_name_en text,
    amnt              text,
    un                text
)
LANGUAGE sql STABLE
AS $$
    WITH best AS (
        SELECT p.kod_sukl,
               similarity(lower(p.nazev), lower(p_query)) AS match_score
        FROM dlp_lecivepripravky p
        WHERE p.nazev IS NOT NULL
          AND lower(p.nazev) <-> lower(p_query) <= 1 - p_min_score
        ORDER BY lower(p.nazev) <-> lower(p_query),
                 lower(concat_ws(' ', p.nazev, p.sila)) <-> lower(p_query),
                 p.kod_sukl
        LIMIT 1
    )
    SELECT ms.kod_sukl,
           ms.nazev,
           ms.sila,
           ms.forma,
           best.match_score,
           ms.s,
           ms.kod_latky,
           ms.substance_name_en,
           ms.amnt,
           ms.un
    FROM best
    JOIN medication_substances ms ON ms.kod_sukl = best.kod_sukl
    ORDER BY ms.substance_name_en;
$$;
