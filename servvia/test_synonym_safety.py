"""
ServVia Synonym Bypass Safety Test
====================================

Proves that the extraction → validation pipeline catches herb synonyms
that would previously have bypassed the safety engine.

Each test simulates an LLM response containing a synonym (e.g. "curcumin"
instead of "turmeric") and verifies:
  1. The extractor resolves it to the correct canonical name
  2. The safety validator flags the interaction with the user's medication

Run:
    cd servvia
    python manage.py test test_synonym_safety --verbosity=2
"""

import os, sys, re
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_core.settings")

import django
django.setup()

from django.test import TestCase
from datetime import datetime, timezone, timedelta

from neurosymbolic.temporal_validator import (
    TemporalSafetyValidator,
    HERB_ALIASES,
    INTERACTION_DATABASE,
)
from core.models import (
    UserMedicalProfile,
    MedicationRecord,
    RemedyProposal,
)

# Import the extraction functions from the pipeline
from api.views import (
    _extract_herbs_from_response,
    _extract_herbs_structured,
    _extract_herbs_regex,
    _substitute_flagged_remedies,
    _format_safety_inline_warning,
    _SYNONYM_TABLE,
    _ALLERGEN_SUBSTITUTE_MAP,
    _PRIMARY_SUBSTITUTE,
)


class TestSynonymTable(TestCase):
    """Verify the unified synonym table is correctly built."""

    def test_all_herb_aliases_present(self):
        """Every entry in HERB_ALIASES must appear in _SYNONYM_TABLE."""
        for alias, canonical in HERB_ALIASES.items():
            self.assertIn(
                alias.lower(), _SYNONYM_TABLE,
                f"HERB_ALIASES entry '{alias}' missing from _SYNONYM_TABLE"
            )
            self.assertEqual(
                _SYNONYM_TABLE[alias.lower()], canonical.lower(),
                f"'{alias}' should resolve to '{canonical}', "
                f"got '{_SYNONYM_TABLE.get(alias.lower())}'"
            )

    def test_all_interaction_db_herbs_present(self):
        """Every herb in INTERACTION_DATABASE must be in _SYNONYM_TABLE."""
        for herb in INTERACTION_DATABASE:
            self.assertIn(
                herb.lower(), _SYNONYM_TABLE,
                f"INTERACTION_DATABASE herb '{herb}' missing from _SYNONYM_TABLE"
            )

    def test_critical_synonyms_resolve(self):
        """Spot-check the most dangerous synonym gaps from the audit."""
        critical_cases = {
            "curcumin": "turmeric",
            "curcuma longa": "turmeric",
            "indian saffron": "turmeric",
            "haldi": "turmeric",
            "curcuminoids": "turmeric",
            "zingiber officinale": "ginger",
            "adrak": "ginger",
            "allium sativum": "garlic",
            "lahsun": "garlic",
            "hypericum perforatum": "st. john's wort",
            "silymarin": "milk thistle",
            "serenoa repens": "saw palmetto",
            "tanacetum parthenium": "feverfew",
            "angelica sinensis": "dong quai",
            "vaccinium macrocarpon": "cranberry",
        }
        for synonym, expected in critical_cases.items():
            self.assertEqual(
                _SYNONYM_TABLE.get(synonym.lower()), expected,
                f"'{synonym}' should resolve to '{expected}'"
            )


