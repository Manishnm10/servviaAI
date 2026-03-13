"""
ServVia - Clean Response Formatter
"""

class ResponseFormatter:
    
    @staticmethod
    def format_remedy_card(remedy: dict, index: int) -> str:
        """Format a single remedy with full details"""
        scs = remedy. get('confidence_score', {})
        score = scs.get('score', 'N/A')
        emoji = scs.get('confidence_emoji', '')
        tier = scs.get('evidence_tier_label', 'N/A')
        studies = len(remedy.get('pubmed_ids', []))
        
        card = f"""
### {index}. {remedy['herb_name']} _{remedy. get('scientific_name', '')}_

{emoji} **Confidence: {score}/10** | {tier} | {studies} published study

**Why it helps:** {remedy.get('mechanism', 'Traditional remedy with historical use')}

{remedy.get('usage_instructions', '')}

"""
        return card
    
    @staticmethod
    def format_full_response(
        user_name: str,
        condition: str,
        remedies: list,
        env_context: dict,
        allergies: list = None,
        base_response: str = ""
    ) -> str:
        """Format complete clean response"""
        
        # Friendly greeting based on condition
        condition_greetings = {
            'headache': f"Hi {user_name}! I understand headaches can really disrupt your day. Here are some natural remedies that may bring you relief:",
            'cold': f"Hi {user_name}! Sorry to hear you're feeling under the weather. Let me share some remedies to help you recover faster:",
            'cough': f"Hi {user_name}! A persistent cough can be exhausting. Here are some soothing natural remedies:",
            'fever': f"Hi {user_name}! Fever is your body fighting back.  Here are some natural ways to support your recovery:",
            'anxiety': f"Hi {user_name}!  I understand anxiety can be overwhelming. Here are some calming natural remedies:",
            'insomnia': f"Hi {user_name}! Having trouble sleeping? These natural remedies may help you rest better:",
            'nausea': f"Hi {user_name}! Nausea is uncomfortable. Here are some gentle remedies to settle your stomach:",
            'stress': f"Hi {user_name}! We all face stress.  Here are some natural ways to find your calm:",
            'indigestion': f"Hi {user_name}! Digestive discomfort is no fun. Here are some remedies to help:",
            'sore throat': f"Hi {user_name}!  A sore throat can be painful. Here are some soothing remedies:",
            'toothache': f"Hi {user_name}!  Toothaches can be intense. Here are some natural pain relievers:",
        }
        
        response = condition_greetings. get(
            condition.lower(), 
            f"Hi {user_name}!  Here are some evidence-based natural remedies for {condition}:"
        )
        response += "\n\n"
        
        # Allergy notice
        if allergies:
            allergy_list = ", ".join(allergies)
            response += f"**Your Safety:** I've excluded remedies containing **{allergy_list}** based on your profile.\n\n"
        
        response += "---\n"
        
        # Remedy cards with full instructions
        if remedies:
            for i, remedy in enumerate(remedies[:3], 1):
                response += ResponseFormatter.format_remedy_card(remedy, i)
                response += "---\n"
        
        # Seasonal tip
        if env_context.get('season'):
            season = env_context['season'].title()
            seasonal_herbs = env_context.get('seasonal_herbs', [])
            
            if seasonal_herbs:
                safe_herbs = [h for h in seasonal_herbs if h. lower() not in [a.lower() for a in (allergies or [])]]
                if safe_herbs:
                    herbs_list = ", ".join(safe_herbs[:3])
                    response += f"\n**Seasonal Wellness ({season}):** {herbs_list} are especially beneficial this time of year.\n\n"
        
        # Confidence guide
        response += """
**What the Confidence Scores Mean:**

| | Score | Evidence Level |
|---|---|---|
| 🟢 | 8-10 | Strong clinical evidence |
| 🟡 | 5-7 | Good research support |
| 🔴 | 1-4 | Traditional use, limited studies |

"""
        
        # Safety footer
        response += "---\n\n"
        response += "**Remember:** These natural remedies complement professional medical care. If symptoms persist or worsen, please consult a healthcare provider.\n\n"
        response += "**Want to know more about any remedy?** Just ask me!"
        
        return response
