import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import duckdb
import os
import requests
import requests_cache
from dotenv import load_dotenv
from fastembed import TextEmbedding  # FastEmbed for generating embeddings

# cache requests
try:
    requests_cache.install_cache("data/openalex_cache", expire_after=86400)
except ImportError:
    print("failed to init request cache")
    exit(1)


def load_requests_data(data_path: Path):
    """Load JSON data from the given path and return a list of records.

    Returns None if the file is not found, the JSON is invalid, or the data
    is not a list.
    """
    try:
        with data_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {data_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None

    if not isinstance(data, list):
        print("Unexpected JSON format: expected a list of records.")
        return None
    return data


def fetch_frontmatter(doi):
    api_url = f"https://api.openalex.org/works/doi:{quote(doi)}"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        work_data = response.json()
        title = work_data.get("display_name") or work_data.get("title")
        abstract_inverted_index = work_data.get("abstract_inverted_index")

        # Rebuild the abstract from the inverted index
        if abstract_inverted_index:
            try:
                max_pos = max(
                    pos
                    for positions in abstract_inverted_index.values()
                    for pos in positions
                )
                abstract_tokens = [""] * (max_pos + 1)
                for term, positions in abstract_inverted_index.items():
                    for pos in positions:
                        abstract_tokens[pos] = term
                abstract = " ".join(abstract_tokens).strip()
            except Exception:
                abstract = "Error reconstructing abstract"
        else:
            abstract = "No abstract available"
        return {"doi": doi, "title": title, "abstract": abstract}
    except Exception as e:
        print(f"Failed to retrieve OpenAlex data for DOI {doi}: {e}")
        return None


def calc_embedding(record, embedder):
    """Create an embedding from title and abstract."""
    text = f"{record.get('title', '')}\n{record.get('abstract', '')}"
    try:
        embedding = list(embedder.embed([text]))
        return embedding[0]
    except Exception as e:
        print(f"Failed to embed record for DOI {record.get('doi')}: {e}")
        return None


def store_frontmatter(conn, frontmatter, embedding):
    """Insert a frontmatter record and its embedding into the DuckDB table.
    If a record with the same DOI already exists, update it instead of raising
    an exception."""
    try:
        conn.execute(
            """
            INSERT INTO frontmatter (doi, title, abstract, embedding)
            VALUES (?, ?, ?, ?)
            """,
            (
                frontmatter["doi"],
                frontmatter["title"],
                frontmatter["abstract"],
                embedding,
            ),
        )
    except Exception as e:
        # If the insert fails due to a duplicate primary key, update the existing row.
        err_msg = str(e).lower()
        if "unique" in err_msg or "duplicate" in err_msg:
            try:
                conn.execute(
                    """
                    UPDATE frontmatter
                    SET title = ?, abstract = ?, embedding = ?
                    WHERE doi = ?
                    """,
                    (
                        frontmatter["title"],
                        frontmatter["abstract"],
                        embedding,
                        frontmatter["doi"],
                    ),
                )
            except Exception as ue:
                print(f"Failed to update record for DOI {frontmatter['doi']}: {ue}")
        else:
            print(f"Failed to store record for DOI {frontmatter['doi']}: {e}")


def record_exists(conn, doi):
    """Check whether a record with the given DOI already exists in the frontmatter table."""
    try:
        result = conn.execute(
            "SELECT 1 FROM frontmatter WHERE doi = ?", (doi,)
        ).fetchone()
        return result is not None
    except Exception as e:
        print(f"Error checking existence of DOI {doi}: {e}")
        return False


def main():

    load_dotenv()
    token = os.getenv("PREREVIEW_REQUEST_DATA_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("https://prereview.org/requests-data", headers=headers)
    response.raise_for_status()
    requests_data = response.json()

    if requests_data is None:
        return

    # Initialize DuckDB connection and ensure table exists
    db_path = Path("./data/frontmatter.duckdb")
    duckdbconn = duckdb.connect(database=str(db_path))
    duckdbconn.execute("""
        CREATE TABLE IF NOT EXISTS frontmatter (
            doi TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            embedding DOUBLE[]  -- store vector as an array of doubles
        )
        """)

    # Initialize FastEmbed model (you can choose a specific model if desired)
    embedder = TextEmbedding(model_name="thenlper/gte-large")

    for idx, entry in enumerate(requests_data):
        doi = entry.get("preprint", "").strip("doi:")
        if not doi:
            print(f"[{idx}] No DOI in request data")
            continue

        if record_exists(duckdbconn, doi):
            continue

        frontmatter = fetch_frontmatter(doi)
        if frontmatter is None:
            print(f"[{idx}] Failed to fetch frontmatter for DOI {doi}")
            continue

        embedding = calc_embedding(frontmatter, embedder)
        if embedding is None:
            print(f"[{idx}] Skipping storage due to embedding failure for DOI {doi}")
            continue

        store_frontmatter(duckdbconn, frontmatter, embedding)

    duckdbconn.close()


if __name__ == "__main__":
    main()
