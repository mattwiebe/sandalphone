import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

import pipecat_app


@pytest.mark.contract
def test_supported_runtime_surface_exports_current_core_types() -> None:
    expected = {
        "AudioPolicy",
        "LiveKitRoomPolicy",
        "InboundSipConfig",
        "OutboundDialRequest",
        "PrivateTranslationRuntime",
        "StructuredEventLogger",
    }

    assert expected.issubset(set(pipecat_app.__all__))
