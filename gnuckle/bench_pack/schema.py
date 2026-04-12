"""Manifest schema validation."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from gnuckle.bench_pack.parser import validate_regex_pattern
from gnuckle.bench_pack.trust import ALLOWED_BINARIES, ALLOWED_PLACEHOLDERS, TRUSTED_DATASET_HOSTS

MANIFEST_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,48}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
ARG_RE = re.compile(r"^(-{0,2}[a-zA-Z0-9_./:=@-]+|\{[a-z_]+\})$")
PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")


class AuthorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    contact: str | None = None


class DatasetModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    url: str
    sha256: str
    size_bytes_max: int
    archive: str | None = None
    extract: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https":
            raise ValueError("dataset.url must use https")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", value or ""):
            raise ValueError("dataset.sha256 must be 64 hex chars")
        return value.lower()

    @field_validator("size_bytes_max")
    @classmethod
    def validate_size_cap(cls, value: int) -> int:
        if value < 1 or value > 500 * 1024 * 1024:
            raise ValueError("dataset.size_bytes_max must be between 1 and 500 MB")
        return value


class StageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    when: str | None = None
    args_template: list[str]

    @field_validator("args_template")
    @classmethod
    def validate_args_template(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("args_template must not be empty")
        for item in value:
            if not ARG_RE.fullmatch(item):
                raise ValueError(f"unsafe arg template entry: {item}")
            for match in PLACEHOLDER_RE.findall(item):
                if match not in ALLOWED_PLACEHOLDERS:
                    raise ValueError(f"unknown placeholder: {match}")
        return value


class ParseMetricModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern: str
    unit: str | None = None

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, value: str) -> str:
        return validate_regex_pattern(value)


class ReportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    column_label: str | None = None
    primary_metric: str | None = None
    delta_vs_baseline: str | None = None
    tier_thresholds: dict[str, float] | None = None
    sort: str | None = None


class ManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = Field(alias="schema")
    id: str
    version: str
    gnuckle_min: str
    gnuckle_max: str | None = None
    author: AuthorModel
    description: str
    license: str
    kind: str
    tags: list[str] = Field(default_factory=list)
    binary: str
    dataset: DatasetModel | None = None
    requires_baseline: str | None = None
    stages: list[StageModel]
    parse: dict[str, ParseMetricModel]
    report: ReportModel | None = None
    timeout_seconds: int
    code_plugin: bool = False

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("only schema version 1 is supported")
        return value

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not MANIFEST_ID_RE.fullmatch(value or ""):
            raise ValueError("manifest id must match ^[a-z][a-z0-9_]{2,48}$")
        return value

    @field_validator("version", "gnuckle_min", "gnuckle_max")
    @classmethod
    def validate_semver(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not SEMVER_RE.fullmatch(value):
            raise ValueError("version fields must be semver")
        return value

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        allowed = {"quality", "speed", "agentic", "custom"}
        if value not in allowed:
            raise ValueError(f"kind must be one of {sorted(allowed)}")
        return value

    @field_validator("binary")
    @classmethod
    def validate_binary(cls, value: str) -> str:
        if value not in ALLOWED_BINARIES:
            raise ValueError(f"binary is not allowlisted: {value}")
        return value

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, value: int) -> int:
        if value < 1 or value > 7200:
            raise ValueError("timeout_seconds must be between 1 and 7200")
        return value

    @model_validator(mode="after")
    def validate_parse(self) -> "ManifestModel":
        if not self.parse:
            raise ValueError("manifest parse block must not be empty")
        return self


def schema_document() -> dict:
    return json.loads(files("gnuckle").joinpath("bench_manifest_schema.json").read_text(encoding="utf-8"))


def validate_manifest_dict(data: dict, *, trust_url: bool = False) -> ManifestModel:
    try:
        manifest = ManifestModel.model_validate(data)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    if manifest.dataset is not None and not trust_url:
        host = urlsplit(manifest.dataset.url).hostname or ""
        if host not in TRUSTED_DATASET_HOSTS:
            raise ValueError(f"dataset host is not trusted: {host}")
    return manifest
