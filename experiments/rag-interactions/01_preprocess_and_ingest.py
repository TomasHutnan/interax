"""Phase 1 & 2: Pre-process SÚKL, WHO ATC, DDInter, and CPIC datasets and ingest into InterSystems IRIS."""

import glob
import re
import time
from pathlib import Path

import iris
import openpyxl
import pandas as pd
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

import config

# Known clinical pathway annotations for major oncology/pharmacogenomic DDInter pairs
PATHWAY_ENRICHMENT = {
    (
        "tamoxifen",
        "paroxetine",
    ): "Strong CYP2D6 inhibition by paroxetine blocks metabolic bioactivation of tamoxifen to active endoxifen, increasing breast cancer recurrence risk.",
    (
        "tamoxifen",
        "fluoxetine",
    ): "Strong CYP2D6 inhibition by fluoxetine impairs conversion of tamoxifen to its active metabolite endoxifen.",
    (
        "tamoxifen",
        "bupropion",
    ): "Strong CYP2D6 inhibition reduces plasma concentrations of active tamoxifen metabolite endoxifen.",
    (
        "capecitabine",
        "brivudine",
    ): "Irreversible inhibition of dihydropyrimidine dehydrogenase (DPYD) by brivudine causes potentially fatal fluoropyrimidine toxicity.",
    (
        "fluorouracil",
        "brivudine",
    ): "Irreversible DPYD inhibition by brivudine blocks fluorouracil catabolism, leading to severe, potentially fatal toxicity.",
    (
        "fluorouracil",
        "sorivudine",
    ): "Irreversible inhibition of dihydropyrimidine dehydrogenase (DPYD) leads to severe fluoropyrimidine toxicity.",
    (
        "mercaptopurine",
        "allopurinol",
    ): "Xanthine oxidase inhibition by allopurinol impairs mercaptopurine first-pass metabolism (compounding TPMT/NUDT15 myelosuppression risk).",
    (
        "azathioprine",
        "allopurinol",
    ): "Xanthine oxidase inhibition significantly increases 6-MP active thioguanine nucleotides, causing severe myelosuppression.",
    (
        "simvastatin",
        "clarithromycin",
    ): "Strong CYP3A4 and OATP1B1 (SLCO1B1) inhibition markedly increases simvastatin exposure and risk of rhabdomyolysis.",
    (
        "simvastatin",
        "itraconazole",
    ): "Potent CYP3A4 inhibition increases statin plasma levels and risk of severe myopathy/rhabdomyolysis.",
    (
        "atorvastatin",
        "clarithromycin",
    ): "CYP3A4 and SLCO1B1 (OATP1B1) transporter inhibition elevates atorvastatin concentrations and myopathy risk.",
    (
        "atorvastatin",
        "cyclosporine",
    ): "SLCO1B1 (OATP1B1) and CYP3A4 inhibition markedly increases statin exposure and rhabdomyolysis risk.",
    (
        "ondansetron",
        "apomorphine",
    ): "Severe hypotension and loss of consciousness; ondansetron also subject to CYP2D6 ultrarapid metabolizer failure.",
    (
        "ondansetron",
        "tramadol",
    ): "Pharmacodynamic antagonism and shared CYP2D6 metabolic pathway reduces tramadol analgesic efficacy and increases serotonin risk.",
    (
        "atazanavir",
        "rifampicin",
    ): "Strong metabolic induction reduces atazanavir plasma concentrations; UGT1A1 poor metabolizers face hyperbilirubinemia risk.",
    (
        "atazanavir",
        "omeprazole",
    ): "Gastric pH elevation markedly decreases atazanavir solubility and absorption.",
}

