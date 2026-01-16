import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote

import requests


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


def main():
    requests_data = load_requests_data(Path("./prereview-data/requests.json"))
    if requests_data is None:
        return

    count_requests_per_server(requests_data)

    # Find the first DOI for a biorxiv request
    doi = ""
    for request in requests_data:
        if request.get("server", "") == "biorxiv":
            doi = request.get("preprint", "")
            break

    if not doi:
        print("No DOI found for a biorxiv request.")
    else:
        # Use the OpenAlex Works API to retrieve title and abstract

        # Encode the DOI for safe URL usage
        encoded_doi = quote(doi)
        api_url = f"https://api.openalex.org/works/doi:{encoded_doi}"

        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            work_data = response.json()
            title = work_data.get("display_name") or work_data.get("title")
            abstract = work_data.get("abstract_inverted_index")
            print(f"Title: {title}")
            print(f"Abstract: {abstract}")
        except Exception as e:
            print(f"Failed to retrieve OpenAlex data for DOI {doi}: {e}")


if __name__ == "__main__":
    main()
