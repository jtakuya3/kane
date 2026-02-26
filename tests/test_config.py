"""Tests for the configuration module."""

from pathlib import Path

from kane.config.settings import Settings, LLMConfig, GatewayConfig


class TestSettings:
    def test_defaults(self) -> None:
        settings = Settings()
        assert settings.llm.provider == "openai"
        assert settings.llm.model == "gpt-4o"
        assert settings.gateway.host == "127.0.0.1"
        assert settings.gateway.port == 8321
        assert "cli" in settings.enabled_channels
        assert settings.default_agent == "default"

    def test_save_and_load(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        settings = Settings()
        settings.llm.api_key = "test-key-123"
        settings.llm.provider = "anthropic"
        settings.save(config_path)

        loaded = Settings.load(config_path)
        assert loaded.llm.api_key == "test-key-123"
        assert loaded.llm.provider == "anthropic"

    def test_load_missing_file(self, tmp_path: Path) -> None:
        settings = Settings.load(tmp_path / "nonexistent.json")
        assert settings.llm.provider == "openai"  # defaults

    def test_to_dict_and_from_dict(self) -> None:
        settings = Settings()
        settings.llm.model = "custom-model"
        settings.enabled_channels = ["cli", "webhook"]

        data = settings._to_dict()
        restored = Settings._from_dict(data)
        assert restored.llm.model == "custom-model"
        assert restored.enabled_channels == ["cli", "webhook"]


class TestLLMConfig:
    def test_defaults(self) -> None:
        config = LLMConfig()
        assert config.provider == "openai"
        assert config.temperature == 0.7
        assert config.max_tokens == 4096


class TestGatewayConfig:
    def test_defaults(self) -> None:
        config = GatewayConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8321
        assert config.debug is False
