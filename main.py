import json
from collections import Counter
from pathlib import Path


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

    doi = ""
    for request in requests_data:
        if request.get("server", "") == "biorxiv":
            doi = request["preprint"]
            break
    print(doi)


if __name__ == "__main__":
    main()
