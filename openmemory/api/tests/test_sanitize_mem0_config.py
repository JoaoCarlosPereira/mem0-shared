"""Regression: stale cross-provider keys must not break Memory client init."""

from app.utils.memory import sanitize_mem0_config


def test_openai_llm_drops_ollama_base_url():
    raw = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-oss-20b.gguf",
                "openai_base_url": "http://host.docker.internal:8000/v1",
                "ollama_base_url": "http://192.168.3.213:8000/v1",
                "api_key": "llama.cpp",
            },
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": "nomic-embed-text:latest",
                "ollama_base_url": "http://host.docker.internal:11434",
            },
        },
    }
    cleaned = sanitize_mem0_config(raw)
    assert "ollama_base_url" not in cleaned["llm"]["config"]
    assert cleaned["llm"]["config"]["openai_base_url"].endswith("/v1")


def test_ollama_llm_drops_openai_base_url():
    raw = {
        "llm": {
            "provider": "ollama",
            "config": {
                "model": "llama3",
                "ollama_base_url": "http://host.docker.internal:11434",
                "openai_base_url": "http://host.docker.internal:8000/v1",
            },
        },
    }
    cleaned = sanitize_mem0_config(raw)
    assert "openai_base_url" not in cleaned["llm"]["config"]


def test_ollama_embedder_drops_openai_base_url():
    raw = {
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": "nomic-embed-text",
                "ollama_base_url": "http://host.docker.internal:11434",
                "openai_base_url": "http://host.docker.internal:8000/v1",
            },
        },
    }
    cleaned = sanitize_mem0_config(raw)
    assert "openai_base_url" not in cleaned["embedder"]["config"]
