FROM postgres:17-alpine

COPY data/CONCEPT.csv data/CONCEPT_RELATIONSHIP.csv \
    data/dlp_lecivepripravky.csv data/dlp_latky.csv data/dlp_slozeni.csv \
    /vocab/

COPY init/ /docker-entrypoint-initdb.d/
