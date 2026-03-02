"""Tests for POST /generate-note."""

from unittest.mock import patch

SOAP_FIXTURE = {
    "subjective": "Patient reports sensitivity to cold on upper right.",
    "objective": {
        "clinical_findings": "Caries noted on tooth 3 occlusal.",
        "radiographic_findings": None,
        "vitals": None,
    },
    "assessment": "Dental caries, tooth 3.",
    "plan": {
        "today": ["Composite restoration tooth 3 occlusal"],
        "next_visit": ["Recall in 6 months"],
        "patient_instructions": ["Avoid cold foods for 24 hours"],
        "cdt_codes": ["D2391  Resin-based composite — one surface, posterior"],
    },
    "medication_changes": [],
}

PERIO_FIXTURE = {
    "readings": [
        {"tooth": 14, "surface": "buccal", "depths": [3, 2, 4], "bop": True, "recession": 0}
    ],
    "unparsed_segments": [],
}

MED_FIXTURE = {
    "changes": [
        {
            "drug_name": "amoxicillin",
            "dose": "500mg",
            "frequency": "TID×7d",
            "change_type": "prescribed",
            "prescribing_note": None,
        }
    ]
}


def _make_req(note_type: str, transcript: str = "test transcript") -> dict:  # type: ignore[type-arg]
    return {"note_type": note_type, "transcript": transcript}


def test_generate_soap(client):
    with patch(
        "dental_notes_backend.services.claude_service.generate_soap",
        return_value=__import__(
            "dental_notes_backend.models.api_models", fromlist=["SoapNoteResponse"]
        ).SoapNoteResponse.model_validate(SOAP_FIXTURE),
    ):
        resp = client.post("/generate-note", json=_make_req("soap"))
    assert resp.status_code == 200
    body = resp.json()
    assert "subjective" in body
    assert body["medication_changes"] == []


def test_generate_perio_parse(client):
    with patch(
        "dental_notes_backend.services.claude_service.generate_perio_parse",
        return_value=__import__(
            "dental_notes_backend.models.api_models", fromlist=["PerioParseResponse"]
        ).PerioParseResponse.model_validate(PERIO_FIXTURE),
    ):
        resp = client.post("/generate-note", json=_make_req("perio_parse"))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["readings"]) == 1
    assert body["readings"][0]["tooth"] == 14


def test_generate_medication_extract(client):
    with patch(
        "dental_notes_backend.services.claude_service.generate_medication_extract",
        return_value=__import__(
            "dental_notes_backend.models.api_models", fromlist=["MedicationExtractResponse"]
        ).MedicationExtractResponse.model_validate(MED_FIXTURE),
    ):
        resp = client.post("/generate-note", json=_make_req("medication_extract"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["changes"][0]["drug_name"] == "amoxicillin"


def test_invalid_note_type(client):
    resp = client.post("/generate-note", json=_make_req("invalid_type"))
    assert resp.status_code == 422


def test_generate_note_claude_error(client):
    with patch(
        "dental_notes_backend.services.claude_service.generate_soap",
        side_effect=ValueError("Bad JSON"),
    ):
        resp = client.post("/generate-note", json=_make_req("soap"))
    assert resp.status_code == 422
