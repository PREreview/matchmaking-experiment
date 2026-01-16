import json
from collections import Counter
from pathlib import Path


def main():
    # load data
    data_path = Path("./prereview-data/requests.json")
    try:
        with data_path.open("r", encoding="utf-8") as f:
            requests_data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {data_path}")
        return
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return

    if not isinstance(requests_data, list):
        print("Unexpected JSON format: expected a list of records.")
        return

    # count entries per 'server'
    servers = [rec["server"] for rec in requests_data if "server" in rec]
    server_counts = Counter(servers)

    print("Requests per server:")
    for server, count in server_counts.items():
        print(f"{server}: {count}")
    print("\n")


if __name__ == "__main__":
    main()
