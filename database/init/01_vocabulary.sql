CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TEMP TABLE stg_concept (
    concept_id       integer,
    concept_name     text,
    domain_id        text,
    vocabulary_id    text,
    concept_class_id text,
    standard_concept text,
    concept_code     text,
    valid_start_date text,
    valid_end_date   text,
    invalid_reason   text
);

CREATE TEMP TABLE stg_concept_relationship (
    concept_id_1     integer,
    concept_id_2     integer,
    relationship_id  text,
    valid_start_date text,
    valid_end_date   text,
    invalid_reason   text
);

COPY stg_concept FROM '/vocab/CONCEPT.csv'
    WITH (FORMAT text, DELIMITER E'\t', HEADER true, NULL '');

COPY stg_concept_relationship FROM '/vocab/CONCEPT_RELATIONSHIP.csv'
    WITH (FORMAT text, DELIMITER E'\t', HEADER true, NULL '');

CREATE TABLE concept (
    concept_id       integer      PRIMARY KEY,
    concept_name     varchar(255) NOT NULL,
    domain_id        varchar(20)  NOT NULL,
    vocabulary_id    varchar(20)  NOT NULL,
    concept_class_id varchar(20)  NOT NULL,
    standard_concept varchar(1),
    concept_code     varchar(50)  NOT NULL,
    valid_start_date date         NOT NULL,
    valid_end_date   date         NOT NULL,
    invalid_reason   varchar(1)
);

CREATE TABLE concept_relationship (
    concept_id_1     integer     NOT NULL REFERENCES concept (concept_id),
    concept_id_2     integer     NOT NULL REFERENCES concept (concept_id),
    relationship_id  varchar(20) NOT NULL,
    valid_start_date date        NOT NULL,
    valid_end_date   date        NOT NULL,
    invalid_reason   varchar(1),
    PRIMARY KEY (concept_id_1, concept_id_2, relationship_id)
);

INSERT INTO concept
SELECT concept_id,
       concept_name,
       domain_id,
       vocabulary_id,
       concept_class_id,
       standard_concept,
       concept_code,
       to_date(valid_start_date, 'YYYYMMDD'),
       to_date(valid_end_date, 'YYYYMMDD'),
       invalid_reason
FROM stg_concept
WHERE domain_id IN ('Drug', 'Regimen');

INSERT INTO concept_relationship
SELECT r.concept_id_1,
       r.concept_id_2,
       r.relationship_id,
       to_date(r.valid_start_date, 'YYYYMMDD'),
       to_date(r.valid_end_date, 'YYYYMMDD'),
       r.invalid_reason
FROM stg_concept_relationship r
WHERE EXISTS (SELECT 1 FROM concept c WHERE c.concept_id = r.concept_id_1)
  AND EXISTS (SELECT 1 FROM concept c WHERE c.concept_id = r.concept_id_2);

DROP TABLE stg_concept;
DROP TABLE stg_concept_relationship;

CREATE INDEX idx_concept_domain_id ON concept (domain_id);
CREATE INDEX idx_concept_concept_code ON concept (concept_code);
CREATE INDEX idx_concept_name_trgm ON concept USING gin (lower(concept_name) gin_trgm_ops);
CREATE INDEX idx_concept_relationship_id_2 ON concept_relationship (concept_id_2);
CREATE INDEX idx_concept_relationship_relationship_id ON concept_relationship (relationship_id);

ANALYZE concept;
ANALYZE concept_relationship;
