"""Tests for the extended configuration model (language, framework, agents)."""

from sdlc_agents.config import AppConfig


def test_defaults_include_agents_and_framework():
    cfg = AppConfig()
    assert cfg.test_framework == "auto"
    assert cfg.agents.architect.detail_level == "standard"
    assert cfg.agents.developer.generate_unit_tests is True
    assert cfg.agents.validation.excel_report is True


def test_roundtrip_preserves_language_framework_and_agent_config():
    cfg = AppConfig()
    cfg.target_language = "rust"
    cfg.test_framework = "cargo-test"
    cfg.agents.architect.include_risks = False
    cfg.agents.developer.run_tests = False
    cfg.agents.validation.static_security_scan = False

    restored = AppConfig.from_dict(cfg.to_dict())
    assert restored.target_language == "rust"
    assert restored.test_framework == "cargo-test"
    assert restored.agents.architect.include_risks is False
    assert restored.agents.developer.run_tests is False
    assert restored.agents.validation.static_security_scan is False


def test_from_dict_tolerates_missing_agents_block():
    # Config files written by an older version have no 'agents' / 'test_framework'.
    legacy = {"backend": "offline", "target_language": "java"}
    cfg = AppConfig.from_dict(legacy)
    assert cfg.target_language == "java"
    assert cfg.test_framework == "auto"
    assert cfg.agents.developer.include_build_manifest is True


def test_from_dict_ignores_unknown_keys():
    data = AppConfig().to_dict()
    data["agents"]["developer"]["bogus_field"] = 123
    data["unknown_top"] = "x"
    cfg = AppConfig.from_dict(data)  # must not raise
    assert isinstance(cfg, AppConfig)
