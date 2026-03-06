from pathlib import Path

import duckdb
from fastembed import TextEmbedding
from flask import Flask, render_template_string, request

from generate_embeddings import calc_embedding, fetch_frontmatter

DB_PATH = Path("./data/frontmatter.duckdb")

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<head>
  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.classless.min.css"
  >
  <title>Related Review Requests</title>
</head>
<body>
  <main>
    <h1>Find related review requests</h1>
    <p>Find review requests for preprints similar to given DOIs.</p>
    <form method="get">
      <textarea name="dois" placeholder="Enter one DOI per line" rows="5" required>{{ dois_value }}</textarea>
      <button type="submit">Search</button>
    </form>
    {% if error %}
      <p style="color:red;">{{ error }}</p>
    {% endif %}
    {% if query %}
      <h2>Searched DOIs</h2>
      <ul>
        {% for item in query.dois %}
          <li><a href="https://doi.org/{{ item.doi }}" target="_blank">{{ item.doi }}</a> – {{ item.title }}</li>
        {% endfor %}
      </ul>
    {% endif %}
    {% if results %}
      <h2>Top 10 related review requests</h2>
      <ul>
        {% for item in results %}
          <li><a href="https://doi.org/{{ item.doi }}" target="_blank">{{ item.doi }}</a> – {{ item.title }}</li>
        {% endfor %}
      </ul>
    {% endif %}
  </main>
</body>
"""

_webapp_embedder = TextEmbedding(
    model_name="thenlper/gte-large",
    cache_dir="./fastembed_cache",
    local_files_only=True,
)


def _find_similar(query_emb, limit=10):
    """Return up to `limit` records with the smallest Euclidean distance to `query_emb`."""
    DB_PATH = Path("./data/frontmatter.duckdb")
    if not DB_PATH.is_file():
        return []
    conn = duckdb.connect(database=str(DB_PATH))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_embeddings (
                query TEXT PRIMARY KEY,
                embedding DOUBLE[]
            )
        """)
        rows = conn.execute(
            """
            SELECT doi, title
            FROM frontmatter
            WHERE embedding IS NOT NULL
            ORDER BY list_distance(embedding, ?)
            LIMIT ?
        """,
            [query_emb, limit],
        ).fetchall()
    finally:
        conn.close()
    return [{"doi": d, "title": t} for d, t in rows]


def _get_query_embedding(query_key):
    """Return cached embedding for query from query_embeddings table, or None if not found."""
    DB_PATH = Path("./data/frontmatter.duckdb")
    if not DB_PATH.is_file():
        return None
    conn = duckdb.connect(database=str(DB_PATH))
    try:
        row = conn.execute(
            "SELECT embedding FROM query_embeddings WHERE query = ?", (query_key,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _save_query_embedding(query_key, emb):
    """Store computed embedding in query_embeddings table."""
    DB_PATH = Path("./data/frontmatter.duckdb")
    if not DB_PATH.is_file():
        return
    conn = duckdb.connect(database=str(DB_PATH))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO query_embeddings (query, embedding) VALUES (?, ?)",
            (query_key, emb),
        )
    finally:
        conn.close()


@app.route("/", methods=["GET"])
def index():
    error = None

    dois_arg = request.args.get("dois", "").strip()
    if not dois_arg:
        return render_template_string(
            HTML_TEMPLATE, results=None, error=None, query=None, dois_value=""
        )

    dois_raw = [
        d.strip()
        for d in dois_arg.replace(",", " ").replace("\n", " ").split()
        if d.strip()
    ]
    if not dois_raw:
        error = "Please provide at least one DOI."
        return render_template_string(
            HTML_TEMPLATE, results=None, error=error, query=None, dois_value=dois_arg
        )

    failed_dois = []
    successful_frontmatters = []
    for doi in dois_raw:
        front = fetch_frontmatter(doi)
        if not front:
            failed_dois.append(doi)
        else:
            successful_frontmatters.append(front)

    if failed_dois:
        error = f"Could not retrieve frontmatter for the following entries. Please remove or fix them. {', '.join(failed_dois)}"
        return render_template_string(
            HTML_TEMPLATE, results=None, error=error, query=None, dois_value=dois_arg
        )

    dois_raw.sort()
    query_key = "|".join(dois_raw)
    query_emb = _get_query_embedding(query_key)

    if query_emb is None:
        combined_text = "\n\n".join(
            [f"{f['title']}\n{f['abstract']}" for f in successful_frontmatters]
        )
        query_emb = calc_embedding(
            {"title": combined_text, "abstract": ""}, _webapp_embedder
        )
        if query_emb is None:
            error = "Failed to compute embedding."
            return render_template_string(
                HTML_TEMPLATE,
                results=None,
                error=error,
                query=None,
                dois_value=dois_arg,
            )

        _save_query_embedding(query_key, query_emb)

    results = _find_similar(query_emb, limit=10)
    if not results:
        error = "No similar entries found."

    query_info = {
        "dois": [
            {"doi": doi, "title": (fetch_frontmatter(doi) or {}).get("title", "")}
            for doi in dois_raw
        ]
    }

    return render_template_string(
        HTML_TEMPLATE,
        results=results,
        error=error,
        query=query_info,
        dois_value=dois_arg,
    )


if __name__ == "__main__":
    if not DB_PATH.is_file():
        print(f"failed to connect to duckdb file at: {DB_PATH}")
        os.exit(1)
    conn = duckdb.connect(database=str(DB_PATH))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS query_embeddings (
                query TEXT PRIMARY KEY,
                embedding DOUBLE[]
            )
        """)
    finally:
        conn.close()

    app.run(host="0.0.0.0", port=8080, debug=True)
