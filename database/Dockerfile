FROM postgres:17-alpine

# Raw source files (OMOP vocabulary + SÚKL DLP). They are only read once by the
# init scripts on first start; the loaded result lives in the data volume.
COPY data/CONCEPT.csv data/CONCEPT_RELATIONSHIP.csv data/dlp_lecivepripravky.csv /vocab/

# Scripts here run once, in lexical order, when the data directory is empty.
COPY init/ /docker-entrypoint-initdb.d/
