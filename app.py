from pathlib import Path

import duckdb
import numpy as np
from fastembed import TextEmbedding
from flask import Flask, render_template_string, request

from generate_embeddings import calc_embedding, fetch_frontmatter

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
    <p>Find review requests for preprints similar to a given DOI.</p>
    <form method="post" role="search">
      <input type="text" name="doi" placeholder="Enter DOI" style="width:400px;" required>
      <button type="submit">Search</button>
    </form>
    {% if error %}
      <p style="color:red;">{{ error }}</p>
    {% endif %}
    {% if query %}
      <h2>Searched DOI</h2>
      <p><a href="https://doi.org/{{ query.doi }}" target="_blank">{{ query.doi }}</a></p>
      <p>{{ query.title }}</p>
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
    db_path = Path("./data/frontmatter.duckdb")
    if not db_path.is_file():
        return []
    conn = duckdb.connect(database=str(db_path))
    try:
        rows = conn.execute("SELECT doi, title, embedding FROM frontmatter").fetchall()
    finally:
        conn.close()
    distances = []
    q = np.array(query_emb, dtype=np.float64)
    for doi, title, stored_emb in rows:
        if stored_emb is None:
            continue
        try:
            s = np.array(stored_emb, dtype=np.float64)
            dist = np.linalg.norm(q - s)
            distances.append((dist, doi, title))
        except Exception:
            continue
    distances.sort(key=lambda x: x[0])
    top = distances[:limit]
    return [{"doi": d, "title": t} for _, d, t in top]


@app.route("/", methods=["GET", "POST"])
def index():
    error = None

    if request.method != "POST":
        return render_template_string(
            HTML_TEMPLATE, results=None, error=None, query=None
        )

    doi = request.form.get("doi", "").strip()
    if not doi:
        error = "Please provide a DOI."
        return render_template_string(
            HTML_TEMPLATE, results=None, error=error, query=None
        )

    front = fetch_frontmatter(doi)
    if not front:
        error = f"No entry found for DOI {doi}."
        return render_template_string(
            HTML_TEMPLATE, results=None, error=error, query=None
        )

    emb = calc_embedding(front, _webapp_embedder)
    if emb is None:
        error = "Failed to compute embedding."
        return render_template_string(
            HTML_TEMPLATE, results=None, error=error, query=None
        )

    results = _find_similar(emb, limit=10)
    if not results:
        error = "No similar entries found."
    query_info = {"doi": doi, "title": front.get("title", "")}
    return render_template_string(
        HTML_TEMPLATE, results=results, error=error, query=query_info
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
