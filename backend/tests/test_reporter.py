"""
Unit tests for services/reporter.py.

All tests run without a real database or network — inputs are built in-memory
and the Anthropic SDK is mocked throughout.

Coverage:
  - Mock path (USE_MOCK_REPORTS=true)
  - Real path with successful first-attempt parse
  - Real path with first-attempt parse failure → second-attempt success (retry)
  - Real path where both attempts fail → RuntimeError
  - _build_prompt() output shape
  - _parse_claude_json() — happy path and all failure modes
  - stream_report_tokens() async generator with mocked AsyncAnthropic
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from app.models.anomaly import Anomaly, AnomalyType, ReportStatus, Severity
from app.repositories.market_repo import RollingStats
from app.services.reporter import (
    _build_prompt,
    _call_claude_with_retry,
    _parse_claude_json,
    stream_report_tokens,
)

pytestmark = pytest.mark.asyncio


# ── Fixtures / helpers ────────────────────────────────────────────────────────


def _make_anomaly(**overrides) -> MagicMock:
    """Return a MagicMock that looks like an Anomaly ORM object."""
    defaults: dict = {
        "id": uuid.uuid4(),
        "detected_at": datetime(2024, 1, 15, 14, 30, tzinfo=timezone.utc),
        "candle_time": datetime(2024, 1, 15, 14, 29, tzinfo=timezone.utc),
        "ticker": "TSLA",
        "type": AnomalyType.volume_spike,
        "severity": Severity.HIGH,
        "zscore": 4.23,
        "iqr_flag": False,
        "report_status": ReportStatus.pending,
    }
    defaults.update(overrides)
    mock = MagicMock(spec=Anomaly)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


def _make_stats(mean: float = 1_000_000, std: float = 100_000, count: int = 20) -> RollingStats:
    return RollingStats(mean=mean, std=std, count=count)


def _make_candle() -> MagicMock:
    c = MagicMock()
    c.open = "180.0000"
    c.high = "181.0000"
    c.low = "179.0000"
    c.close = "180.5000"
    c.volume = 5_000_000
    return c


def _valid_report_json(**overrides) -> str:
    base = {
        "summary": "Significant volume spike detected above historical norms.",
        "reasons": ["Z-score exceeded 3.5 threshold.", "Institutional volume pattern.", "Elevated ADV."],
        "risk_level": "High",
        "confidence": 0.88,
    }
    base.update(overrides)
    return json.dumps(base)


def _mock_anthropic_response(content: str, input_tokens: int = 120, output_tokens: int = 80) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=content)]
    resp.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    return resp


# ── _build_prompt tests ───────────────────────────────────────────────────────


def test_build_prompt_contains_ticker():
    anomaly = _make_anomaly(ticker="NVDA")
    prompt = _build_prompt(anomaly, [], _make_stats())
    assert "NVDA" in prompt


def test_build_prompt_contains_zscore():
    anomaly = _make_anomaly(zscore=3.75)
    prompt = _build_prompt(anomaly, [], _make_stats())
    assert "3.75" in prompt


def test_build_prompt_contains_severity():
    anomaly = _make_anomaly(severity=Severity.MEDIUM)
    prompt = _build_prompt(anomaly, [], _make_stats())
    assert "MEDIUM" in prompt


def test_build_prompt_includes_candle_data():
    anomaly = _make_anomaly()
    candle = _make_candle()
    prompt = _build_prompt(anomaly, [candle], _make_stats())
    assert "5,000,000" in prompt  # volume formatted with commas
    assert "180.5000" in prompt   # close price


def test_build_prompt_includes_rolling_stats():
    stats = _make_stats(mean=2_000_000, std=200_000, count=20)
    prompt = _build_prompt(_make_anomaly(), [], stats)
    assert "2,000,000" in prompt


def test_build_prompt_handles_none_zscore():
    anomaly = _make_anomaly(zscore=None)
    prompt = _build_prompt(anomaly, [], _make_stats())
    assert "N/A" in prompt


def test_build_prompt_handles_empty_candles():
    prompt = _build_prompt(_make_anomaly(), [], _make_stats(count=0))
    # Should not raise; candle/stats context simply absent
    assert "TSLA" in prompt


# ── _parse_claude_json tests ──────────────────────────────────────────────────


def test_parse_claude_json_happy_path():
    anomaly = _make_anomaly()
    raw = _valid_report_json()
    result = _parse_claude_json(raw, anomaly, start=0.0, tokens_used=100)

    assert result.anomaly_id == anomaly.id
    assert result.summary == "Significant volume spike detected above historical norms."
    assert len(result.reasons) == 3
    assert result.risk_level == "High"
    assert result.confidence == pytest.approx(0.88)
    assert result.tokens_used == 100
    assert result.latency_ms >= 0


def test_parse_claude_json_strips_markdown_fences():
    anomaly = _make_anomaly()
    raw = "```json\n" + _valid_report_json() + "\n```"
    result = _parse_claude_json(raw, anomaly, start=0.0, tokens_used=0)
    assert result.summary != ""


def test_parse_claude_json_strips_plain_fences():
    anomaly = _make_anomaly()
    raw = "```\n" + _valid_report_json() + "\n```"
    result = _parse_claude_json(raw, anomaly, start=0.0, tokens_used=0)
    assert result.risk_level == "High"


def test_parse_claude_json_raises_on_invalid_json():
    with pytest.raises(json.JSONDecodeError):
        _parse_claude_json("not json at all", _make_anomaly(), start=0.0, tokens_used=0)


def test_parse_claude_json_raises_on_missing_fields():
    raw = json.dumps({"summary": "ok"})  # missing reasons, risk_level, confidence
    with pytest.raises(ValueError, match="Missing required fields"):
        _parse_claude_json(raw, _make_anomaly(), start=0.0, tokens_used=0)


def test_parse_claude_json_raises_on_wrong_reasons_count():
    raw = json.dumps({
        "summary": "ok",
        "reasons": ["only one"],
        "risk_level": "High",
        "confidence": 0.9,
    })
    with pytest.raises(ValueError, match="3 reasons"):
        _parse_claude_json(raw, _make_anomaly(), start=0.0, tokens_used=0)


# ── generate_report — mock path ───────────────────────────────────────────────


def test_generate_report_mock_path_returns_hardcoded_report():
    """Mock path: USE_MOCK_REPORTS=true returns the hardcoded mock without API call."""
    from app.services import reporter as reporter_module

    anomaly = _make_anomaly()

    with patch.object(reporter_module.settings, "use_mock_reports", True):
        # Access the underlying function even if @observe is wrapping it
        fn = getattr(reporter_module.generate_report, "__wrapped__", reporter_module.generate_report)
        result = fn(anomaly, [], _make_stats())

    assert result.anomaly_id == anomaly.id
    assert result.tokens_used == 0
    assert result.summary != ""
    assert len(result.reasons) == 3
    assert result.latency_ms >= 0


def test_generate_report_mock_path_makes_no_api_call():
    """Mock path must never touch the Anthropic client."""
    from app.services import reporter as reporter_module

    anomaly = _make_anomaly()

    with patch.object(reporter_module.settings, "use_mock_reports", True):
        with patch("app.services.reporter.anthropic.Anthropic") as mock_cls:
            fn = getattr(reporter_module.generate_report, "__wrapped__", reporter_module.generate_report)
            fn(anomaly, [], _make_stats())
            mock_cls.assert_not_called()


# ── _call_claude_with_retry tests ─────────────────────────────────────────────


def test_call_claude_success_on_first_attempt():
    """First attempt returns valid JSON — second attempt must not be made."""
    anomaly = _make_anomaly()
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_anthropic_response(_valid_report_json())

    with patch("app.services.reporter.settings") as mock_settings:
        mock_settings.anthropic_api_key = "sk-ant-test"
        result = _call_claude_with_retry(mock_client, "test prompt", anomaly, start=0.0)

    assert result.risk_level == "High"
    assert result.tokens_used == 200  # 120 input + 80 output
    mock_client.messages.create.assert_called_once()


def test_call_claude_retries_on_parse_failure():
    """First attempt returns garbage JSON → second attempt returns valid JSON."""
    anomaly = _make_anomaly()
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _mock_anthropic_response("not valid json {{{}"),   # attempt 1 fails
        _mock_anthropic_response(_valid_report_json()),    # attempt 2 succeeds
    ]

    result = _call_claude_with_retry(mock_client, "test prompt", anomaly, start=0.0)

    assert result.summary != ""
    assert mock_client.messages.create.call_count == 2


def test_call_claude_raises_after_two_failures():
    """Both attempts fail → RuntimeError is raised."""
    anomaly = _make_anomaly()
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _mock_anthropic_response("garbage 1"),
        _mock_anthropic_response("garbage 2"),
    ]

    with pytest.raises(RuntimeError, match="unparseable JSON after 2 attempts"):
        _call_claude_with_retry(mock_client, "test prompt", anomaly, start=0.0)

    assert mock_client.messages.create.call_count == 2


def test_call_claude_tokens_accumulated_across_attempts():
    """tokens_used must sum both attempts when a retry occurs."""
    anomaly = _make_anomaly()
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _mock_anthropic_response("bad json", input_tokens=50, output_tokens=10),
        _mock_anthropic_response(_valid_report_json(), input_tokens=80, output_tokens=60),
    ]

    result = _call_claude_with_retry(mock_client, "test prompt", anomaly, start=0.0)

    # 50+10 (failed attempt) + 80+60 (successful attempt) = 200
    assert result.tokens_used == 200


# ── stream_report_tokens tests ────────────────────────────────────────────────


class _MockTextStream:
    """Async iterator that yields a fixed list of string tokens."""

    def __init__(self, tokens: list[str]) -> None:
        self._iter = iter(tokens)

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _MockStreamCM:
    """Async context manager that exposes .text_stream."""

    def __init__(self, tokens: list[str]) -> None:
        self.text_stream = _MockTextStream(tokens)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


async def test_stream_report_tokens_yields_all_tokens():
    """Generator must yield every token the streaming API produces."""
    expected_tokens = ['{"summary":', ' "Volume spike.',
                       '", "reasons":', ' ["R1", "R2", "R3"],',
                       ' "risk_level": "High", "confidence": 0.9}']

    mock_instance = MagicMock()
    mock_instance.messages.stream.return_value = _MockStreamCM(expected_tokens)

    with patch("app.services.reporter.anthropic.AsyncAnthropic", return_value=mock_instance):
        with patch("app.services.reporter.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-ant-test"
            collected = []
            async for token in stream_report_tokens(_make_anomaly(), [], _make_stats()):
                collected.append(token)

    assert collected == expected_tokens


async def test_stream_report_tokens_uses_correct_model():
    """Streaming call must use the same model constant as non-streaming calls."""
    from app.services.reporter import _MODEL

    mock_instance = MagicMock()
    mock_instance.messages.stream.return_value = _MockStreamCM([])

    with patch("app.services.reporter.anthropic.AsyncAnthropic", return_value=mock_instance):
        with patch("app.services.reporter.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-ant-test"
            async for _ in stream_report_tokens(_make_anomaly(), [], _make_stats()):
                pass

    _, kwargs = mock_instance.messages.stream.call_args
    assert kwargs.get("model") == _MODEL or mock_instance.messages.stream.call_args[0][0] == _MODEL or \
        mock_instance.messages.stream.call_args.kwargs.get("model") == _MODEL


async def test_stream_report_tokens_yields_nothing_for_empty_stream():
    """Empty stream produces no tokens — generator terminates cleanly."""
    mock_instance = MagicMock()
    mock_instance.messages.stream.return_value = _MockStreamCM([])

    with patch("app.services.reporter.anthropic.AsyncAnthropic", return_value=mock_instance):
        with patch("app.services.reporter.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-ant-test"
            tokens = [t async for t in stream_report_tokens(_make_anomaly(), [], _make_stats())]

    assert tokens == []