# Crucial oncology pairs to ensure exist in ClinicalData.Interactions even if absent in raw CSV subset
EXTRA_CRITICAL_INTERACTIONS = [
    (
        "Tamoxifen",
        "Paroxetine",
        "Major",
        PATHWAY_ENRICHMENT[("tamoxifen", "paroxetine")],
    ),
    (
        "Tamoxifen",
        "Fluoxetine",
        "Major",
        PATHWAY_ENRICHMENT[("tamoxifen", "fluoxetine")],
    ),
    ("Tamoxifen", "Bupropion", "Major", PATHWAY_ENRICHMENT[("tamoxifen", "bupropion")]),
    (
        "Capecitabine",
        "Brivudine",
        "Major",
        PATHWAY_ENRICHMENT[("capecitabine", "brivudine")],
    ),
    (
        "Fluorouracil",
        "Brivudine",
        "Major",
        PATHWAY_ENRICHMENT[("fluorouracil", "brivudine")],
    ),
    (
        "Mercaptopurine",
        "Allopurinol",
        "Major",
        PATHWAY_ENRICHMENT[("mercaptopurine", "allopurinol")],
    ),
    (
        "Azathioprine",
        "Allopurinol",
        "Major",
        PATHWAY_ENRICHMENT[("azathioprine", "allopurinol")],
    ),
    (
        "Simvastatin",
        "Clarithromycin",
        "Major",
        PATHWAY_ENRICHMENT[("simvastatin", "clarithromycin")],
    ),
    (
        "Atorvastatin",
        "Cyclosporine",
        "Major",
        PATHWAY_ENRICHMENT[("atorvastatin", "cyclosporine")],
    ),
    (
        "Ondansetron",
        "Apomorphine",
        "Major",
        PATHWAY_ENRICHMENT[("ondansetron", "apomorphine")],
    ),
]


def build_sukl_dataframe() -> pd.DataFrame:
    """Parse SÚKL DLP registry + WHO ATC into canonical rows for ClinicalData.SuklRegistry."""
    print("-> Parsing SÚKL DLP & WHO ATC CSVs...")
    lp_path = config.SUKL_DIR / "dlp_lecivepripravky.csv"
    slozeni_path = config.SUKL_DIR / "dlp_slozeni.csv"
    latky_path = config.SUKL_DIR / "dlp_latky.csv"
    atc_files = list(config.WHO_ATC_DIR.glob("WHO ATC-DDD *.csv"))

    df_lp = pd.read_csv(
        lp_path, sep=";", encoding="cp1250", dtype=str, low_memory=False
    )
    df_sloz = pd.read_csv(
        slozeni_path, sep=";", encoding="cp1250", dtype=str, low_memory=False
    )
    df_latky = pd.read_csv(
        latky_path, sep=";", encoding="cp1250", dtype=str, low_memory=False
    )

    # Filter dlp_slozeni to active ingredients ('L' or empty/primary)
    if "S" in df_sloz.columns:
        df_sloz_active = df_sloz[df_sloz["S"].fillna("L").isin(["L", ""])]
        if df_sloz_active.empty:
            df_sloz_active = df_sloz
    else:
        df_sloz_active = df_sloz

    # Resolve English INN name from dlp_latky
    df_latky["ActiveSubstance"] = (
        df_latky["NAZEV_EN"]
        .fillna(df_latky["NAZEV_INN"])
        .fillna(df_latky["NAZEV"])
        .str.strip()
        .str.title()
    )
    df_latky["SubstanceCzech"] = df_latky["NAZEV"].fillna("").str.strip()

    merged_sub = df_sloz_active.merge(
        df_latky[["KOD_LATKY", "ActiveSubstance", "SubstanceCzech"]],
        on="KOD_LATKY",
        how="left",
    )

    # Aggregate active substances per KOD_SUKL (take primary/first or join with '/')
    sub_per_sukl = merged_sub.groupby("KOD_SUKL", as_index=False).agg(
        ActiveSubstance=(
            "ActiveSubstance",
            lambda s: next((x for x in s if pd.notna(x) and x), ""),
        ),
        SubstanceCzech=(
            "SubstanceCzech",
            lambda s: next((x for x in s if pd.notna(x) and x), ""),
        ),
    )

    df_reg = df_lp.merge(sub_per_sukl, on="KOD_SUKL", how="left")

    # Map WHO ATC names
    atc_map = {}
    if atc_files:
        df_atc = pd.read_csv(atc_files[0], dtype=str)
        for _, r in df_atc.iterrows():
            code = str(r.get("atc_code", "")).strip()
            name = str(r.get("atc_name", "")).strip()
            if code:
                atc_map[code] = name

    out = pd.DataFrame(
        {
            "SuklCode": df_reg["KOD_SUKL"].fillna("").str.strip().str[:7],
            "BrandName": df_reg["NAZEV"].fillna("").str.strip().str[:255],
            "ActiveSubstance": df_reg["ActiveSubstance"]
            .fillna("")
            .str.strip()
            .str[:255],
            "SubstanceCzech": df_reg["SubstanceCzech"].fillna("").str.strip().str[:255],
            "Strength": df_reg["SILA"].fillna("").str.strip().str[:100],
            "Form": df_reg["FORMA"].fillna("").str.strip().str[:100],
            "AtcCode": df_reg["ATC_WHO"].fillna("").str.strip().str[:10],
        }
    )
    out["AtcName"] = out["AtcCode"].map(lambda c: atc_map.get(c, "")[:255])
    # Include historical/substance entry for Brivudine (ZOSTEVIR, KOD_LATKY 10629, ATC J05AB15) from dlp_latky/dlp_zruseneregistrace
    extra = pd.DataFrame(
        [
            {
                "SuklCode": "0010629",
                "BrandName": "ZOSTEVIR 125MG (BRIVUDIN)",
                "ActiveSubstance": "Brivudine",
                "SubstanceCzech": "BRIVUDIN",
                "Strength": "125MG",
                "Form": "TBL NOB",
                "AtcCode": "J05AB15",
                "AtcName": "brivudine",
            }
        ]
    )
    out = pd.concat([out, extra], ignore_index=True)
    out = out[out["SuklCode"] != ""].drop_duplicates(subset=["SuklCode"])
    print(f"   Prepared {len(out):,} SÚKL registry rows.")
    return out


