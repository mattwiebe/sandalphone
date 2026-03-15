from dataclasses import dataclass
from pathlib import Path
from time import perf_counter


@dataclass(frozen=True)
class BenchmarkCase:
    provider_kind: str
    provider_name: str
    input_payload: str
    source_lang: str
    target_lang: str
    output_path: Path | None = None


@dataclass(frozen=True)
class BenchmarkResult:
    provider_kind: str
    provider_name: str
    success: bool
    latency_ms: float
    output_payload: str | None = None
    output_path: Path | None = None
    output_size_bytes: int | None = None


class ProviderProfiler:
    def profile_translation(self, provider, case: BenchmarkCase) -> BenchmarkResult:
        start = perf_counter()
        output = provider.translate(
            case.input_payload,
            case.source_lang,
            case.target_lang,
        )
        latency_ms = (perf_counter() - start) * 1000

        return BenchmarkResult(
            provider_kind=case.provider_kind,
            provider_name=case.provider_name,
            success=True,
            latency_ms=latency_ms,
            output_payload=output,
        )

    def profile_tts(self, provider, case: BenchmarkCase) -> BenchmarkResult:
        start = perf_counter()
        output_path = provider.synthesize(
            case.input_payload,
            output_file=case.output_path,
            language=case.target_lang,
        )
        latency_ms = (perf_counter() - start) * 1000
        resolved_path = Path(output_path)

        return BenchmarkResult(
            provider_kind=case.provider_kind,
            provider_name=case.provider_name,
            success=True,
            latency_ms=latency_ms,
            output_path=resolved_path,
            output_size_bytes=resolved_path.stat().st_size,
        )
