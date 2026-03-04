"""Tests for slowapi rate limiting."""

from unittest.mock import patch

from dental_notes_backend.models.api_models import SoapNoteResponse


def test_generate_note_rate_limit(client):
    """POST /generate-note returns 429 after exceeding 20/minute."""
    soap_json = {
        "subjective": "Toothache",
        "objective": {
            "clinical_findings": "Caries on #19",
            "radiographic_findings": None,
            "vitals": None,
        },
        "assessment": "Caries #19",
        "plan": {
            "today": ["Composite restoration"],
            "next_visit": [],
            "patient_instructions": [],
            "cdt_codes": ["D2391"],
        },
        "medication_changes": [],
    }

    with patch(
        "dental_notes_backend.services.claude_service.generate_soap",
    ) as mock_soap:
        mock_soap.return_value = SoapNoteResponse.model_validate(soap_json)

        statuses = []
        for _ in range(21):
            resp = client.post(
                "/generate-note",
                json={"transcript": "test", "note_type": "soap"},
            )
            statuses.append(resp.status_code)

    assert 429 in statuses, f"Expected at least one 429, got: {set(statuses)}"
    assert statuses[0] == 200
