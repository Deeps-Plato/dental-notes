"""Tests for OllamaService and FakeOllamaService.

Tests cover:
- FakeOllamaService behavior (is_available, is_model_ready, generate_structured, unload)
- FakeOllamaService call recording (call_count, last_system_prompt, last_user_content)
- FakeOllamaService default response validates against ExtractionResult schema
- Real OllamaService with mocked ollama.Client (no running Ollama needed)
"""

import json
from unittest import mock

import pytest


# --- FakeOllamaService tests ---


class TestFakeOllamaServiceAvailability:
    """FakeOllamaService returns True for availability checks."""

    def test_is_available_returns_true(self, fake_ollama_service):
        assert fake_ollama_service.is_available() is True

    def test_is_model_ready_returns_true(self, fake_ollama_service):
        assert fake_ollama_service.is_model_ready() is True


class TestFakeOllamaServiceGenerate:
    """FakeOllamaService generate_structured returns valid JSON and records calls."""

    def test_generate_structured_returns_json(self, fake_ollama_service):
        from dental_notes.clinical.models import ExtractionResult

        raw = fake_ollama_service.generate_structured(
            system_prompt="test prompt",
            user_content="test content",
            schema=ExtractionResult.model_json_schema(),
        )
        # Must parse as valid JSON
        data = json.loads(raw)
        assert isinstance(data, dict)
        # Must validate against ExtractionResult schema
        result = ExtractionResult.model_validate(data)
        assert result.soap_note.subjective is not None

    def test_generate_structured_records_call(self, fake_ollama_service):
        fake_ollama_service.generate_structured(
            system_prompt="sys prompt",
            user_content="user text",
            schema={},
        )
        assert fake_ollama_service.last_system_prompt == "sys prompt"
        assert fake_ollama_service.last_user_content == "user text"

    def test_generate_structured_increments_call_count(self, fake_ollama_service):
        assert fake_ollama_service.call_count == 0
        fake_ollama_service.generate_structured("s", "u", {})
        assert fake_ollama_service.call_count == 1
        fake_ollama_service.generate_structured("s", "u", {})
        assert fake_ollama_service.call_count == 2

    def test_default_response_nests_cdt_codes_in_soap_note(self, fake_ollama_service):
        """CRITICAL: cdt_codes must be inside soap_note, not at top level."""
        raw = fake_ollama_service.generate_structured("s", "u", {})
        data = json.loads(raw)
        assert "cdt_codes" in data["soap_note"], "cdt_codes must be inside soap_note"
        assert "cdt_codes" not in data, "cdt_codes must NOT be at top level"


class TestFakeOllamaServiceUnload:
    """FakeOllamaService unload completes without error."""

    def test_unload_does_not_raise(self, fake_ollama_service):
        fake_ollama_service.unload()  # Should not raise


# --- Real OllamaService tests (with mocked Client) ---


class TestRealOllamaServiceAvailability:
    """OllamaService availability checks with mocked ollama.Client."""

    def test_is_available_true(self):
        from dental_notes.clinical.ollama_service import OllamaService

        service = OllamaService(host="http://localhost:11434", model="qwen3:8b")
        with mock.patch.object(service, "_client") as mock_client:
            mock_client.list.return_value = mock.MagicMock(models=[])
            assert service.is_available() is True

    def test_is_available_false_on_connection_error(self):
        from dental_notes.clinical.ollama_service import OllamaService

        service = OllamaService(host="http://localhost:11434", model="qwen3:8b")
        with mock.patch.object(service, "_client") as mock_client:
            mock_client.list.side_effect = ConnectionError("Connection refused")
            assert service.is_available() is False


class TestRealOllamaServiceModelReady:
    """OllamaService model readiness checks with mocked Client."""

    def test_is_model_ready_true(self):
        from dental_notes.clinical.ollama_service import OllamaService

        service = OllamaService(host="http://localhost:11434", model="qwen3:8b")
        with mock.patch.object(service, "_client") as mock_client:
            mock_client.show.return_value = {"model": "qwen3:8b"}
            assert service.is_model_ready() is True

    def test_is_model_ready_false_on_404(self):
        from ollama import ResponseError

        from dental_notes.clinical.ollama_service import OllamaService

        service = OllamaService(host="http://localhost:11434", model="qwen3:8b")
        with mock.patch.object(service, "_client") as mock_client:
            mock_client.show.side_effect = ResponseError("model not found")
            assert service.is_model_ready() is False


class TestRealOllamaServiceGenerate:
    """OllamaService generate_structured with mocked Client."""

    def test_generate_structured_returns_json_string(self):
        from dental_notes.clinical.ollama_service import OllamaService

        service = OllamaService(host="http://localhost:11434", model="qwen3:8b")

        mock_response = mock.MagicMock()
        mock_response.message.content = json.dumps({
            "soap_note": {
                "subjective": "s",
                "objective": "o",
                "assessment": "a",
                "plan": "p",
                "cdt_codes": [],
            },
            "speaker_chunks": [],
            "clinical_summary": "summary",
        })

        with mock.patch.object(service, "_client") as mock_client:
            mock_client.chat.return_value = mock_response
            result = service.generate_structured(
                system_prompt="sys",
                user_content="user",
                schema={"type": "object"},
            )
            assert isinstance(result, str)
            data = json.loads(result)
            assert data["soap_note"]["subjective"] == "s"

    def test_generate_structured_prepends_nothink(self):
        """generate_structured must prepend /nothink to user content."""
        from dental_notes.clinical.ollama_service import OllamaService

        service = OllamaService(host="http://localhost:11434", model="qwen3:8b")

        mock_response = mock.MagicMock()
        mock_response.message.content = "{}"

        with mock.patch.object(service, "_client") as mock_client:
            mock_client.chat.return_value = mock_response
            service.generate_structured(
                system_prompt="sys",
                user_content="transcript text",
                schema={},
            )
            call_args = mock_client.chat.call_args
            messages = call_args.kwargs.get("messages", call_args[1].get("messages", []))
            user_msg = messages[1]["content"]
            assert user_msg.startswith("/nothink\n\n")
            assert "transcript text" in user_msg


class TestRealOllamaServiceUnload:
    """OllamaService unload with mocked Client."""

    def test_unload_success(self):
        from dental_notes.clinical.ollama_service import OllamaService

        service = OllamaService(host="http://localhost:11434", model="qwen3:8b")
        with mock.patch.object(service, "_client") as mock_client:
            mock_client.chat.return_value = mock.MagicMock()
            service.unload()  # Should not raise
            mock_client.chat.assert_called_once()

    def test_unload_failure_does_not_raise(self):
        from dental_notes.clinical.ollama_service import OllamaService

        service = OllamaService(host="http://localhost:11434", model="qwen3:8b")
        with mock.patch.object(service, "_client") as mock_client:
            mock_client.chat.side_effect = Exception("Connection refused")
            service.unload()  # Should NOT raise despite the error
