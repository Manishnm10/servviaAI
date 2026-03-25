"""
ServVia Temporal Safety Validator
=================================

A **deterministic, rule-based** pharmacovigilance engine that validates
proposed herbal remedies against a patient's medical profile. This module
contains ZERO LLM calls — every safety decision is made by hard-coded
clinical rules with known interaction databases and washout periods.

Architecture:
    1. Allergy Check       → Exact-match against patient allergens.
    2. Active Drug Check   → Cross-reference active meds vs interaction DB.
    3. Washout Period Check → Ensure sufficient time has elapsed after
                             stopping a conflicting medication.

The interaction database is structured as a nested dict mapping:
    herb → { drug_class → InteractionRule(severity, washout_days, reason) }

All matching is case-insensitive and uses canonical names.

Author: ServVia Engineering
Version: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from core.models import (
    InteractionSeverity,
    MedicationRecord,
    RemedyProposal,
    SafetyVerdict,
    UserMedicalProfile,
    ValidationResult,
)

logger = logging.getLogger("ServVia.TemporalValidator")


# =============================================================================
# INTERACTION RULE DATA STRUCTURE
# =============================================================================

@dataclass(frozen=True)
class InteractionRule:
    """
    A single herb-drug interaction rule.

    Attributes:
        drug_class: Canonical name of the drug or drug class.
        severity: How dangerous this interaction is.
        washout_days: Minimum days after stopping the drug before the herb
                      is considered safe. 0 = never safe while active.
        reason: Clinical explanation of the interaction mechanism.
        pmid: PubMed ID for the supporting evidence (if available).
    """
    drug_class: str
    severity: InteractionSeverity
    washout_days: int
    reason: str
    pmid: Optional[str] = None


# =============================================================================
# INTERACTION DATABASE (HARDCODED CLINICAL KNOWLEDGE)
# =============================================================================

# Structure: herb_name (lowercase) → List[InteractionRule]
# Each herb maps to one or more drug classes it may interact with.

INTERACTION_DATABASE: Dict[str, List[InteractionRule]] = {
    # -----------------------------------------------------------------
    # St. John's Wort — CYP3A4 inducer, extremely broad interactions
    # -----------------------------------------------------------------
    "st. john's wort": [
        InteractionRule(
            drug_class="ssri",
            severity=InteractionSeverity.CRITICAL,
            washout_days=14,
            reason=(
                "St. John's Wort combined with SSRIs can cause Serotonin "
                "Syndrome — a potentially fatal condition. The herb induces "
                "serotonin reuptake inhibition, compounding the SSRI effect. "
                "A 14-day washout is required after stopping the SSRI."
            ),
            pmid="PMC6970572",
        ),
        InteractionRule(
            drug_class="snri",
            severity=InteractionSeverity.CRITICAL,
            washout_days=14,
            reason=(
                "SNRIs (e.g., venlafaxine, duloxetine) carry the same "
                "Serotonin Syndrome risk as SSRIs when combined with "
                "St. John's Wort."
            ),
            pmid="PMC6970572",
        ),
        InteractionRule(
            drug_class="birth control",
            severity=InteractionSeverity.CRITICAL,
            washout_days=28,
            reason=(
                "St. John's Wort induces CYP3A4 liver enzymes, rapidly "
                "metabolizing oral contraceptives and causing breakthrough "
                "bleeding and contraceptive failure."
            ),
            pmid="PMC4500611",
        ),
        InteractionRule(
            drug_class="immunosuppressant",
            severity=InteractionSeverity.CRITICAL,
            washout_days=14,
            reason=(
                "CYP3A4 induction by St. John's Wort dramatically reduces "
                "immunosuppressant levels (cyclosporine, tacrolimus), "
                "risking organ transplant rejection."
            ),
            pmid="PMC3621465",
        ),
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.HIGH,
            washout_days=14,
            reason=(
                "St. John's Wort accelerates warfarin metabolism via "
                "CYP3A4/CYP2C9 induction, reducing INR and increasing "
                "thrombosis risk."
            ),
            pmid="PMC3621465",
        ),
        InteractionRule(
            drug_class="hiv medication",
            severity=InteractionSeverity.CRITICAL,
            washout_days=14,
            reason=(
                "Reduces protease inhibitor and NNRTI levels to sub-"
                "therapeutic concentrations, risking HIV treatment failure "
                "and resistance."
            ),
            pmid="PMC3621465",
        ),
    ],

    # -----------------------------------------------------------------
    # Grapefruit — CYP3A4 inhibitor
    # -----------------------------------------------------------------
    "grapefruit": [
        InteractionRule(
            drug_class="statin",
            severity=InteractionSeverity.HIGH,
            washout_days=3,
            reason=(
                "Grapefruit inhibits intestinal CYP3A4, causing toxic "
                "accumulation of statins (especially simvastatin and "
                "atorvastatin). Risk of rhabdomyolysis."
            ),
            pmid="PMC3589309",
        ),
        InteractionRule(
            drug_class="calcium channel blocker",
            severity=InteractionSeverity.HIGH,
            washout_days=3,
            reason=(
                "CYP3A4 inhibition increases calcium channel blocker "
                "levels, risking severe hypotension and reflex tachycardia."
            ),
            pmid="PMC3589309",
        ),
    ],

    # -----------------------------------------------------------------
    # Turmeric / Curcumin — antiplatelet + hypoglycemic
    # -----------------------------------------------------------------
    "turmeric": [
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Curcumin has antiplatelet activity that compounds "
                "warfarin's anticoagulant effect, significantly "
                "increasing bleeding risk."
            ),
            pmid="PMC3992385",
        ),
        InteractionRule(
            drug_class="blood thinner",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Curcumin inhibits platelet aggregation. Combined with "
                "any anticoagulant or antiplatelet agent, it creates "
                "compounded bleeding risk."
            ),
        ),
        InteractionRule(
            drug_class="diabetes medication",
            severity=InteractionSeverity.MODERATE,
            washout_days=3,
            reason=(
                "Curcumin can lower blood glucose levels, risking "
                "hypoglycemia when combined with diabetes medications."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Ginger — antiplatelet
    # -----------------------------------------------------------------
    "ginger": [
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Ginger inhibits thromboxane synthase, reducing platelet "
                "aggregation. Combined with warfarin, this substantially "
                "increases bleeding risk."
            ),
            pmid="PMC3583891",
        ),
        InteractionRule(
            drug_class="blood thinner",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Ginger's antiplatelet effects compound with any "
                "anticoagulant, increasing hemorrhage risk."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Valerian — CNS depressant
    # -----------------------------------------------------------------
    "valerian": [
        InteractionRule(
            drug_class="benzodiazepine",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Valerian acts on GABA receptors. Combining with "
                "benzodiazepines risks excessive sedation, respiratory "
                "depression, and cognitive impairment."
            ),
        ),
        InteractionRule(
            drug_class="sedative",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Additive CNS depression when combined with any sedative "
                "or sleep medication."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Ashwagandha — thyroid stimulant + sedative potentiator
    # -----------------------------------------------------------------
    "ashwagandha": [
        InteractionRule(
            drug_class="thyroid medication",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Ashwagandha stimulates thyroid hormone production "
                "(T3/T4), risking thyrotoxicosis in patients already on "
                "levothyroxine or similar thyroid replacement therapy."
            ),
        ),
        InteractionRule(
            drug_class="immunosuppressant",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Ashwagandha has immunostimulatory properties that may "
                "counteract immunosuppressive therapy."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Licorice — mineralocorticoid effect
    # -----------------------------------------------------------------
    "licorice": [
        InteractionRule(
            drug_class="blood pressure medication",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Glycyrrhizin causes sodium retention and potassium "
                "depletion, raising blood pressure and directly "
                "counteracting antihypertensive therapy."
            ),
        ),
        InteractionRule(
            drug_class="diuretic",
            severity=InteractionSeverity.HIGH,
            washout_days=5,
            reason=(
                "Licorice compounds potassium loss from diuretics, "
                "risking dangerous hypokalemia and cardiac arrhythmias."
            ),
        ),
        InteractionRule(
            drug_class="digoxin",
            severity=InteractionSeverity.CRITICAL,
            washout_days=7,
            reason=(
                "Licorice-induced hypokalemia sensitizes the heart "
                "to digoxin toxicity, risking fatal arrhythmias."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Kava — hepatotoxic
    # -----------------------------------------------------------------
    "kava": [
        InteractionRule(
            drug_class="benzodiazepine",
            severity=InteractionSeverity.CRITICAL,
            washout_days=14,
            reason=(
                "Kava has both hepatotoxic potential and CNS-depressant "
                "effects. Combined with benzodiazepines, it risks liver "
                "damage and severe sedation."
            ),
        ),
        InteractionRule(
            drug_class="acetaminophen",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Both kava and acetaminophen are hepatically metabolized. "
                "Co-administration amplifies liver damage risk."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Ginkgo — antiplatelet + seizure threshold
    # -----------------------------------------------------------------
    "ginkgo": [
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Ginkgo inhibits platelet activating factor (PAF), "
                "increasing bleeding risk when combined with warfarin."
            ),
        ),
        InteractionRule(
            drug_class="anticonvulsant",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Ginkgo can lower the seizure threshold, potentially "
                "reducing the efficacy of anticonvulsant medications."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Echinacea — immunostimulant
    # -----------------------------------------------------------------
    "echinacea": [
        InteractionRule(
            drug_class="immunosuppressant",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Echinacea stimulates immune function, theoretically "
                "counteracting immunosuppressive therapies used for "
                "organ transplants or autoimmune diseases."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Garlic — antiplatelet activity, CYP3A4 induction
    # -----------------------------------------------------------------
    "garlic": [
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Garlic inhibits platelet aggregation via ajoene and "
                "allicin, significantly increasing bleeding risk when "
                "combined with warfarin. Multiple case reports of elevated "
                "INR and spontaneous bleeding."
            ),
            pmid="PMC4032839",
        ),
        InteractionRule(
            drug_class="blood thinner",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Garlic's antiplatelet activity (ajoene, allicin) is "
                "additive with anticoagulants and antiplatelets, raising "
                "hemorrhagic risk."
            ),
            pmid="PMC4032839",
        ),
        InteractionRule(
            drug_class="hiv medication",
            severity=InteractionSeverity.MODERATE,
            washout_days=0,
            reason=(
                "Garlic supplements induce CYP3A4 and can reduce plasma "
                "levels of saquinavir and other protease inhibitors by "
                "up to 50%."
            ),
            pmid="11180024",
        ),
    ],

    # -----------------------------------------------------------------
    # Milk Thistle — CYP2C9 / CYP3A4 inhibition
    # -----------------------------------------------------------------
    "milk thistle": [
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.MODERATE,
            washout_days=5,
            reason=(
                "Silymarin (active constituent of milk thistle) inhibits "
                "CYP2C9, the primary metabolic pathway of S-warfarin. "
                "This can elevate INR and increase bleeding risk."
            ),
            pmid="PMC2763259",
        ),
        InteractionRule(
            drug_class="statin",
            severity=InteractionSeverity.MODERATE,
            washout_days=3,
            reason=(
                "Milk thistle inhibits CYP3A4 and OATP1B1 transport. "
                "Co-administration with statins (especially simvastatin, "
                "atorvastatin) can increase statin plasma levels, raising "
                "myopathy/rhabdomyolysis risk."
            ),
        ),
        InteractionRule(
            drug_class="diabetes medication",
            severity=InteractionSeverity.MODERATE,
            washout_days=0,
            reason=(
                "Silymarin has hypoglycemic activity. Combined with "
                "metformin or insulin, it may potentiate blood sugar "
                "lowering and increase hypoglycemia risk."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Saw Palmetto — CYP3A4 / CYP2C9 substrate competition
    # -----------------------------------------------------------------
    "saw palmetto": [
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.MODERATE,
            washout_days=5,
            reason=(
                "Saw palmetto has antiplatelet properties and may inhibit "
                "CYP2C9. Case reports document INR elevation and bleeding "
                "when co-administered with warfarin."
            ),
        ),
        InteractionRule(
            drug_class="blood thinner",
            severity=InteractionSeverity.MODERATE,
            washout_days=5,
            reason=(
                "Saw palmetto's antiplatelet activity is additive with "
                "other anticoagulants, increasing hemorrhagic risk."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Feverfew — antiplatelet, prostaglandin inhibition
    # -----------------------------------------------------------------
    "feverfew": [
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Feverfew inhibits platelet aggregation via parthenolide "
                "and prostaglandin synthesis inhibition. Combined with "
                "warfarin, this significantly elevates bleeding risk."
            ),
        ),
        InteractionRule(
            drug_class="blood thinner",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "Feverfew's antiplatelet mechanism is additive with "
                "anticoagulants and antiplatelet agents."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Dong Quai — coumarin content, CYP3A4 inhibition
    # -----------------------------------------------------------------
    "dong quai": [
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.CRITICAL,
            washout_days=10,
            reason=(
                "Dong quai contains natural coumarins that potentiate "
                "warfarin's anticoagulant effect. Case reports document "
                "INR >10 and serious bleeding. Co-administration is "
                "strictly contraindicated."
            ),
            pmid="9727078",
        ),
        InteractionRule(
            drug_class="blood thinner",
            severity=InteractionSeverity.HIGH,
            washout_days=7,
            reason=(
                "The coumarin content in dong quai is additive with "
                "all anticoagulant and antiplatelet agents."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Cranberry — CYP2C9 inhibition, warfarin potentiation
    # -----------------------------------------------------------------
    "cranberry": [
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.MODERATE,
            washout_days=3,
            reason=(
                "Cranberry juice/extract inhibits CYP2C9, the primary "
                "warfarin metabolic pathway. Large or sustained intake "
                "can elevate INR. Multiple case reports including one "
                "fatality documented by MHRA."
            ),
            pmid="PMC1884543",
        ),
    ],

    # -----------------------------------------------------------------
    # Chamomile — coumarin content, CYP1A2 / CYP3A4
    # -----------------------------------------------------------------
    "chamomile": [
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.MODERATE,
            washout_days=3,
            reason=(
                "Chamomile contains natural coumarins and inhibits "
                "CYP1A2. Concentrated chamomile tea or supplements "
                "can elevate INR when combined with warfarin."
            ),
        ),
        InteractionRule(
            drug_class="sedative",
            severity=InteractionSeverity.MODERATE,
            washout_days=0,
            reason=(
                "Chamomile has GABAergic sedative activity. Combined "
                "with sedatives or benzodiazepines, it may potentiate "
                "CNS depression."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Green Tea — vitamin K content, CYP3A4
    # -----------------------------------------------------------------
    "green tea": [
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.MODERATE,
            washout_days=0,
            reason=(
                "Green tea contains vitamin K which directly antagonizes "
                "warfarin's mechanism. Large or variable intake causes "
                "INR fluctuations. EGCG also inhibits CYP3A4."
            ),
        ),
        InteractionRule(
            drug_class="blood pressure medication",
            severity=InteractionSeverity.LOW,
            washout_days=0,
            reason=(
                "Caffeine in green tea can transiently raise blood "
                "pressure, potentially reducing antihypertensive efficacy."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Fenugreek — hypoglycemic, anticoagulant activity
    # -----------------------------------------------------------------
    "fenugreek": [
        InteractionRule(
            drug_class="diabetes medication",
            severity=InteractionSeverity.MODERATE,
            washout_days=0,
            reason=(
                "Fenugreek has significant hypoglycemic activity via "
                "4-hydroxyisoleucine. Combined with metformin or insulin, "
                "it can cause dangerous hypoglycemia."
            ),
            pmid="PMC3912882",
        ),
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.MODERATE,
            washout_days=3,
            reason=(
                "Fenugreek contains coumarin compounds and has "
                "anticoagulant activity. Co-administration with warfarin "
                "may potentiate bleeding risk."
            ),
        ),
    ],

    # -----------------------------------------------------------------
    # Cinnamon — CYP2C9, hypoglycemic
    # -----------------------------------------------------------------
    "cinnamon": [
        InteractionRule(
            drug_class="diabetes medication",
            severity=InteractionSeverity.MODERATE,
            washout_days=0,
            reason=(
                "Cinnamon (especially cassia variety) lowers blood glucose "
                "via enhanced insulin sensitivity. Combined with diabetes "
                "medications it may cause hypoglycemia."
            ),
        ),
        InteractionRule(
            drug_class="warfarin",
            severity=InteractionSeverity.LOW,
            washout_days=0,
            reason=(
                "Cassia cinnamon contains coumarin. High supplemental "
                "doses may have additive anticoagulant effect with warfarin."
            ),
        ),
    ],
}

# =============================================================================
# DRUG NAME ALIASES → CANONICAL DRUG CLASS MAPPING
# =============================================================================

# Maps common brand/generic names to the canonical drug_class used in
# INTERACTION_DATABASE. This enables matching "sertraline" → "ssri".

DRUG_CLASS_ALIASES: Dict[str, str] = {
    # SSRIs
    "sertraline": "ssri",
    "zoloft": "ssri",
    "fluoxetine": "ssri",
    "prozac": "ssri",
    "paroxetine": "ssri",
    "paxil": "ssri",
    "citalopram": "ssri",
    "celexa": "ssri",
    "escitalopram": "ssri",
    "lexapro": "ssri",
    "fluvoxamine": "ssri",
    "luvox": "ssri",
    # SNRIs
    "venlafaxine": "snri",
    "effexor": "snri",
    "duloxetine": "snri",
    "cymbalta": "snri",
    "desvenlafaxine": "snri",
    "pristiq": "snri",
    # Anticoagulants
    "warfarin": "warfarin",
    "coumadin": "warfarin",
    "jantoven": "warfarin",
    "heparin": "blood thinner",
    "enoxaparin": "blood thinner",
    "lovenox": "blood thinner",
    "rivaroxaban": "blood thinner",
    "xarelto": "blood thinner",
    "apixaban": "blood thinner",
    "eliquis": "blood thinner",
    "dabigatran": "blood thinner",
    "pradaxa": "blood thinner",
    "clopidogrel": "blood thinner",
    "plavix": "blood thinner",
    "aspirin": "blood thinner",
    "blood thinner": "blood thinner",
    "anticoagulant": "blood thinner",
    # Statins
    "atorvastatin": "statin",
    "lipitor": "statin",
    "simvastatin": "statin",
    "zocor": "statin",
    "rosuvastatin": "statin",
    "crestor": "statin",
    "pravastatin": "statin",
    "statin": "statin",
    "cholesterol medicine": "statin",
    # Calcium Channel Blockers
    "amlodipine": "calcium channel blocker",
    "norvasc": "calcium channel blocker",
    "nifedipine": "calcium channel blocker",
    "diltiazem": "calcium channel blocker",
    "verapamil": "calcium channel blocker",
    # Contraceptives
    "birth control": "birth control",
    "oral contraceptive": "birth control",
    "contraceptive": "birth control",
    # Thyroid
    "levothyroxine": "thyroid medication",
    "synthroid": "thyroid medication",
    "thyronorm": "thyroid medication",
    "eltroxin": "thyroid medication",
    "thyroid medication": "thyroid medication",
    # Benzodiazepines
    "diazepam": "benzodiazepine",
    "valium": "benzodiazepine",
    "alprazolam": "benzodiazepine",
    "xanax": "benzodiazepine",
    "lorazepam": "benzodiazepine",
    "ativan": "benzodiazepine",
    "clonazepam": "benzodiazepine",
    "klonopin": "benzodiazepine",
    "benzodiazepine": "benzodiazepine",
    # Sedatives
    "sedative": "sedative",
    "zolpidem": "sedative",
    "ambien": "sedative",
    "sleeping pill": "sedative",
    "sleep medication": "sedative",
    # Immunosuppressants
    "cyclosporine": "immunosuppressant",
    "tacrolimus": "immunosuppressant",
    "methotrexate": "immunosuppressant",
    "mycophenolate": "immunosuppressant",
    "immunosuppressant": "immunosuppressant",
    # Diabetes
    "metformin": "diabetes medication",
    "glucophage": "diabetes medication",
    "insulin": "diabetes medication",
    "glipizide": "diabetes medication",
    "glyburide": "diabetes medication",
    "diabetes medication": "diabetes medication",
    "sugar medicine": "diabetes medication",
    # Blood Pressure
    "lisinopril": "blood pressure medication",
    "losartan": "blood pressure medication",
    "atenolol": "blood pressure medication",
    "metoprolol": "blood pressure medication",
    "blood pressure medication": "blood pressure medication",
    "bp medicine": "blood pressure medication",
    "antihypertensive": "blood pressure medication",
    # Diuretics
    "furosemide": "diuretic",
    "lasix": "diuretic",
    "hydrochlorothiazide": "diuretic",
    "diuretic": "diuretic",
    # Digoxin
    "digoxin": "digoxin",
    "lanoxin": "digoxin",
    # Acetaminophen
    "acetaminophen": "acetaminophen",
    "paracetamol": "acetaminophen",
    "tylenol": "acetaminophen",
    # Anticonvulsants
    "carbamazepine": "anticonvulsant",
    "phenytoin": "anticonvulsant",
    "valproic acid": "anticonvulsant",
    "lamotrigine": "anticonvulsant",
    "anticonvulsant": "anticonvulsant",
    "seizure medication": "anticonvulsant",
    # HIV
    "saquinavir": "hiv medication",
    "ritonavir": "hiv medication",
    "efavirenz": "hiv medication",
    "hiv medication": "hiv medication",
}

# Herb name aliases for flexible matching
HERB_ALIASES: Dict[str, str] = {
    # ── St. John's Wort ──────────────────────────────────────────────
    "st john's wort": "st. john's wort",
    "st johns wort": "st. john's wort",
    "saint john's wort": "st. john's wort",
    "hypericum": "st. john's wort",
    "hypericum perforatum": "st. john's wort",
    # ── Turmeric ─────────────────────────────────────────────────────
    "curcumin": "turmeric",
    "curcuma": "turmeric",
    "curcuma longa": "turmeric",
    "haldi": "turmeric",
    "indian saffron": "turmeric",
    "turmeric root": "turmeric",
    "turmeric powder": "turmeric",
    "curcumin extract": "turmeric",
    "curcuminoid": "turmeric",
    "curcuminoids": "turmeric",
    # ── Ginger ───────────────────────────────────────────────────────
    "zingiber": "ginger",
    "zingiber officinale": "ginger",
    "adrak": "ginger",
    "sonth": "ginger",
    "ginger root": "ginger",
    "ground ginger": "ginger",
    "dried ginger": "ginger",
    # ── Garlic ───────────────────────────────────────────────────────
    "allium sativum": "garlic",
    "lahsun": "garlic",
    "garlic extract": "garlic",
    "aged garlic": "garlic",
    "garlic supplement": "garlic",
    # ── Ashwagandha ──────────────────────────────────────────────────
    "withania": "ashwagandha",
    "withania somnifera": "ashwagandha",
    "winter cherry": "ashwagandha",
    "indian ginseng": "ashwagandha",
    # ── Licorice ─────────────────────────────────────────────────────
    "mulethi": "licorice",
    "glycyrrhiza": "licorice",
    "glycyrrhiza glabra": "licorice",
    "licorice root": "licorice",
    "liquorice": "licorice",
    "yashtimadhu": "licorice",
    # ── Kava ─────────────────────────────────────────────────────────
    "piper methysticum": "kava",
    "kava kava": "kava",
    # ── Ginkgo ───────────────────────────────────────────────────────
    "ginkgo biloba": "ginkgo",
    "maidenhair tree": "ginkgo",
    "ginkgo extract": "ginkgo",
    # ── Echinacea ────────────────────────────────────────────────────
    "echinacea purpurea": "echinacea",
    "echinacea angustifolia": "echinacea",
    "purple coneflower": "echinacea",
    # ── Valerian ─────────────────────────────────────────────────────
    "valeriana": "valerian",
    "valeriana officinalis": "valerian",
    "valerian root": "valerian",
    "tagar": "valerian",
    # ── Grapefruit ───────────────────────────────────────────────────
    "grapefruit juice": "grapefruit",
    "citrus paradisi": "grapefruit",
    # ── Feverfew ─────────────────────────────────────────────────────
    "feverfew": "feverfew",
    "tanacetum parthenium": "feverfew",
    # ── Milk Thistle ─────────────────────────────────────────────────
    "silybum": "milk thistle",
    "silybum marianum": "milk thistle",
    "silymarin": "milk thistle",
    "milk thistle extract": "milk thistle",
    # ── Saw Palmetto ─────────────────────────────────────────────────
    "serenoa repens": "saw palmetto",
    "saw palmetto extract": "saw palmetto",
    # ── Dong Quai ────────────────────────────────────────────────────
    "dong quai": "dong quai",
    "angelica sinensis": "dong quai",
    "female ginseng": "dong quai",
    # ── Chamomile ────────────────────────────────────────────────────
    "matricaria chamomilla": "chamomile",
    "chamomile tea": "chamomile",
    "babune": "chamomile",
    # ── Green Tea ────────────────────────────────────────────────────
    "camellia sinensis": "green tea",
    "matcha": "green tea",
    "green tea extract": "green tea",
    "egcg": "green tea",
    # ── Aloe Vera ────────────────────────────────────────────────────
    "aloe barbadensis": "aloe vera",
    "ghritkumari": "aloe vera",
    "kumari": "aloe vera",
    # ── Fenugreek ────────────────────────────────────────────────────
    "trigonella foenum-graecum": "fenugreek",
    "methi": "fenugreek",
    "fenugreek seeds": "fenugreek",
    # ── Cinnamon ─────────────────────────────────────────────────────
    "cinnamomum": "cinnamon",
    "cinnamomum verum": "cinnamon",
    "dalchini": "cinnamon",
    # ── Neem ─────────────────────────────────────────────────────────
    "azadirachta indica": "neem",
    "nimba": "neem",
    "margosa": "neem",
    # ── Tulsi ────────────────────────────────────────────────────────
    "ocimum tenuiflorum": "tulsi",
    "ocimum sanctum": "tulsi",
    "holy basil": "tulsi",
    # ── Amla ─────────────────────────────────────────────────────────
    "phyllanthus emblica": "amla",
    "emblica officinalis": "amla",
    "indian gooseberry": "amla",
    "amalaki": "amla",
    # ── Elderberry ───────────────────────────────────────────────────
    "sambucus nigra": "elderberry",
    "elderberry extract": "elderberry",
    # ── Cranberry ────────────────────────────────────────────────────
    "cranberry": "cranberry",
    "vaccinium macrocarpon": "cranberry",
    "cranberry extract": "cranberry",
    "cranberry juice": "cranberry",
}


# =============================================================================
# TEMPORAL SAFETY VALIDATOR
# =============================================================================

class TemporalSafetyValidator:
    """
    Deterministic, rule-based pharmacovigilance engine.

    Validates proposed herbal remedies against a patient's medical profile
    using hard-coded clinical interaction rules and washout period logic.
    Contains **NO LLM calls** — all decisions are explainable and auditable.

    Validation Pipeline:
        1. **Allergy Check**: Exact substring match against declared allergens.
        2. **Active Medication Check**: Cross-reference active drugs against
           the interaction database using canonical drug class resolution.
        3. **Washout Period Check**: For stopped medications, verify that
           sufficient time has elapsed since the last dose.

    Usage:
        >>> from core.models import UserMedicalProfile, RemedyProposal, MedicationRecord
        >>> from datetime import datetime, timezone, timedelta
        >>>
        >>> validator = TemporalSafetyValidator()
        >>>
        >>> profile = UserMedicalProfile(
        ...     user_id="patient@example.com",
        ...     allergies=[],
        ...     current_medications=[
        ...         MedicationRecord(
        ...             drug_name="sertraline",
        ...             start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        ...             end_date=datetime(2026, 2, 20, tzinfo=timezone.utc),
        ...         )
        ...     ],
        ...     symptom_onset_hours=48,
        ... )
        >>>
        >>> proposal = RemedyProposal(
        ...     herb_or_remedy_name="St. John's Wort",
        ...     intended_effect="mood support",
        ... )
        >>>
        >>> result = validator.validate_remedy(profile, proposal)
        >>> result.is_safe
        False  # Washout period (14 days) not met
    """

    def __init__(
        self,
        interaction_db: Optional[Dict[str, List[InteractionRule]]] = None,
        drug_aliases: Optional[Dict[str, str]] = None,
        herb_aliases: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize the validator.

        Args:
            interaction_db: Override the default interaction database.
                            Useful for testing with custom rules.
            drug_aliases: Override the default drug-to-class alias map.
            herb_aliases: Override the default herb alias map.
        """
        self._interaction_db = interaction_db or INTERACTION_DATABASE
        self._drug_aliases = drug_aliases or DRUG_CLASS_ALIASES
        self._herb_aliases = herb_aliases or HERB_ALIASES
        logger.info(
            f"TemporalSafetyValidator initialized: "
            f"{len(self._interaction_db)} herbs, "
            f"{sum(len(v) for v in self._interaction_db.values())} rules, "
            f"{len(self._drug_aliases)} drug aliases"
        )

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def validate_remedy(
        self,
        profile: UserMedicalProfile,
        proposal: RemedyProposal,
        reference_time: Optional[datetime] = None,
    ) -> ValidationResult:
        """
        Validate a proposed remedy against the patient's medical profile.

        Runs the full safety pipeline:
            1. Allergy check
            2. Active medication interaction check
            3. Washout period check for stopped medications

        Args:
            profile: The patient's medical context.
            proposal: The remedy being proposed.
            reference_time: Override current time (for testing).

        Returns:
            ValidationResult with is_safe, confidence_score, and reason.
        """
        ref_time = reference_time or datetime.now(timezone.utc)
        herb_canonical = self._resolve_herb_name(proposal.herb_or_remedy_name)

        logger.info(
            f"Validating '{proposal.herb_or_remedy_name}' "
            f"(canonical: '{herb_canonical}') for user {profile.user_id}"
        )

        # ----- STEP 1: Allergy Check -----
        allergy_result = self._check_allergies(profile, herb_canonical, proposal)
        if allergy_result is not None:
            logger.warning(f"⛔ ALLERGY BLOCK: {allergy_result.reason}")
            return allergy_result

        # ----- STEP 2: Get interaction rules for this herb -----
        rules = self._interaction_db.get(herb_canonical, [])
        if not rules:
            logger.info(f"✅ No known interactions for '{herb_canonical}'.")
            return ValidationResult(
                is_safe=True,
                verdict=SafetyVerdict.SAFE,
                confidence_score=0.8,
                reason=(
                    f"No known drug interactions found for "
                    f"'{proposal.herb_or_remedy_name}' in the interaction "
                    f"database. General caution advised."
                ),
            )

        # ----- STEP 3: Check active medications -----
        active_block = self._check_active_medications(
            profile, herb_canonical, proposal, rules
        )
        if active_block is not None:
            logger.warning(f"⛔ ACTIVE MED BLOCK: {active_block.reason}")
            return active_block

        # ----- STEP 4: Check washout periods for stopped medications -----
        washout_block = self._check_washout_periods(
            profile, herb_canonical, proposal, rules, ref_time
        )
        if washout_block is not None:
            logger.warning(f"⏳ WASHOUT BLOCK: {washout_block.reason}")
            return washout_block

        # ----- All checks passed -----
        logger.info(
            f"✅ '{proposal.herb_or_remedy_name}' passed all safety checks "
            f"for user {profile.user_id}."
        )
        return ValidationResult(
            is_safe=True,
            verdict=SafetyVerdict.SAFE,
            confidence_score=1.0,
            reason=(
                f"'{proposal.herb_or_remedy_name}' has been checked against "
                f"{len(profile.current_medications)} medication(s) and "
                f"{len(profile.allergies)} allergen(s). No contraindications "
                f"detected."
            ),
        )

    # -------------------------------------------------------------------------
    # PRIVATE: ALLERGY CHECK
    # -------------------------------------------------------------------------

    def _check_allergies(
        self,
        profile: UserMedicalProfile,
        herb_canonical: str,
        proposal: RemedyProposal,
    ) -> Optional[ValidationResult]:
        """
        Check if the proposed herb matches any declared allergy.

        Uses substring matching in both directions to catch variations
        like "turmeric" matching an allergy of "curcumin/turmeric".

        Returns:
            ValidationResult if allergy detected, None otherwise.
        """
        for allergen in profile.allergies:
            if herb_canonical in allergen or allergen in herb_canonical:
                return ValidationResult(
                    is_safe=False,
                    verdict=SafetyVerdict.UNSAFE,
                    confidence_score=1.0,
                    reason=(
                        f"⛔ ALLERGY CONTRAINDICATION: "
                        f"'{proposal.herb_or_remedy_name}' matches declared "
                        f"allergy '{allergen}'. This remedy is strictly "
                        f"contraindicated."
                    ),
                    contraindications=[
                        f"Allergy: {allergen} ↔ {proposal.herb_or_remedy_name}"
                    ],
                )
        return None

    # -------------------------------------------------------------------------
    # PRIVATE: ACTIVE MEDICATION CHECK
    # -------------------------------------------------------------------------

    def _check_active_medications(
        self,
        profile: UserMedicalProfile,
        herb_canonical: str,
        proposal: RemedyProposal,
        rules: List[InteractionRule],
    ) -> Optional[ValidationResult]:
        """
        Check if the herb interacts with any currently active medication.

        Returns the MOST SEVERE interaction found. If multiple interactions
        exist, the one with the highest severity wins.

        Returns:
            ValidationResult if interaction found, None otherwise.
        """
        worst_interaction: Optional[Tuple[MedicationRecord, InteractionRule]] = None

        for med in profile.active_medications:
            drug_class = self._resolve_drug_class(med.drug_name)

            for rule in rules:
                if rule.drug_class == drug_class:
                    # Track the worst interaction
                    if worst_interaction is None or self._severity_rank(
                        rule.severity
                    ) > self._severity_rank(worst_interaction[1].severity):
                        worst_interaction = (med, rule)

        if worst_interaction is not None:
            med, rule = worst_interaction
            return ValidationResult(
                is_safe=False,
                verdict=SafetyVerdict.UNSAFE,
                confidence_score=1.0,
                reason=(
                    f"⛔ ACTIVE MEDICATION CONTRAINDICATION [{rule.severity.value.upper()}]: "
                    f"'{proposal.herb_or_remedy_name}' is contraindicated "
                    f"with '{med.drug_name}' (class: {rule.drug_class}). "
                    f"{rule.reason}"
                ),
                contraindications=[
                    f"{proposal.herb_or_remedy_name} × {med.drug_name} "
                    f"({rule.drug_class}) — {rule.severity.value}"
                ],
            )

        return None

    # -------------------------------------------------------------------------
    # PRIVATE: WASHOUT PERIOD CHECK
    # -------------------------------------------------------------------------

    def _check_washout_periods(
        self,
        profile: UserMedicalProfile,
        herb_canonical: str,
        proposal: RemedyProposal,
        rules: List[InteractionRule],
        reference_time: datetime,
    ) -> Optional[ValidationResult]:
        """
        Check if sufficient time has elapsed since stopping a conflicting drug.

        For each stopped medication, calculate days since last dose and
        compare against the required washout period.

        Returns:
            ValidationResult if washout incomplete, None otherwise.
        """
        worst_washout: Optional[
            Tuple[MedicationRecord, InteractionRule, int, int]
        ] = None  # (med, rule, days_since, days_remaining)

        for med in profile.stopped_medications:
            drug_class = self._resolve_drug_class(med.drug_name)
            days_since = self._calculate_days_since_last_dose(med, reference_time)

            for rule in rules:
                if rule.drug_class == drug_class:
                    days_remaining = rule.washout_days - days_since

                    if days_remaining > 0:
                        # Washout not met
                        if worst_washout is None or days_remaining > worst_washout[3]:
                            worst_washout = (med, rule, days_since, days_remaining)

        if worst_washout is not None:
            med, rule, days_since, days_remaining = worst_washout
            return ValidationResult(
                is_safe=False,
                verdict=SafetyVerdict.UNSAFE,
                confidence_score=1.0,
                reason=(
                    f"⏳ WASHOUT PERIOD NOT MET [{rule.severity.value.upper()}]: "
                    f"'{proposal.herb_or_remedy_name}' requires a "
                    f"{rule.washout_days}-day washout after stopping "
                    f"'{med.drug_name}' (class: {rule.drug_class}). "
                    f"Only {days_since} day(s) have elapsed — "
                    f"{days_remaining} day(s) remaining. "
                    f"{rule.reason}"
                ),
                contraindications=[
                    f"{proposal.herb_or_remedy_name} × {med.drug_name}: "
                    f"washout {days_since}/{rule.washout_days} days"
                ],
                washout_days_remaining=days_remaining,
            )

        return None

    # -------------------------------------------------------------------------
    # PRIVATE: HELPERS
    # -------------------------------------------------------------------------

    @staticmethod
    def _calculate_days_since_last_dose(
        med: MedicationRecord,
        reference_time: datetime,
    ) -> int:
        """
        Calculate the number of full days since the patient's last dose.

        Args:
            med: The medication record to check.
            reference_time: The current point in time.

        Returns:
            0 if the medication is currently active (no end_date).
            Otherwise, days elapsed since end_date.
        """
        return med.days_since_last_dose(reference_time)

    def _resolve_herb_name(self, name: str) -> str:
        """
        Resolve a herb name to its canonical form using the alias map.

        Args:
            name: Raw herb name (already lowercased by Pydantic).

        Returns:
            Canonical herb name from the interaction database.
        """
        return self._herb_aliases.get(name, name)

    def _resolve_drug_class(self, drug_name: str) -> str:
        """
        Resolve a specific drug name to its canonical class.

        Falls through to the drug name itself if no alias exists,
        enabling direct class names (e.g., "ssri") to work.

        Args:
            drug_name: Raw drug name (already lowercased by Pydantic).

        Returns:
            Canonical drug class string.
        """
        return self._drug_aliases.get(drug_name, drug_name)

    @staticmethod
    def _severity_rank(severity: InteractionSeverity) -> int:
        """
        Convert severity enum to integer for comparison.

        Returns:
            4=CRITICAL, 3=HIGH, 2=MODERATE, 1=LOW
        """
        return {
            InteractionSeverity.CRITICAL: 4,
            InteractionSeverity.HIGH: 3,
            InteractionSeverity.MODERATE: 2,
            InteractionSeverity.LOW: 1,
        }[severity]
