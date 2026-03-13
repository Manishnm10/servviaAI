"""
ServVia Temporal Reasoning Engine

Neurosymbolic temporal validation engine for pharmacovigilance.
Checks medication histories, washout periods, and symptom acuity
to validate remedy safety BEFORE LLM generation.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

from asgiref.sync import sync_to_async
from django.utils import timezone

from user_profile.models import UserProfile, MedicationHistory, SymptomOnset
from .constants import (
    MEDICATION_STABILIZATION_PERIODS,
    HERB_WASHOUT_PERIODS,
    SYMPTOM_ACUITY_THRESHOLDS,
    INTERACTION_TIME_WINDOWS,
    get_stabilization_period,
    get_washout_period,
    classify_acuity,
    get_interaction_timing,
)

logger = logging.getLogger(__name__)


@dataclass
class TemporalSafetyResult:
    """Result of temporal safety validation"""
    is_safe: bool
    herb_name: str
    user_id: str
    
    # Stabilization check results
    stabilization_violations: List[Dict] = field(default_factory=list)
    
    # Washout check results
    washout_violations: List[Dict] = field(default_factory=list)
    
    # Acuity assessment
    symptom_acuity: Dict[str, str] = field(default_factory=dict)
    
    # Cross-reactivity results
    allergy_warnings: List[str] = field(default_factory=list)
    
    # Overall assessment
    warnings: List[str] = field(default_factory=list)
    safety_recommendations: List[str] = field(default_factory=list)
    
    def add_warning(self, warning: str):
        """Add a safety warning to the result"""
        self.warnings.append(warning)
        self.is_safe = False
    
    def to_dict(self) -> Dict:
        """Convert result to dictionary for API responses"""
        return {
            'is_safe': self.is_safe,
            'herb_name': self.herb_name,
            'user_id': self.user_id,
            'stabilization_violations': self.stabilization_violations,
            'washout_violations': self.washout_violations,
            'symptom_acuity': self.symptom_acuity,
            'allergy_warnings': self.allergy_warnings,
            'warnings': self.warnings,
            'safety_recommendations': self.safety_recommendations,
            'violation_count': len(self.stabilization_violations) + len(self.washout_violations),
        }


class TemporalReasoningEngine:
    """
    Neurosymbolic temporal reasoning engine for pharmacovigilance.
    
    Validates remedy recommendations against:
    - Medication stabilization windows (e.g., new BP meds)
    - Herb washout periods (e.g., after stopping St. John's Wort)
    - Symptom acuity (acute vs chronic conditions)
    - Cross-reactivity patterns
    
    This engine runs BEFORE LLM generation to prevent dangerous recommendations.
    """
    
    def __init__(self):
        """Initialize the temporal reasoning engine"""
        logger.info("Temporal Reasoning Engine initialized")
    
    async def validate_safety_profile(
        self, 
        user_id: str, 
        herb_name: str,
        symptom_descriptions: Optional[List[str]] = None
    ) -> TemporalSafetyResult:
        """
        Main validation method - runs all temporal safety checks.
        ASYNC version for use in async pipeline.
        
        Args:
            user_id: User identifier (email)
            herb_name: Herb being recommended
            symptom_descriptions: Optional list of symptoms to check acuity
            
        Returns:
            TemporalSafetyResult with complete safety assessment
        """
        logger.info(f"Validating temporal safety for {user_id} - herb: {herb_name}")
        
        result = TemporalSafetyResult(
            is_safe=True,
            herb_name=herb_name,
            user_id=user_id
        )
        
        # Check medication stabilization (async)
        stab_violations = await self.check_medication_stabilization(user_id, herb_name)
        result.stabilization_violations = stab_violations
        for violation in stab_violations:
            result.add_warning(
                f"⚠️ Medication stabilization: {violation['medication']} started {violation['days_ago']} days ago. "
                f"Requires {violation['required_days']} days stabilization. "
                f"Risk: {violation['risk_description']}"
            )
            result.safety_recommendations.append(
                f"Wait {violation['days_remaining']} more days before using {herb_name} with {violation['medication']}"
            )
        
        # Check washout periods (async)
        washout_violations = await self.check_washout_period(user_id, herb_name)
        result.washout_violations = washout_violations
        for violation in washout_violations:
            result.add_warning(
                f"🚫 Washout violation: User stopped {violation['medication']} only {violation['days_since_stop']} days ago. "
                f"Requires {violation['required_washout']} days washout for {herb_name}. "
                f"Risk: {violation['risk_description']}"
            )
            result.safety_recommendations.append(
                f"Wait {violation['days_remaining']} more days before using {herb_name}"
            )
        
        # Assess symptom acuity if provided (async)
        if symptom_descriptions:
            for symptom in symptom_descriptions:
                acuity = await self.assess_symptom_acuity(user_id, symptom)
                result.symptom_acuity[symptom] = acuity
                
                # Add context-appropriate warnings based on acuity
                if acuity == 'acute' and herb_name.lower() in ['ashwagandha', 'ginseng']:
                    result.safety_recommendations.append(
                        f"For acute {symptom}: {herb_name} may be appropriate for short-term use"
                    )
        
        # Check allergy cross-reactivity (async)
        allergy_warnings = await self.check_allergy_cross_reactivity(user_id, herb_name)
        result.allergy_warnings = allergy_warnings
        for warning in allergy_warnings:
            result.add_warning(warning)
        
        # Set final safety status
        result.is_safe = len(result.warnings) == 0
        
        logger.info(
            f"Temporal validation complete for {user_id}: "
            f"{len(result.stabilization_violations)} stab violations, "
            f"{len(result.washout_violations)} washout violations, "
            f"safe={result.is_safe}"
        )
        
        return result
    
    def _sync_check_medication_stabilization(
        self, 
        user_id: str, 
        herb_name: str
    ) -> List[Dict]:
        """SYNC helper for medication stabilization DB operations."""
        violations = []
        herb_lower = herb_name.lower().replace(' ', '_')
        
        try:
            user = UserProfile.objects.get(email=user_id)
            
            # Get active medications started recently
            recent_meds = MedicationHistory.objects.filter(
                user=user,
                status__in=['active', 'paused'],
                start_date__gte=timezone.now() - timedelta(days=90)
            )
            
            for med in recent_meds:
                med_name = med.medication_name.lower()
                required_days = get_stabilization_period(med_name)
                days_on_med = (timezone.now() - med.start_date).days
                
                if days_on_med < required_days:
                    interaction = get_interaction_timing(herb_name, med_name)
                    
                    if interaction:
                        violations.append({
                            'medication': med.medication_name,
                            'generic_name': med.generic_name,
                            'days_ago': days_on_med,
                            'required_days': required_days,
                            'days_remaining': required_days - days_on_med,
                            'start_date': med.start_date.isoformat(),
                            'risk_description': interaction.get('mechanism', 'Unknown interaction mechanism'),
                            'severity': interaction.get('severity', 'HIGH'),
                            'interaction_timing': interaction.get('timing', {}).value if interaction.get('timing') else None,
                        })
        
        except UserProfile.DoesNotExist:
            logger.error(f"User not found: {user_id}")
        except Exception as e:
            logger.error(f"Error checking medication stabilization: {e}")
        
        return violations
    
    async def check_medication_stabilization(
        self, 
        user_id: str, 
        herb_name: str
    ) -> List[Dict]:
        """
        ASYNC: Check if user recently started medications that require stabilization.
        Wraps sync DB operations in thread pool.
        """
        return await sync_to_async(self._sync_check_medication_stabilization)(user_id, herb_name)
    
    def _sync_check_washout_period(self, user_id: str, herb_name: str) -> List[Dict]:
        """SYNC helper for washout period DB operations."""
        violations = []
        required_washout = get_washout_period(herb_name)
        
        if required_washout == 0:
            return violations
        
        try:
            user = UserProfile.objects.get(email=user_id)
            
            stopped_meds = MedicationHistory.objects.filter(
                user=user,
                status='discontinued',
                stop_date__gte=timezone.now() - timedelta(days=required_washout + 30)
            )
            
            for med in stopped_meds:
                days_since_stop = (timezone.now() - med.stop_date).days
                med_name = med.medication_name.lower()
                
                interaction = get_interaction_timing(herb_name, med_name)
                
                if interaction and days_since_stop < required_washout:
                    violations.append({
                        'medication': med.medication_name,
                        'generic_name': med.generic_name,
                        'days_since_stop': days_since_stop,
                        'required_washout': required_washout,
                        'days_remaining': required_washout - days_since_stop,
                        'stop_date': med.stop_date.isoformat(),
                        'reason_stopped': med.reason_for_discontinuation,
                        'risk_description': interaction.get('mechanism', 'Interaction risk persists during washout'),
                        'severity': interaction.get('severity', 'HIGH'),
                    })
        
        except UserProfile.DoesNotExist:
            logger.error(f"User not found: {user_id}")
        except Exception as e:
            logger.error(f"Error checking washout period: {e}")
        
        return violations
    
    async def check_washout_period(self, user_id: str, herb_name: str) -> List[Dict]:
        """ASYNC: Check if user recently stopped medications that require washout."""
        return await sync_to_async(self._sync_check_washout_period)(user_id, herb_name)
    
    def _sync_assess_symptom_acuity(self, user_id: str, symptom_description: str) -> str:
        """SYNC helper for symptom acuity DB operations."""
        try:
            user = UserProfile.objects.get(email=user_id)
            
            symptom_records = SymptomOnset.objects.filter(
                user=user,
                symptom_description__icontains=symptom_description[:20]
            ).order_by('-onset_date')
            
            if symptom_records.exists():
                record = symptom_records.first()
                days_since_onset = (timezone.now() - record.onset_date).days
                return classify_acuity(days_since_onset)
            else:
                return 'acute'
                
        except UserProfile.DoesNotExist:
            logger.error(f"User not found: {user_id}")
            return 'acute'
        except Exception as e:
            logger.error(f"Error assessing symptom acuity: {e}")
            return 'acute'
    
    async def assess_symptom_acuity(self, user_id: str, symptom_description: str) -> str:
        """ASYNC: Assess whether a symptom is acute, subacute, or chronic."""
        acuity = await sync_to_async(self._sync_assess_symptom_acuity)(user_id, symptom_description)
        logger.info(f"Symptom acuity for {user_id}: {symptom_description} = {acuity}")
        return acuity
    
    def _sync_check_allergy_cross_reactivity(self, user_id: str, herb_name: str) -> List[str]:
        """SYNC helper for allergy cross-reactivity DB operations."""
        warnings = []
        herb_lower = herb_name.lower()
        
        try:
            from user_profile.models import AllergyHistory
            from .constants import CROSS_REACTIVITY_WINDOWS
            
            user = UserProfile.objects.get(email=user_id)
            user_allergies = AllergyHistory.objects.filter(user=user)
            
            for allergy in user_allergies:
                allergen_lower = allergy.allergen.lower().replace(' ', '_')
                cross_reactive_data = CROSS_REACTIVITY_WINDOWS.get(allergen_lower)
                
                if cross_reactive_data:
                    cross_reactive_herbs = cross_reactive_data.get('cross_reactive', [])
                    
                    if herb_lower in [h.lower().replace(' ', '_') for h in cross_reactive_herbs]:
                        warnings.append(
                            f"⚠️ ALLERGY CROSS-REACTIVITY: User has {allergy.severity} "
                            f"{allergy.allergen} allergy which may cross-react with {herb_name}. "
                            f"Mechanism: {cross_reactive_data.get('mechanism', 'Unknown')}"
                        )
        
        except UserProfile.DoesNotExist:
            logger.error(f"User not found: {user_id}")
        except ImportError:
            logger.error("AllergyHistory model not available")
        except Exception as e:
            logger.error(f"Error checking allergy cross-reactivity: {e}")
        
        return warnings
    
    async def check_allergy_cross_reactivity(self, user_id: str, herb_name: str) -> List[str]:
        """ASYNC: Check for cross-reactive allergies that might affect herb safety."""
        return await sync_to_async(self._sync_check_allergy_cross_reactivity)(user_id, herb_name)
    
    def get_safety_window_summary(
        self, 
        user_id: str, 
        herb_name: str
    ) -> Dict:
        """
        Get a comprehensive safety window summary for a user-herb pair.
        Useful for UI displays showing when a herb will become safe.
        
        Returns dict with:
        - is_currently_safe: bool
        - next_safe_date: Optional[datetime]
        - blocking_medications: List[dict]
        - recommendations: List[str]
        """
        result = {
            'is_currently_safe': True,
            'next_safe_date': None,
            'blocking_medications': [],
            'recommendations': [],
        }
        
        # Check all violations
        safety_result = self.validate_safety_profile(user_id, herb_name)
        
        if safety_result.is_safe:
            return result
        
        result['is_currently_safe'] = False
        
        # Find the furthest out safety date
        latest_safe_dates = []
        
        for violation in safety_result.stabilization_violations:
            days_remaining = violation.get('days_remaining', 0)
            safe_date = datetime.now() + timedelta(days=days_remaining)
            latest_safe_dates.append(safe_date)
            result['blocking_medications'].append({
                'name': violation['medication'],
                'reason': 'stabilization_required',
                'days_remaining': days_remaining,
            })
        
        for violation in safety_result.washout_violations:
            days_remaining = violation.get('days_remaining', 0)
            safe_date = datetime.now() + timedelta(days=days_remaining)
            latest_safe_dates.append(safe_date)
            result['blocking_medications'].append({
                'name': violation['medication'],
                'reason': 'washout_required',
                'days_remaining': days_remaining,
            })
        
        if latest_safe_dates:
            result['next_safe_date'] = max(latest_safe_dates)
        
        result['recommendations'] = safety_result.safety_recommendations
        
        return result


# Global engine instance
_temporal_engine = None


def get_temporal_engine() -> TemporalReasoningEngine:
    """Get or create the global temporal reasoning engine instance"""
    global _temporal_engine
    if _temporal_engine is None:
        _temporal_engine = TemporalReasoningEngine()
    return _temporal_engine