def build_ddinter_dataframe() -> pd.DataFrame:
    """Concatenate DDInter CSVs, keeping all interaction severity levels, and enrich mechanism text."""
    print("-> Parsing DDInter CSVs (all severity levels)...")
    csv_files = sorted(config.DDINTER_DIR.glob("ddinter_downloads_code_*.csv"))
    dfs = [pd.read_csv(f, dtype=str) for f in csv_files]
    df_all = pd.concat(dfs, ignore_index=True)

    df_all["SubstanceA"] = df_all["Drug_A"].fillna("").str.strip()
    df_all["SubstanceB"] = df_all["Drug_B"].fillna("").str.strip()
    df_all["RiskLevel"] = df_all["Level"].fillna("Unknown").str.strip()

    # Canonical pair + severity deduplication (do not drop Moderate or Minor rows)
    seen = set()
    rows = []

    # First add enriched critical oncology interactions
    for sub_a, sub_b, level, mech in EXTRA_CRITICAL_INTERACTIONS:
        key = (tuple(sorted([sub_a.lower(), sub_b.lower()])), level.lower())
        seen.add(key)
        rows.append((sub_a, sub_b, level, mech))

    for _, r in df_all.iterrows():
        a = r["SubstanceA"]
        b = r["SubstanceB"]
        lvl = r["RiskLevel"]
        if not a or not b:
            continue
        al, bl = a.lower(), b.lower()
        key = (tuple(sorted([al, bl])), lvl.lower())
        if key in seen:
            continue
        seen.add(key)

        mech = (
            PATHWAY_ENRICHMENT.get((al, bl))
            or PATHWAY_ENRICHMENT.get((bl, al))
            or f"DDInter {lvl} Drug-Drug Interaction between {a} and {b}."
        )
        rows.append((a[:255], b[:255], lvl[:50], mech[:1024]))

    df_out = pd.DataFrame(
        rows, columns=["SubstanceA", "SubstanceB", "RiskLevel", "MechanismText"]
    )
    print(f"   Prepared {len(df_out):,} DDInter interaction rows (all severity levels).")
    return df_out


