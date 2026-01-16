## Experiment with embeddings for review requests

`uv run suggest.py` to run webserver that lets you find similar DOI

`uv run generate_embeddings.py` to generate embeddings

Queries to OpenAlex are cached in sqlite DB. Frontmatter and embedding are store in DuckDB file. Initial run for 1000 requests took 12 minutes. The cache and embeddings are stored in git LFS, so you don't have to run the generation to try the suggestions.
