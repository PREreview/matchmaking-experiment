from pathlib import Path

import duckdb
import numpy as np
from fastembed import TextEmbedding
from flask import Flask, render_template_string, request

from generate_embeddings import calc_embedding, fetch_frontmatter

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<title>DOI Similarity Search</title>
<h1>Search by DOI</h1>
<form method="post">
  <input type="text" name="doi" placeholder="Enter DOI" style="width:400px;" required>
  <button type="submit">Search</button>
</form>
{% if error %}
  <p style="color:red;">{{ error }}</p>
{% endif %}
{% if results %}
  <h2>Top 10 similar entries</h2>
  <ul>
  {% for item in results %}
    <li><a href="https://doi.org/{{ item.doi }}" target="_blank">{{ item.doi }}</a> – {{ item.title }}</li>
  {% endfor %}
  </ul>
{% endif %}
"""

_webapp_embedder = TextEmbedding(model_name="thenlper/gte-large")


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
        return render_template_string(HTML_TEMPLATE, results=None, error=None)

    doi = request.form.get("doi", "").strip()
    if not doi:
        error = "Please provide a DOI."
        return render_template_string(HTML_TEMPLATE, results=None, error=error)

    front = fetch_frontmatter(doi)
    if not front:
        error = f"No entry found for DOI {doi}."
        return render_template_string(HTML_TEMPLATE, results=None, error=error)

    emb = calc_embedding(front, _webapp_embedder)
    if emb is None:
        error = "Failed to compute embedding."
        return render_template_string(HTML_TEMPLATE, results=None, error=error)

    results = _find_similar(emb)
    if not results:
        error = "No similar entries found."
    return render_template_string(HTML_TEMPLATE, results=results, error=error)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
