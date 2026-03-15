from dataclasses import dataclass, field


class ConfigValidationError(ValueError):
    pass


@dataclass(frozen=True)
class AppConfig:
    livekit_url: str
    api_key: str
    api_secret: str


@dataclass(frozen=True)
class HealthReport:
    status: str
    checks: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "checks": self.checks,
        }


@dataclass
class MetricsCollector:
    counters: dict[str, int] = field(default_factory=dict)
    latencies: dict[str, list[float]] = field(default_factory=dict)

    def increment_error(self, counter_name: str) -> None:
        self.counters[counter_name] = self.counters.get(counter_name, 0) + 1

    def record_latency(self, metric_name: str, value_ms: float) -> None:
        self.latencies.setdefault(metric_name, []).append(value_ms)


class StructuredEventLogger:
    def log(self, event: str, **fields: str) -> dict[str, str]:
        return {
            "event": event,
            **fields,
        }


def validate_config(config: AppConfig) -> None:
    if not config.livekit_url:
        raise ConfigValidationError("livekit_url is required")
    if not config.api_key:
        raise ConfigValidationError("api_key is required")
    if not config.api_secret:
        raise ConfigValidationError("api_secret is required")


def build_health_report(config: AppConfig) -> HealthReport:
    checks = {
        "livekit_url": "ready" if config.livekit_url else "missing",
        "api_key": "ready" if config.api_key else "missing",
        "api_secret": "ready" if config.api_secret else "missing",
    }
    status = "healthy" if all(value == "ready" for value in checks.values()) else "degraded"
    return HealthReport(status=status, checks=checks)