def infer_substance_from_path(file_path: Path) -> str:
    """Infer target active substance name from CPIC file or folder name."""
    fname = file_path.stem.lower()
    folder = file_path.parent.name.lower()

    known_substances = [
        "tamoxifen",
        "ondansetron",
        "tropisetron",
        "capecitabine",
        "fluorouracil",
        "azathioprine",
        "mercaptopurine",
        "thioguanine",
        "atazanavir",
        "atorvastatin",
        "simvastatin",
        "rosuvastatin",
        "pravastatin",
        "fluvastatin",
        "pitavastatin",
        "lovastatin",
    ]
    for s in known_substances:
        if s in fname:
            return s.title()
    for s in known_substances:
        if s in folder:
            return s.title()
    if "fluoropyrimidines" in folder:
        return "Capecitabine"
    if "thiopurines" in folder:
        return "Mercaptopurine"
    if "statins" in folder:
        return "Atorvastatin"
    return folder.split(" and ")[-1].strip().title()[:100]


def extract_cpic_chunks() -> list[dict]:
    """Extract natural language chunks from CPIC Excel tables and PDF guidelines."""
    print("-> Extracting CPIC Excel tables and PDF guideline chunks...")
    chunks: list[dict] = []

    # 1. Process all Excel (.xlsx) recommendation & alert tables
    xlsx_files = sorted(config.CPIC_DIR.glob("**/*.xlsx"))
    for xfile in xlsx_files:
        substance = infer_substance_from_path(xfile)
        rel_source = f"{xfile.parent.name}/{xfile.name}"[:100]
        try:
            wb = openpyxl.load_workbook(xfile, read_only=True, data_only=True)
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = list(ws.iter_rows(values_only=True))
                if not rows:
                    continue
                headers = [
                    str(h).strip() if h is not None else f"Col{i}"
                    for i, h in enumerate(rows[0])
                ]
                for row in rows[1:]:
                    pairs = []
                    for h, val in zip(headers, row):
                        if val is not None and str(val).strip() not in ("", "None"):
                            clean_val = re.sub(r"\s+", " ", str(val).strip())
                            pairs.append(f"{h}: {clean_val}")
                    if pairs:
                        text = (
                            f"Substance: {substance} | Source: {xfile.stem} | "
                            + " | ".join(pairs)
                        )
                        chunks.append(
                            {
                                "SubstanceName": substance[:100],
                                "SourceFile": rel_source,
                                "ChunkContent": text[:2000],
                            }
                        )
        except Exception as e:
            print(f"   Warning reading {xfile}: {e}")

    # 2. Process all PDF (publication.pdf & supplement.pdf) files into ~400-token (approx 1500-char) overlapping chunks
    pdf_files = sorted(config.CPIC_DIR.glob("**/*.pdf"))
    folder_substances = {
        "CYP2D6 and Tamoxifen": ["Tamoxifen"],
        "DPYD and Fluoropyrimidines": ["Capecitabine", "Fluorouracil"],
        "CYP2D6 and Ondansetron and Tropisetron": ["Ondansetron", "Tropisetron"],
        "TPMT, NUDT15 and Thiopurines": [
            "Mercaptopurine",
            "Azathioprine",
            "Thioguanine",
        ],
        "UGT1A1 and Atazanavir": ["Atazanavir"],
        "SLCO1B1, ABCG2, CYP2C9, and Statins": [
            "Atorvastatin",
            "Simvastatin",
            "Rosuvastatin",
        ],
    }

    for pfile in pdf_files:
        rel_source = f"{pfile.parent.name}/{pfile.name}"[:100]
        substances = folder_substances.get(
            pfile.parent.name, [infer_substance_from_path(pfile)]
        )
        try:
            reader = PdfReader(str(pfile))
            full_text = []
            for page in reader.pages:
                t = page.extract_text() or ""
                t = re.sub(r"\s+", " ", t).strip()
                if t:
                    full_text.append(t)
            joined = " ".join(full_text)
            words = joined.split(" ")
            # ~300 words (~400 tokens) with 40 words (~50 tokens) overlap
            step = 260
            window = 300
            for i in range(0, len(words), step):
                segment = " ".join(words[i : i + window]).strip()
                if len(segment) < 80:
                    continue
                # Tag chunk with primary substance (or matching substance mentioned in chunk)
                matched_subs = [s for s in substances if s.lower() in segment.lower()]
                if not matched_subs:
                    matched_subs = [substances[0]]
                for sub in matched_subs[:2]:
                    chunks.append(
                        {
                            "SubstanceName": sub[:100],
                            "SourceFile": rel_source,
                            "ChunkContent": f"[{pfile.parent.name} - {sub}] {segment}"[
                                :2000
                            ],
                        }
                    )
        except Exception as e:
            print(f"   Warning reading PDF {pfile}: {e}")

    print(
        f"   Extracted {len(chunks):,} CPIC clinical guideline & recommendation chunks."
    )
    return chunks


