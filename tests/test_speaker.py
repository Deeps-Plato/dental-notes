"""Tests for text-based speaker classification (3-way: Doctor/Patient/Assistant)."""

from dental_notes.session.speaker import classify_speaker


class TestClassifySpeakerDoctor:
    """Doctor classification via clinical terminology."""

    def test_clinical_text_classified_as_doctor(self):
        text = "I see the MOD amalgam on tooth 14 has a fracture line"
        assert classify_speaker(text) == "Doctor"

    def test_cdt_code_classified_as_doctor(self):
        text = "We'll do a zirconia crown, D2740, and prep today"
        assert classify_speaker(text) == "Doctor"

    def test_treatment_plan_classified_as_doctor(self):
        text = "The plan is scaling and root planing in all four quadrants"
        assert classify_speaker(text) == "Doctor"

    def test_instruction_classified_as_doctor(self):
        text = "Open wider please, and bite down on this"
        assert classify_speaker(text) == "Doctor"

    def test_diagnosis_classified_as_doctor(self):
        text = "I see Class II caries on number 14"
        assert classify_speaker(text) == "Doctor"


class TestClassifySpeakerPatient:
    """Patient classification via symptom/lay language."""

    def test_symptom_text_classified_as_patient(self):
        text = "My tooth hurts when I bite down, it's been bothering me"
        assert classify_speaker(text) == "Patient"

    def test_question_classified_as_patient(self):
        text = "How long will it take? Does insurance cover that?"
        assert classify_speaker(text) == "Patient"

    def test_acknowledgment_classified_as_patient(self):
        text = "Okay sounds good, thank you"
        assert classify_speaker(text) == "Patient"

    def test_patient_concern(self):
        text = "I noticed my gums have been bleeding when I brush"
        assert classify_speaker(text) == "Patient"


class TestClassifySpeakerAssistant:
    """Assistant classification via instrument/comfort/procedural/admin patterns."""

    def test_instrument_call_suction(self):
        text = "suction please"
        assert classify_speaker(text) == "Assistant"

    def test_patient_comfort(self):
        text = "you're doing great, almost done"
        assert classify_speaker(text) == "Assistant"

    def test_procedural_assist(self):
        text = "isolation complete"
        assert classify_speaker(text) == "Assistant"

    def test_charting_admin(self):
        text = "noted, which tooth?"
        assert classify_speaker(text) == "Assistant"

    def test_instrument_cotton_roll(self):
        text = "cotton roll, and pass the explorer"
        assert classify_speaker(text) == "Assistant"

    def test_comfort_rinse_and_spit(self):
        text = "rinse and spit, are you okay?"
        assert classify_speaker(text) == "Assistant"

    def test_procedural_ready(self):
        text = "ready for the impression, cement mixed"
        assert classify_speaker(text) == "Assistant"

    def test_admin_should_i(self):
        text = "should I get the shade guide? want me to check"
        assert classify_speaker(text) == "Assistant"


class TestClassifySpeakerTieBreaking:
    """Tie-breaking rules for ambiguous classification."""

    def test_assistant_doctor_tie_defaults_to_doctor(self):
        """When assistant and doctor scores tie, default to Doctor."""
        # Text with both doctor-like and assistant-like terms
        text = "suction, I see caries"
        result = classify_speaker(text)
        assert result == "Doctor"

    def test_ambiguous_alternates_from_doctor(self):
        text = "Yes, that's right"
        assert classify_speaker(text, prev_speaker="Doctor") == "Patient"

    def test_ambiguous_alternates_from_patient(self):
        text = "Yes, that's right"
        assert classify_speaker(text, prev_speaker="Patient") == "Doctor"

    def test_ambiguous_no_context_defaults_doctor(self):
        text = "Hello, good morning"
        assert classify_speaker(text) == "Doctor"

    def test_all_scores_zero_no_prev_defaults_doctor(self):
        """When all scores are 0 and no prev_speaker, default to Doctor."""
        text = "mmhmm"
        assert classify_speaker(text) == "Doctor"
