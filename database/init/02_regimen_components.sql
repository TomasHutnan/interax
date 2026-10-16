CREATE FUNCTION regimen_components(p_regimen_id integer)
RETURNS TABLE (
    concept_id   integer,
    concept_name varchar(255),
    concept_code varchar(50)
)
LANGUAGE sql STABLE
AS $$
    SELECT drug.concept_id,
           drug.concept_name,
           drug.concept_code
    FROM concept regimen
    JOIN concept_relationship rel ON rel.concept_id_1 = regimen.concept_id
    JOIN concept drug ON drug.concept_id = rel.concept_id_2
    WHERE regimen.concept_id = p_regimen_id
      AND regimen.domain_id = 'Regimen'
      AND regimen.concept_class_id = 'Regimen'
      AND drug.domain_id = 'Drug'
      AND drug.concept_class_id = 'Component'
      AND rel.invalid_reason IS NULL
      AND rel.relationship_id = 'Has cytotoxic chemo'
    GROUP BY drug.concept_id, drug.concept_name, drug.concept_code
    ORDER BY drug.concept_name;
$$;
