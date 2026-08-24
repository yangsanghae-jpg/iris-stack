import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _bounded_int(
    values: Mapping[str, str],
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(values.get(name, str(default)))
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


@dataclass(frozen=True)
class RuntimePolicy:
    profile: str
    default_model: str
    allowed_models: tuple[str, ...]
    max_context_tokens: int
    max_output_tokens: int

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "RuntimePolicy":
        return cls(
            profile=(values.get("IRIS_RUNTIME_PROFILE") or "default").strip(),
            default_model=(values.get("IRIS_DEFAULT_MODEL") or "qwen3:30b").strip(),
            allowed_models=_csv(values.get("IRIS_ALLOWED_MODELS")),
            max_context_tokens=_bounded_int(
                values,
                "IRIS_MODEL_NUM_CTX",
                default=32768,
                minimum=1024,
                maximum=131072,
            ),
            max_output_tokens=_bounded_int(
                values,
                "IRIS_MODEL_NUM_PREDICT",
                default=4096,
                minimum=1,
                maximum=32768,
            ),
        )

    @classmethod
    def from_env(cls) -> "RuntimePolicy":
        return cls.from_mapping(os.environ)

    def resolve_model(self, requested_model: str | None) -> str:
        model = (requested_model or self.default_model).strip()
        if not model:
            raise ValueError("model is required")
        if self.allowed_models and model not in self.allowed_models:
            allowed = ", ".join(self.allowed_models)
            raise ValueError(f"model '{model}' is not allowed; allowed models: {allowed}")
        return model

    def apply_generation_limits(self, options: Mapping[str, Any] | None) -> dict[str, Any]:
        limited = dict(options or {})
        limited["num_ctx"] = self._cap_option(
            limited.get("num_ctx"),
            default=self.max_context_tokens,
            maximum=self.max_context_tokens,
        )
        limited["num_predict"] = self._cap_option(
            limited.get("num_predict"),
            default=self.max_output_tokens,
            maximum=self.max_output_tokens,
        )
        return limited

    def filter_ollama_models(self, models: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.allowed_models:
            return list(models)
        allowed = set(self.allowed_models)
        return [model for model in models if model.get("name") in allowed]

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "default_model": self.default_model,
            "allowed_models": list(self.allowed_models),
            "max_context_tokens": self.max_context_tokens,
            "max_output_tokens": self.max_output_tokens,
        }

    @staticmethod
    def _cap_option(value: Any, *, default: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(1, min(parsed, maximum))
