import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import requests
import requests_cache

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


def count_requests_per_server(requests_data):
    """Count entries per 'server' and print the results."""
    # Extract server values from records that contain the key
    servers = [rec["server"] for rec in requests_data if "server" in rec]
    # Compute counts
    server_counts = Counter(servers)

    # Print the results
    print("Requests per server:")
    for server, count in server_counts.items():
        print(f"{server}: {count}")
    print("\n")
    return server_counts


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


def main():
    requests_data = load_requests_data(Path("./data/requests.json"))
    if requests_data is None:
        return

    count_requests_per_server(requests_data)

    frontmatter_list = []
    for idx, entry in enumerate(requests_data[:10]):
        doi = entry.get("preprint", "")
        if not doi:
            print(f"[{idx}] No DOI in request data")
            continue

        result = fetch_frontmatter(doi)
        if result is None:
            print(f"[{idx}] Failed to fetch frontmatter for DOI {doi}")
            continue

        frontmatter_list.append(result)

    print("Frontmatter list:")
    for item in frontmatter_list:
        print(item)


if __name__ == "__main__":
    main()
