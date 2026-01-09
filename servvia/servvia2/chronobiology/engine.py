"""
ServVia 2. 0 - Chronobiological Engine
"""
from datetime import datetime
from typing import Dict, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Season(Enum):
    SHISHIRA = "late_winter"
    VASANTA = "spring"
    GRISHMA = "summer"
    VARSHA = "monsoon"
    SHARAD = "autumn"
    HEMANTA = "early_winter"


class CircadianEngine:
    
    def __init__(self):
        self.remedy_timing = {
            'digestive': {
                'best_time': 'Before meals',
                'optimal_hours': [7, 12, 18],
                'reason': 'Digestive fire is strongest around meal times'
            },
            'sleep_aid': {
                'best_time': '1-2 hours before bed',
                'optimal_hours': [21, 22],
                'reason': 'Allows herbs to take effect before sleep'
            },
            'anti_inflammatory': {
                'best_time': 'Morning',
                'optimal_hours': [6, 7, 8],
                'reason': 'Inflammatory markers peak in early morning'
            },
            'immune_booster': {
                'best_time': 'Evening',
                'optimal_hours': [18, 19, 20],
                'reason': 'Immune activity increases before sleep'
            },
            'adaptogen': {
                'best_time': 'Morning or evening',
                'optimal_hours': [7, 8, 20, 21],
                'reason': 'Morning for energy, evening for recovery'
            },
            'detox': {
                'best_time': 'Early morning empty stomach',
                'optimal_hours': [5, 6, 7],
                'reason': 'Liver detox is highest in early morning'
            },
            'respiratory': {
                'best_time': 'Morning and before bed',
                'optimal_hours': [7, 21],
                'reason': 'Clears airways for day and sleep'
            },
            'pain_relief': {
                'best_time': 'As needed',
                'optimal_hours': [8, 14, 21],
                'reason': 'Pain perception varies throughout day'
            }
        }
        
        self.seasonal_data = {
            Season.SHISHIRA: {
                'season_name': 'Late Winter (Jan-Feb)',
                'dosha_focus': 'Kapha accumulating - keep warm',
                'beneficial_herbs': ['Ginger', 'Cinnamon', 'Black Pepper', 'Garlic'],
                'diet_tips': ['Warm nourishing foods']
            },
            Season.VASANTA: {
                'season_name': 'Spring (Mar-Apr)',
                'dosha_focus': 'Kapha aggravated - lighten up',
                'beneficial_herbs': ['Turmeric', 'Tulsi', 'Neem', 'Triphala'],
                'diet_tips': ['Light warm dry foods']
            },
            Season. GRISHMA: {
                'season_name': 'Summer (May-Jun)',
                'dosha_focus': 'Pitta aggravating - stay cool',
                'beneficial_herbs': ['Aloe Vera', 'Mint', 'Coriander', 'Fennel'],
                'diet_tips': ['Cool liquid-rich foods']
            },
            Season. VARSHA: {
                'season_name': 'Monsoon (Jul-Aug)',
                'dosha_focus': 'Vata aggravated - aid digestion',
                'beneficial_herbs': ['Ginger', 'Cumin', 'Ajwain', 'Tulsi'],
                'diet_tips': ['Light easily digestible foods']
            },
            Season.SHARAD: {
                'season_name': 'Autumn (Sep-Oct)',
                'dosha_focus': 'Pitta still aggravated - balance',
                'beneficial_herbs': ['Amla', 'Shatavari', 'Brahmi', 'Fennel'],
                'diet_tips': ['Sweet light bitter foods']
            },
            Season. HEMANTA: {
                'season_name': 'Early Winter (Nov-Dec)',
                'dosha_focus': 'Strong digestion - build strength',
                'beneficial_herbs': ['Ashwagandha', 'Shatavari', 'Garlic', 'Ginger'],
                'diet_tips': ['Heavy nourishing foods']
            }
        }
        
        self.herb_types = {
            'ginger': 'digestive',
            'turmeric': 'anti_inflammatory',
            'ashwagandha': 'adaptogen',
            'chamomile': 'sleep_aid',
            'tulsi': 'immune_booster',
            'triphala': 'detox',
            'brahmi': 'adaptogen',
            'peppermint': 'pain_relief',
            'honey': 'immune_booster',
            'licorice': 'respiratory',
            'clove': 'pain_relief',
            'neem': 'detox',
            'amla': 'immune_booster',
            'fennel': 'digestive',
            'cumin': 'digestive',
            'cinnamon': 'digestive',
            'garlic': 'immune_booster',
            'giloy': 'immune_booster',
            'lavender': 'sleep_aid',
            'mint': 'digestive'
        }
    
    def get_current_season(self, latitude=20.0):
        month = datetime.now(). month
        if latitude < 0:
            month = (month + 5) % 12 + 1
        
        if month in [1, 2]:
            return Season.SHISHIRA
        elif month in [3, 4]:
            return Season.VASANTA
        elif month in [5, 6]:
            return Season. GRISHMA
        elif month in [7, 8]:
            return Season. VARSHA
        elif month in [9, 10]:
            return Season. SHARAD
        else:
            return Season.HEMANTA
    
    def get_seasonal_context(self, latitude=20.0):
        season = self. get_current_season(latitude)
        data = self.seasonal_data.get(season, {})
        return {
            'season': season. value,
            'season_name': data.get('season_name', ''),
            'dosha_focus': data.get('dosha_focus', ''),
            'beneficial_herbs': data.get('beneficial_herbs', []),
            'diet_tips': data.get('diet_tips', [])
        }
    
    def get_remedy_timing(self, remedy_type='digestive'):
        timing = self.remedy_timing.get(remedy_type, self.remedy_timing['digestive'])
        hours = timing.get('optimal_hours', [8])
        times = []
        for h in hours:
            if h < 12:
                times. append(str(h) + " AM")
            elif h == 12:
                times.append("12 PM")
            else:
                times. append(str(h - 12) + " PM")
        return {
            'best_time': timing['best_time'],
            'optimal_times': times,
            'reason': timing['reason']
        }
    
    def get_personalized_timing(self, herb_name):
        herb_lower = herb_name. lower()
        remedy_type = self.herb_types. get(herb_lower, 'digestive')
        timing = self.get_remedy_timing(remedy_type)
        return {
            'herb': herb_name,
            'remedy_type': remedy_type,
            'timing': timing
        }
    
    def format_timing_advice(self, herbs):
        if not herbs:
            return ""
        
        advice = "\n\n**When to Take Your Remedies:**\n\n"
        
        for herb in herbs[:3]:
            info = self.get_personalized_timing(herb)
            t = info['timing']
            herb_title = herb[0].upper() + herb[1:]. lower()
            advice = advice + "**" + herb_title + "**: " + t['best_time'] + "\n"
            advice = advice + "  Best times: " + ", ". join(t['optimal_times']) + "\n"
            advice = advice + "  _" + t['reason'] + "_\n\n"
        
        return advice