class TestRegexExtraction(TestCase):
    """Verify the regex fallback catches synonyms in free text."""

    def test_curcumin_in_remedy(self):
        response = (
            "## While Awaiting Medical Care\n"
            "**For inflammation:**\n"
            "- Remedy: Curcumin supplements (500mg twice daily)\n"
            "- Why it helps: Anti-inflammatory properties\n"
        )
        herbs = _extract_herbs_regex(response)
        self.assertIn("turmeric", herbs)

    def test_indian_saffron_in_remedy(self):
        response = "Try adding Indian saffron paste to warm milk for joint relief."
        herbs = _extract_herbs_regex(response)
        self.assertIn("turmeric", herbs)

    def test_zingiber_in_remedy(self):
        response = "Brew Zingiber officinale root in hot water for 10 minutes."
        herbs = _extract_herbs_regex(response)
        self.assertIn("ginger", herbs)

    def test_allium_sativum_in_remedy(self):
        response = "Crush fresh Allium sativum cloves and consume with honey."
        herbs = _extract_herbs_regex(response)
        self.assertIn("garlic", herbs)

    def test_silymarin_in_remedy(self):
        response = "Consider silymarin capsules for liver support."
        herbs = _extract_herbs_regex(response)
        self.assertIn("milk thistle", herbs)

    def test_disclaimer_lines_excluded(self):
        """Herbs in allergy disclaimers must NOT be extracted."""
        response = (
            "## Remedies\n"
            "- Remedy: Ginger tea\n"
            "Please avoid any remedies containing honey due to your allergy.\n"
        )
        herbs = _extract_herbs_regex(response)
        self.assertIn("ginger", herbs)
        self.assertNotIn("honey", herbs)

    def test_multiple_synonyms_in_one_response(self):
        response = (
            "Try curcumin extract and Zingiber tea together.\n"
            "Also consider Allium sativum for immune support.\n"
        )
        herbs = _extract_herbs_regex(response)
        self.assertIn("turmeric", herbs)
        self.assertIn("ginger", herbs)
        self.assertIn("garlic", herbs)


class TestStructuredExtraction(TestCase):
    """Verify the primary structured HERBS_USED tag parser."""

    def test_basic_tag(self):
        response = (
            "Here are some remedies...\n"
            "<!-- HERBS_USED: ginger, turmeric, honey -->"
        )
        herbs = _extract_herbs_structured(response)
        self.assertEqual(herbs, {"ginger", "turmeric", "honey"})

    def test_synonyms_in_tag_resolved(self):
        response = "<!-- HERBS_USED: curcumin, zingiber, allium sativum -->"
        herbs = _extract_herbs_structured(response)
        self.assertIn("turmeric", herbs)
        self.assertIn("ginger", herbs)
        self.assertIn("garlic", herbs)

    def test_no_tag_returns_empty(self):
        response = "Here are some remedies with ginger and turmeric."
        herbs = _extract_herbs_structured(response)
        self.assertEqual(herbs, set())

    def test_none_tag(self):
        response = "No herbal remedies needed.\n<!-- HERBS_USED: none -->"
        herbs = _extract_herbs_structured(response)
        # "none" is not a real herb, should resolve to itself and be harmless
        self.assertNotIn("ginger", herbs)


class TestUnifiedExtraction(TestCase):
    """Verify the union of structured + regex extraction."""

    def test_structured_and_regex_union(self):
        """If structured tag says ginger but text also has curcumin,
        both should be caught."""
        response = (
            "Try curcumin extract for inflammation.\n"
            "<!-- HERBS_USED: ginger -->"
        )
        herbs = _extract_herbs_from_response(response)
        self.assertIn("ginger", herbs)
        self.assertIn("turmeric", herbs)  # caught by regex

    def test_regex_fallback_when_no_tag(self):
        """If LLM omits the tag, regex must still catch everything."""
        response = "Brew fresh adrak in hot water. Add haldi paste."
        herbs = _extract_herbs_from_response(response)
        self.assertIn("ginger", herbs)    # adrak → ginger
        self.assertIn("turmeric", herbs)  # haldi → turmeric


