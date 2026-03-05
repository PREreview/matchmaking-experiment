from fastembed import TextEmbedding


def trigger_model_download():
    TextEmbedding(model_name="thenlper/gte-large", cache_dir="./fastembed_cache")


if __name__ == "__main__":
    trigger_model_download()
