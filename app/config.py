"""Application configuration loaded from YAML + environment variables."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    secret_key: str = "dev-secret-change-in-production"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://sat_exam:sat_exam@localhost:5432/sat_exam"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    access_token_expire_min: int = 15
    refresh_token_expire_days: int = 7
    bcrypt_rounds: int = 12

    # Upload
    upload_max_file_size_mb: int = 25
    upload_storage_path: str = "./uploads"

    # Exam
    timer_mode_default: str = "strict"
    routing_threshold_default: float = 0.5

    # Practice
    default_weak_threshold: float = 0.60
    default_plan_days: int = 28
    tasks_per_plan_max: int = 30
    min_questions_for_weak_skill: int = 2

    # Extraction
    extraction_llm_provider: str = "openai"
    extraction_llm_model: str = "gpt-4o"
    extraction_confidence_threshold: float = 0.7

    # Scoring
    score_conversions_path: str = "./data/score_conversions.csv"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @classmethod
    def from_yaml(cls, path: str = "config.yaml") -> "Settings":
        """Load settings from YAML file, with env var overrides."""
        settings_dict = {}

        # Map from YAML section.key → Settings field name
        key_map = {
            # YAML path → Settings field
            "app.secret_key": "secret_key",
            "app.debug": "debug",
            "database.url": "database_url",
            "redis.url": "redis_url",
            "auth.access_token_expire_min": "access_token_expire_min",
            "auth.refresh_token_expire_days": "refresh_token_expire_days",
            "auth.bcrypt_rounds": "bcrypt_rounds",
            "upload.max_file_size_mb": "upload_max_file_size_mb",
            "upload.storage_path": "upload_storage_path",
            "exam.timer_mode_default": "timer_mode_default",
            "exam.routing_threshold_default": "routing_threshold_default",
            "practice.default_weak_threshold": "default_weak_threshold",
            "practice.default_plan_days": "default_plan_days",
            "practice.tasks_per_plan_max": "tasks_per_plan_max",
            "extraction.llm_provider": "extraction_llm_provider",
            "extraction.llm_model": "extraction_llm_model",
            "extraction.confidence_threshold": "extraction_confidence_threshold",
            "scoring.conversions_path": "score_conversions_path",
        }

        if os.path.exists(path):
            with open(path) as f:
                yaml_data = yaml.safe_load(f) or {}

            for yaml_path, setting_name in key_map.items():
                parts = yaml_path.split(".")
                val = yaml_data
                for part in parts:
                    if isinstance(val, dict):
                        val = val.get(part)
                    else:
                        val = None
                        break
                if val is not None:
                    settings_dict[setting_name] = val

        # Env vars override YAML (uppercase setting name)
        for setting_name in key_map.values():
            env_val = os.environ.get(setting_name.upper())
            if env_val is not None:
                settings_dict[setting_name] = env_val

        return cls(**settings_dict)


def get_settings() -> Settings:
    return Settings.from_yaml()