class TestEndToEndSafetyBlock(TestCase):
    """
    The critical test: simulate the EXACT scenario from the IEEE review.

    User is on Warfarin. LLM recommends "curcumin supplements".
    Old system: curcumin not in scan list → empty extraction → "safe".
    New system: curcumin → turmeric → warfarin interaction → BLOCKED.
    """

    def setUp(self):
        self.validator = TemporalSafetyValidator()
        self.warfarin_user = UserMedicalProfile(
            user_id="test-warfarin-patient",
            allergies=[],
            current_medications=[
                MedicationRecord(
                    drug_name="warfarin",
                    start_date=datetime.now(timezone.utc) - timedelta(days=90),
                    end_date=None,
                )
            ],
            symptom_onset_hours=0,
        )

    def _assert_flagged(self, response_text: str, expected_canonical: str):
        """Extract herbs from response, validate against warfarin profile,
        assert the expected herb is flagged as unsafe."""
        herbs = _extract_herbs_from_response(response_text)
        self.assertIn(
            expected_canonical, herbs,
            f"Extractor failed to find '{expected_canonical}' in: {response_text[:80]}"
        )
        proposal = RemedyProposal(
            herb_or_remedy_name=expected_canonical,
            intended_effect="LLM-recommended remedy",
        )
        result = self.validator.validate_remedy(self.warfarin_user, proposal)
        self.assertFalse(
            result.is_safe,
            f"'{expected_canonical}' (from response) should be UNSAFE with warfarin. "
            f"Got: is_safe={result.is_safe}, reason={result.reason}"
        )

    def test_curcumin_blocked_for_warfarin(self):
        self._assert_flagged(
            "Take curcumin supplements (500mg twice daily) for inflammation.",
            "turmeric",
        )

    def test_indian_saffron_blocked_for_warfarin(self):
        self._assert_flagged(
            "Mix Indian saffron with warm milk before bedtime.",
            "turmeric",
        )

    def test_haldi_blocked_for_warfarin(self):
        self._assert_flagged(
            "Add a pinch of haldi to your dal for anti-inflammatory benefits.",
            "turmeric",
        )

    def test_curcuma_longa_blocked_for_warfarin(self):
        self._assert_flagged(
            "Curcuma longa extract is beneficial for joint health.",
            "turmeric",
        )

    def test_garlic_blocked_for_warfarin(self):
        self._assert_flagged(
            "Consume 2 cloves of raw garlic daily for cardiovascular health.",
            "garlic",
        )

    def test_allium_sativum_blocked_for_warfarin(self):
        self._assert_flagged(
            "Allium sativum supplements may support heart health.",
            "garlic",
        )

    def test_ginger_blocked_for_warfarin(self):
        self._assert_flagged(
            "Drink fresh ginger tea three times daily.",
            "ginger",
        )

    def test_zingiber_blocked_for_warfarin(self):
        self._assert_flagged(
            "Steep Zingiber officinale root in boiling water.",
            "ginger",
        )

    def test_feverfew_blocked_for_warfarin(self):
        self._assert_flagged(
            "Feverfew capsules may help with migraine prevention.",
            "feverfew",
        )

    def test_dong_quai_blocked_for_warfarin(self):
        self._assert_flagged(
            "Try dong quai tea for menstrual discomfort.",
            "dong quai",
        )

    def test_angelica_sinensis_blocked_for_warfarin(self):
        self._assert_flagged(
            "Angelica sinensis is traditionally used for blood tonification.",
            "dong quai",
        )

    def test_cranberry_flagged_for_warfarin(self):
        self._assert_flagged(
            "Drink cranberry juice daily for urinary tract health.",
            "cranberry",
        )

    def test_milk_thistle_flagged_for_warfarin(self):
        self._assert_flagged(
            "Silymarin capsules support liver detoxification.",
            "milk thistle",
        )

    def test_ginkgo_blocked_for_warfarin(self):
        self._assert_flagged(
            "Ginkgo biloba may improve cognitive function.",
            "ginkgo",
        )

    def test_chamomile_flagged_for_warfarin(self):
        self._assert_flagged(
            "Drink chamomile tea before bed for relaxation.",
            "chamomile",
        )

    def test_fenugreek_flagged_for_warfarin(self):
        self._assert_flagged(
            "Soak methi seeds overnight and drink the water in the morning.",
            "fenugreek",
        )

    def test_green_tea_flagged_for_warfarin(self):
        self._assert_flagged(
            "Matcha powder provides concentrated EGCG for antioxidant support.",
            "green tea",
        )

    def test_structured_tag_catches_synonym(self):
        """Even if the LLM body uses a synonym, the structured tag
        should catch it when the LLM correctly declares it."""
        response = (
            "Take curcumin extract daily.\n"
            "<!-- HERBS_USED: turmeric -->"
        )
        self._assert_flagged(response, "turmeric")

    def test_ssri_user_st_johns_wort_variants(self):
        """All St. John's Wort synonyms must be caught for SSRI users."""
        ssri_user = UserMedicalProfile(
            user_id="test-ssri-patient",
            allergies=[],
            current_medications=[
                MedicationRecord(
                    drug_name="sertraline",
                    start_date=datetime.now(timezone.utc) - timedelta(days=30),
                    end_date=None,
                )
            ],
            symptom_onset_hours=0,
        )
        variants = [
            ("Saint John's Wort tea can help with mild depression.", "st. john's wort"),
            ("Hypericum perforatum extract is a natural mood lifter.", "st. john's wort"),
            ("Try st johns wort capsules for seasonal mood changes.", "st. john's wort"),
        ]
        for response_text, canonical in variants:
            herbs = _extract_herbs_from_response(response_text)
            self.assertIn(canonical, herbs, f"Failed to extract from: {response_text}")
            proposal = RemedyProposal(
                herb_or_remedy_name=canonical,
                intended_effect="LLM-recommended remedy",
            )
            result = self.validator.validate_remedy(ssri_user, proposal)
            self.assertFalse(
                result.is_safe,
                f"'{canonical}' should be CRITICAL with sertraline (SSRI). "
                f"Response: {response_text}"
            )


