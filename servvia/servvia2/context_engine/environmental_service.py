"""
ServVia 2. 0 - Environmental Context Engine
"""
import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


class EnvironmentalService:
    
    def get_season(self, latitude: float = 0) -> Dict:
        month = datetime.now(). month
        is_northern = latitude >= 0
        
        if month in [12, 1, 2]:
            season = 'winter' if is_northern else 'summer'
        elif month in [3, 4, 5]:
            season = 'spring' if is_northern else 'autumn'
        elif month in [6, 7, 8]:
            season = 'summer' if is_northern else 'winter'
        else:
            season = 'autumn' if is_northern else 'spring'
        
        ritucharya = {
            'winter': {'dosha': 'kapha', 'herbs': ['Ginger', 'Black Pepper', 'Cinnamon', 'Garlic']},
            'spring': {'dosha': 'kapha', 'herbs': ['Turmeric', 'Honey', 'Neem', 'Tulsi']},
            'summer': {'dosha': 'pitta', 'herbs': ['Peppermint', 'Coconut Oil', 'Aloe Vera', 'Fennel']},
            'autumn': {'dosha': 'vata', 'herbs': ['Ashwagandha', 'Ginger', 'Fenugreek', 'Licorice Root']},
        }
        
        return {
            'season': season,
            'month': month,
            'ritucharya': ritucharya. get(season, {}),
            'seasonal_herbs': ritucharya.get(season, {}).get('herbs', [])
        }
    
    def get_recommendations(self, season: str = None, aqi: int = None) -> Dict:
        recommendations = []
        warnings = []
        
        if aqi and aqi > 150:
            warnings. append("Poor air quality - limit outdoor activities")
            recommendations.extend([
                "Steam inhalation with eucalyptus",
                "Tulsi tea for respiratory support",
                "Stay hydrated"
            ])
        
        seasonal_tips = {
            'winter': ["Warm ginger tea", "Include warming spices", "Honey for immunity"],
            'spring': ["Light detox with turmeric", "Reduce heavy foods", "Neem for skin"],
            'summer': ["Cooling mint drinks", "Coconut oil for skin", "Avoid spicy foods"],
            'autumn': ["Grounding foods", "Ashwagandha for stress", "Warm sesame oil massage"],
        }
        
        if season:
            tips = seasonal_tips. get(season. lower(), [])
            recommendations.extend(tips)
        
        return {'recommendations': recommendations, 'warnings': warnings}