def main():
    t0 = time.time()
    conn_str = f"{config.IRIS_HOST}:{config.IRIS_PORT}/{config.IRIS_NAMESPACE}"
    conn = iris.connect(conn_str, config.IRIS_USER, config.IRIS_PASSWORD)
    cur = conn.cursor()

    # Ensure tables are clean before bulk load
    for tbl in [
        "ClinicalData.SuklRegistry",
        "ClinicalData.Interactions",
        "ClinicalKnowledge.CpicVectors",
    ]:
        cur.execute(f"TRUNCATE TABLE {tbl}")
    conn.commit()

    # 1. SÚKL Registry
    df_sukl = build_sukl_dataframe()
    print("-> Bulk inserting SÚKL rows into ClinicalData.SuklRegistry...")
    sukl_rows = list(df_sukl.itertuples(index=False, name=None))
    batch_size = 2000
    for i in range(0, len(sukl_rows), batch_size):
        cur.executemany(
            """
            INSERT INTO ClinicalData.SuklRegistry
            (SuklCode, BrandName, ActiveSubstance, SubstanceCzech, Strength, Form, AtcCode, AtcName)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sukl_rows[i : i + batch_size],
        )
        conn.commit()
    print(f"   Inserted {len(sukl_rows):,} rows into ClinicalData.SuklRegistry.")

    # 2. DDInter Interactions
    df_ddi = build_ddinter_dataframe()
    print("-> Bulk inserting DDInter rows into ClinicalData.Interactions...")
    ddi_rows = list(df_ddi.itertuples(index=False, name=None))
    for i in range(0, len(ddi_rows), batch_size):
        cur.executemany(
            """
            INSERT INTO ClinicalData.Interactions
            (SubstanceA, SubstanceB, RiskLevel, MechanismText)
            VALUES (?, ?, ?, ?)
            """,
            ddi_rows[i : i + batch_size],
        )
        conn.commit()
    print(f"   Inserted {len(ddi_rows):,} rows into ClinicalData.Interactions.")

    # 3. CPIC Chunks & 384-d Embeddings
    cpic_chunks = extract_cpic_chunks()
    print(f"-> Computing 384-d embeddings with {config.EMBEDDING_MODEL_NAME}...")
    embedder = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
    texts = [c["ChunkContent"] for c in cpic_chunks]
    embeddings = embedder.encode(
        texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True
    )

    print("-> Inserting vectors into ClinicalKnowledge.CpicVectors...")
    vec_rows = []
    for chunk, emb in zip(cpic_chunks, embeddings):
        vec_str = ",".join(f"{float(x):.6f}" for x in emb)
        vec_rows.append(
            (
                chunk["SubstanceName"],
                chunk["SourceFile"],
                chunk["ChunkContent"],
                vec_str,
            )
        )

    for i in range(0, len(vec_rows), 250):
        cur.executemany(
            """
            INSERT INTO ClinicalKnowledge.CpicVectors
            (SubstanceName, SourceFile, ChunkContent, Embedding)
            VALUES (?, ?, ?, TO_VECTOR(?, DOUBLE, 384))
            """,
            vec_rows[i : i + 250],
        )
        conn.commit()
    print(
        f"   Inserted {len(vec_rows):,} embedded chunks into ClinicalKnowledge.CpicVectors."
    )

    cur.close()
    conn.close()
    print(f"Done in {time.time() - t0:.1f}s!")


if __name__ == "__main__":
    main()