class TestRemedySubstitution(TestCase):
    """Verify that flagged herbs are replaced with safe substitutes in remedy text."""

    def setUp(self):
        self.validator = TemporalSafetyValidator()
        self.aspirin_user = UserMedicalProfile(
            user_id="test-substitution-patient",
            allergies=[],
            current_medications=[
                MedicationRecord(
                    drug_name="aspirin",
                    start_date=datetime.now(timezone.utc) - timedelta(days=90),
                    end_date=None,
                )
            ],
            symptom_onset_hours=0,
        )

    def _get_flagged(self, herb_name):
        proposal = RemedyProposal(
            herb_or_remedy_name=herb_name,
            intended_effect="LLM-recommended remedy",
        )
        result = self.validator.validate_remedy(self.aspirin_user, proposal)
        return [(herb_name, result)]

    def test_herb_replaced_in_heading(self):
        """Ginger in a remedy heading must be replaced with cinnamon."""
        response = (
            "## Personalized Home Remedies\n"
            "**Remedy 1: Ginger and Tulsi Tea**\n"
            "- What you need: 1 tsp ginger\n"
            "- How to use: Drink warm\n"
        )
        flagged = self._get_flagged("ginger")
        result = _substitute_flagged_remedies(response, flagged)

        # Ginger must be gone from remedy text
        self.assertNotIn("Ginger", result)
        self.assertNotIn("ginger", result)
        # Cinnamon must be present (primary substitute for ginger)
        primary = _PRIMARY_SUBSTITUTE["ginger"]
        self.assertIn(primary, result.lower())

    def test_case_preserved_in_heading(self):
        """Title-case 'Ginger' should become 'Cinnamon', lowercase stays lowercase."""
        response = (
            "**Remedy 1: Ginger Tea**\n"
            "- What you need: fresh ginger root\n"
        )
        flagged = self._get_flagged("ginger")
        result = _substitute_flagged_remedies(response, flagged)

        # Title case preserved
        self.assertIn("Cinnamon", result)
        # Lowercase preserved
        self.assertIn("cinnamon", result)

    def test_unflagged_herbs_untouched(self):
        """Herbs that are NOT flagged must remain unchanged."""
        response = (
            "**Remedy 1: Ginger Tea**\n"
            "- Use ginger root\n\n"
            "**Remedy 2: Tulsi and Eucalyptus Steam**\n"
            "- Use tulsi leaves and eucalyptus oil\n"
        )
        flagged = self._get_flagged("ginger")
        result = _substitute_flagged_remedies(response, flagged)

        # Ginger replaced
        self.assertNotIn("ginger", result.lower())
        # Tulsi and eucalyptus untouched
        self.assertIn("tulsi", result.lower())
        self.assertIn("eucalyptus", result.lower())

    def test_trust_engine_section_also_substituted(self):
        """Herb names in the Scientific Validation section must also be replaced."""
        response = (
            "**Remedy 1: Ginger Tea**\n"
            "- Use ginger\n\n"
            "---\n"
            "## \U0001f52c Scientific Validation (Trust Engine)\n"
            "Ginger \U0001f7e1 6.3/10 Evidence: Review\n"
        )
        flagged = self._get_flagged("ginger")
        result = _substitute_flagged_remedies(response, flagged)

        # Ginger replaced everywhere
        self.assertNotIn("Ginger", result)
        self.assertNotIn("ginger", result)
        primary = _PRIMARY_SUBSTITUTE["ginger"]
        self.assertIn(primary[0].upper() + primary[1:], result)

    def test_summary_alert_states_substitution(self):
        """The Ingredient Alert must say X was substituted in place of Y
        with a human-friendly reason."""
        flagged = self._get_flagged("ginger")
        alert = _format_safety_inline_warning(flagged)

        primary = _PRIMARY_SUBSTITUTE["ginger"].title()
        self.assertIn(f"**{primary}** was substituted in place of **Ginger**", alert)
        self.assertIn("Ingredient Alert", alert)
        # Human-friendly reason (not raw validator output)
        self.assertIn("thin the blood", alert)
        self.assertIn("risk of bleeding", alert)
        # Must NOT contain raw validator format
        self.assertNotIn("(class:", alert)
        self.assertNotIn("CONTRAINDICATION", alert)
        # Full alternatives list
        self.assertIn("Other safe alternatives", alert)
        alternatives = _ALLERGEN_SUBSTITUTE_MAP["ginger"]
        self.assertIn(alternatives, alert)

    def test_path_b_serious_remedy_substitution(self):
        """For serious-path responses (Path B), herb names in the
        symptom relief section must be replaced."""
        response = (
            "## While Awaiting Medical Care\n"
            "**For Pain:**\n"
            "- Remedy: Warm ginger tea\n"
            "- How to use: Steep 1 tsp ginger\n\n"
            "**For Fatigue:**\n"
            "- Remedy: Lemon water with jaggery\n"
        )
        flagged = self._get_flagged("ginger")
        result = _substitute_flagged_remedies(response, flagged)

        # Ginger replaced in pain remedy
        self.assertNotIn("ginger", result.lower())
        primary = _PRIMARY_SUBSTITUTE["ginger"]
        self.assertIn(primary, result.lower())
        # Jaggery (unflagged) untouched
        self.assertIn("jaggery", result.lower())

    def test_multiple_herbs_substituted(self):
        """When multiple herbs are flagged, each gets its own substitute."""
        response = (
            "**Remedy 1: Ginger Tea**\n"
            "- Use ginger\n\n"
            "**Remedy 2: Garlic Soup**\n"
            "- Use garlic\n"
        )
        flagged_ginger = self._get_flagged("ginger")
        flagged_garlic = self._get_flagged("garlic")
        all_flagged = flagged_ginger + flagged_garlic
        result = _substitute_flagged_remedies(response, all_flagged)

        self.assertNotIn("ginger", result.lower())
        self.assertNotIn("garlic", result.lower())
        self.assertIn(_PRIMARY_SUBSTITUTE["ginger"], result.lower())
        self.assertIn(_PRIMARY_SUBSTITUTE["garlic"].lower(), result.lower())
