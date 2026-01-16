## Experiment with embeddings for review requests

`uv run main.py` to generate embeddings

Queries to OpenAlex are cached in sqlite DB. Frontmatter and embedding are store in DuckDB file. Initial run for 1000 requests took 12 minutes.

`uv run suggest.py` to run webserver that lets you find similar DOI
