"""Connectivity and schema check for InterSystems IRIS SQL and FHIR R4."""

import sys

import iris
import requests
from requests.auth import HTTPBasicAuth

import config


def get_iris_connection():
    """Return a DB-API connection to InterSystems IRIS."""
    conn_str = f"{config.IRIS_HOST}:{config.IRIS_PORT}/{config.IRIS_NAMESPACE}"
    return iris.connect(conn_str, config.IRIS_USER, config.IRIS_PASSWORD)


def discover_fhir_endpoint() -> str:
    """Probe candidate FHIR R4 endpoints on IRIS and return the active base URL."""
    auth = HTTPBasicAuth(config.IRIS_USER, config.IRIS_PASSWORD)
    headers = {"Accept": "application/fhir+json"}
    for base_url in config.IRIS_FHIR_CANDIDATES:
        try:
            resp = requests.get(
                f"{base_url}/metadata", auth=auth, headers=headers, timeout=10
            )
            if resp.status_code == 200 and "CapabilityStatement" in resp.text:
                return base_url
        except Exception:
            pass
    # Fallback to first candidate if metadata probe differs
    return config.IRIS_FHIR_CANDIDATES[0]


def setup_schemas(conn, drop_existing: bool = False):
    """Create ClinicalData and ClinicalKnowledge tables in InterSystems IRIS."""
    cursor = conn.cursor()

    tables = [
        (
            "ClinicalData.SuklRegistry",
            """
            CREATE TABLE ClinicalData.SuklRegistry (
                SuklCode VARCHAR(7) PRIMARY KEY,
                BrandName VARCHAR(255),
                ActiveSubstance VARCHAR(255),
                SubstanceCzech VARCHAR(255),
                Strength VARCHAR(100),
                Form VARCHAR(100),
                AtcCode VARCHAR(10),
                AtcName VARCHAR(255)
            )
        """,
        ),
        (
            "ClinicalData.Interactions",
            """
            CREATE TABLE ClinicalData.Interactions (
                ID INT PRIMARY KEY IDENTITY,
                SubstanceA VARCHAR(255),
                SubstanceB VARCHAR(255),
                RiskLevel VARCHAR(50),
                MechanismText VARCHAR(1024)
            )
        """,
        ),
        (
            "ClinicalKnowledge.CpicVectors",
            """
            CREATE TABLE ClinicalKnowledge.CpicVectors (
                ID INT PRIMARY KEY IDENTITY,
                SubstanceName VARCHAR(100),
                SourceFile VARCHAR(100),
                ChunkContent VARCHAR(2048),
                Embedding VECTOR(DOUBLE, 384)
            )
        """,
        ),
    ]

    for table_name, ddl in tables:
        if drop_existing:
            try:
                cursor.execute(f"DROP TABLE {table_name}")
                conn.commit()
                print(f"  Dropped existing table {table_name}")
            except Exception:
                pass
        try:
            cursor.execute(ddl)
            conn.commit()
            print(f"  Created table {table_name}")
        except Exception as e:
            if "already exists" in str(e).lower() or "sqlcode: -201" in str(e).lower():
                print(f"  Table {table_name} already exists")
            else:
                raise

    # Create helpful indexes for fast lookup
    indexes = [
        "CREATE INDEX idx_sukl_brand ON ClinicalData.SuklRegistry (BrandName)",
        "CREATE INDEX idx_sukl_substance ON ClinicalData.SuklRegistry (ActiveSubstance)",
        "CREATE INDEX idx_ddi_subA ON ClinicalData.Interactions (SubstanceA)",
        "CREATE INDEX idx_ddi_subB ON ClinicalData.Interactions (SubstanceB)",
        "CREATE INDEX idx_cpic_substance ON ClinicalKnowledge.CpicVectors (SubstanceName)",
    ]
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
            conn.commit()
        except Exception:
            pass

    cursor.close()


if __name__ == "__main__":
    print(
        f"1. Testing IRIS SQL connection to {config.IRIS_HOST}:{config.IRIS_PORT}/{config.IRIS_NAMESPACE}..."
    )
    conn = get_iris_connection()
    cur = conn.cursor()
    cur.execute("SELECT $ZVERSION")
    version = cur.fetchone()[0]
    print(f"   Connected! IRIS Version: {version}")

    print("2. Setting up IRIS schemas...")
    drop = "--drop" in sys.argv
    setup_schemas(conn, drop_existing=drop)

    print("3. Probing FHIR R4 endpoint...")
    fhir_url = discover_fhir_endpoint()
    print(f"   Active FHIR R4 endpoint: {fhir_url}")
    conn.close()
