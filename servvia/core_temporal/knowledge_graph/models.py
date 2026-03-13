"""
ServVia - Knowledge Graph Models
"""
import logging

logger = logging.getLogger(__name__)

HERBS_DATA = {}
DISEASES_DATA = {}
EVIDENCE_DATA = {}


class EvidenceTier:
    TIER_CHOICES = {
        1: 'Tier 1: Clinical Trial',
        2: 'Tier 2: Mechanistic',
        3: 'Tier 3: Traditional Use',
        4: 'Tier 4: Anecdotal',
        5: 'Tier 5: Theoretical',
    }
    TIER_WEIGHTS = {1: 1.0, 2: 0.75, 3: 0.5, 4: 0.25, 5: 0.0}


class HerbRepository:
    
    @staticmethod
    def create(name, scientific_name, description='', properties=None, 
               contraindications=None, usage_instructions=''):
        global HERBS_DATA
        herb_id = len(HERBS_DATA) + 1
        HERBS_DATA[herb_id] = {
            'id': herb_id,
            'name': name,
            'scientific_name': scientific_name,
            'description': description,
            'properties': properties or [],
            'contraindications': contraindications or [],
            'usage_instructions': usage_instructions,
        }
        return HERBS_DATA[herb_id]
    
    @staticmethod
    def get_by_name(name):
        for herb in HERBS_DATA.values():
            if herb['name'].lower() == name.lower():
                return herb
        return None
    
    @staticmethod
    def get_by_id(herb_id):
        return HERBS_DATA. get(herb_id)
    
    @staticmethod
    def update_by_name(name, updates):
        for herb_id, herb in HERBS_DATA.items():
            if herb['name'].lower() == name.lower():
                HERBS_DATA[herb_id].update(updates)
                return HERBS_DATA[herb_id]
        return None


class DiseaseRepository:
    
    @staticmethod
    def create(name, icd_code='', symptoms=None):
        global DISEASES_DATA
        disease_id = len(DISEASES_DATA) + 1
        DISEASES_DATA[disease_id] = {
            'id': disease_id,
            'name': name,
            'icd_code': icd_code,
            'symptoms': symptoms or [],
        }
        return DISEASES_DATA[disease_id]
    
    @staticmethod
    def get_by_name(name):
        for disease in DISEASES_DATA.values():
            if disease['name'].lower() == name.lower():
                return disease
        return None
    
    @staticmethod
    def get_by_id(disease_id):
        return DISEASES_DATA. get(disease_id)


class EvidenceRepository:
    
    @staticmethod
    def create(herb_id, disease_id, evidence_tier, pubmed_ids=None, mechanism=''):
        global EVIDENCE_DATA
        evidence_id = len(EVIDENCE_DATA) + 1
        EVIDENCE_DATA[evidence_id] = {
            'id': evidence_id,
            'herb_id': herb_id,
            'disease_id': disease_id,
            'evidence_tier': evidence_tier,
            'pubmed_ids': pubmed_ids or [],
            'mechanism': mechanism,
        }
        return EVIDENCE_DATA[evidence_id]
    
    @staticmethod
    def get_remedies_for_condition(condition, exclude_ingredients=None):
        exclude_ingredients = exclude_ingredients or []
        exclude_lower = [i.lower() for i in exclude_ingredients]
        
        disease = DiseaseRepository.get_by_name(condition)
        if not disease:
            return []
        
        remedies = []
        for evidence in EVIDENCE_DATA.values():
            if evidence['disease_id'] == disease['id']:
                herb = HerbRepository. get_by_id(evidence['herb_id'])
                if herb and herb['name'].lower() not in exclude_lower:
                    remedies. append({
                        'herb_id': herb['id'],
                        'herb_name': herb['name'],
                        'scientific_name': herb['scientific_name'],
                        'description': herb. get('description', ''),
                        'properties': herb.get('properties', []),
                        'contraindications': herb. get('contraindications', []),
                        'usage_instructions': herb.get('usage_instructions', ''),
                        'evidence_tier': evidence['evidence_tier'],
                        'evidence_tier_label': EvidenceTier.TIER_CHOICES. get(evidence['evidence_tier'], 'Unknown'),
                        'pubmed_ids': evidence['pubmed_ids'],
                        'mechanism': evidence['mechanism'],
                    })
        
        remedies.sort(key=lambda x: x['evidence_tier'])
        return remedies


def seed_knowledge_graph():
    """Seed the knowledge graph with herbs, diseases, and evidence"""
    global HERBS_DATA, DISEASES_DATA, EVIDENCE_DATA
    
    if HERBS_DATA:
        return
    
    print("Seeding herbs...")
    
    # Herbs with detailed usage instructions
    herbs = [
        {
            'name': 'Ginger',
            'scientific_name': 'Zingiber officinale',
            'description': 'A warming root with powerful anti-inflammatory and digestive properties.',
            'properties': ['anti-inflammatory', 'antiemetic', 'digestive'],
            'contraindications': ['blood thinners', 'gallstones'],
            'usage_instructions': '''**How to Use Ginger:**
1. **Fresh Ginger Tea:** Slice 1-inch fresh ginger, boil in 2 cups water for 10 minutes.  Strain and add honey. 
2. **Ginger Compress:** Grate fresh ginger, wrap in cloth, apply to affected area for 15-20 minutes. 
3. **Chewing:** Chew a small piece of fresh ginger slowly for nausea relief. 
**Dosage:** 1-2 cups of tea daily, or 1-2 grams of fresh ginger. '''
        },
        {
            'name': 'Turmeric',
            'scientific_name': 'Curcuma longa',
            'description': 'Golden spice with potent anti-inflammatory and antioxidant properties.',
            'properties': ['anti-inflammatory', 'antioxidant', 'antimicrobial'],
            'contraindications': ['gallbladder problems', 'blood thinners'],
            'usage_instructions': '''**How to Use Turmeric:**
1. **Golden Milk:** Mix 1 tsp turmeric powder in warm milk with a pinch of black pepper.  Drink before bed.
2.  **Turmeric Paste:** Mix turmeric with water to make paste, apply to skin for inflammation.
3. **In Cooking:** Add 1/2 tsp to soups, curries, or smoothies daily.
**Dosage:** 500-1000mg turmeric powder daily.  Always add black pepper for better absorption.'''
        },
        {
            'name': 'Peppermint',
            'scientific_name': 'Mentha piperita',
            'description': 'Cooling herb excellent for headaches, digestion, and respiratory issues.',
            'properties': ['analgesic', 'cooling', 'digestive', 'decongestant'],
            'contraindications': ['GERD', 'hiatal hernia', 'infants'],
            'usage_instructions': '''**How to Use Peppermint:**
1. **For Headaches:** Apply 2-3 drops of peppermint oil mixed with coconut oil to temples. Massage gently in circular motions for 2-3 minutes. 
2. **Peppermint Tea:** Steep 5-10 fresh leaves or 1 tsp dried leaves in hot water for 5-7 minutes.  Drink warm.
3. **Steam Inhalation:** Add 3-4 drops to a bowl of hot water, cover head with towel, inhale for 5-10 minutes.
**Dosage:** 2-3 cups of tea daily.  For oil, always dilute before applying to skin.'''
        },
        {
            'name': 'Tulsi',
            'scientific_name': 'Ocimum sanctum',
            'description': 'Sacred basil known as the "Queen of Herbs" with adaptogenic properties.',
            'properties': ['adaptogenic', 'immunomodulatory', 'antimicrobial'],
            'contraindications': ['pregnancy', 'blood thinners'],
            'usage_instructions': '''**How to Use Tulsi:**
1. **Tulsi Tea:** Steep 8-10 fresh leaves in hot water for 5-10 minutes. Add honey if desired.
2.  **Fresh Leaves:** Chew 4-5 fresh tulsi leaves on empty stomach daily for immunity. 
3. **Tulsi Water:** Soak leaves overnight, drink the water in morning.
**Dosage:** 2-3 cups of tea daily or 5-6 fresh leaves.'''
        },
        {
            'name': 'Ashwagandha',
            'scientific_name': 'Withania somnifera',
            'description': 'Powerful adaptogen for stress, anxiety, and energy.',
            'properties': ['adaptogenic', 'anti-stress', 'rejuvenating'],
            'contraindications': ['pregnancy', 'thyroid disorders', 'autoimmune diseases'],
            'usage_instructions': '''**How to Use Ashwagandha:**
1. **With Warm Milk:** Mix 1/2 tsp ashwagandha powder in warm milk before bed.
2.  **Ashwagandha Tea:** Boil 1 tsp powder in water for 10 minutes, strain, add honey.
3.  **Capsules:** Take 300-500mg standardized extract twice daily.
**Dosage:** 300-600mg daily. Best taken in evening for sleep benefits.'''
        },
        {
            'name': 'Clove',
            'scientific_name': 'Syzygium aromaticum',
            'description': 'Aromatic spice with powerful analgesic and antimicrobial properties.',
            'properties': ['analgesic', 'antimicrobial', 'anti-inflammatory'],
            'contraindications': ['blood thinners', 'liver disease'],
            'usage_instructions': '''**How to Use Clove:**
1.  **For Headaches:** Crush 3-4 cloves, mix with 1 tsp coconut oil.  Apply to temples and forehead.  Massage gently for 5 minutes.
2.  **Clove Tea:** Steep 3-4 whole cloves in hot water for 10 minutes. Add honey and drink warm.
3. **Aromatherapy:** Inhale crushed clove aroma directly, or add to steam inhalation. 
4. **For Toothache:** Place a whole clove near the affected tooth, or apply clove oil with cotton. 
**Dosage:** 1-2 cups of clove tea daily. For oil, use sparingly and always dilute.'''
        },
        {
            'name': 'Neem',
            'scientific_name': 'Azadirachta indica',
            'description': 'Bitter herb with powerful antibacterial and blood-purifying properties.',
            'properties': ['antibacterial', 'antifungal', 'blood purifier'],
            'contraindications': ['pregnancy', 'trying to conceive', 'infants'],
            'usage_instructions': '''**How to Use Neem:**
1. **Neem Water:** Boil 10-15 neem leaves in water, cool, drink in morning on empty stomach.
2. **Skin Application:** Make paste of neem leaves, apply to affected skin for 15-20 minutes. 
3. **Neem Oil:** Dilute with coconut oil, apply to scalp for dandruff. 
**Dosage:** 1 cup neem water daily. For skin, use 2-3 times per week.'''
        },
        {
            'name': 'Honey',
            'scientific_name': 'Mel',
            'description': 'Natural sweetener with antibacterial and soothing properties.',
            'properties': ['antibacterial', 'soothing', 'wound healing'],
            'contraindications': ['infants under 1 year', 'diabetes - use sparingly'],
            'usage_instructions': '''**How to Use Honey:**
1. **For Sore Throat:** Take 1 tbsp raw honey directly, or mix in warm water with lemon. 
2. **With Ginger:** Mix honey with ginger juice for cough relief.
3. **Topical:** Apply raw honey to minor burns or wounds.
**Dosage:** 1-2 tablespoons daily. Use raw, unprocessed honey for best results.'''
        },
        {
            'name': 'Cinnamon',
            'scientific_name': 'Cinnamomum verum',
            'description': 'Warming spice that helps regulate blood sugar and has anti-inflammatory properties.',
            'properties': ['anti-inflammatory', 'antimicrobial', 'blood sugar regulating'],
            'contraindications': ['pregnancy in large amounts', 'liver disease'],
            'usage_instructions': '''**How to Use Cinnamon:**
1. **Cinnamon Tea:** Boil 1 cinnamon stick in water for 10 minutes. Add honey. 
2. **With Honey:** Mix 1/2 tsp cinnamon powder with 1 tbsp honey.  Take daily.
3. **In Warm Milk:** Add 1/4 tsp to warm milk before bed. 
**Dosage:** 1-2 grams daily. Use Ceylon cinnamon for regular consumption.'''
        },
        {
            'name': 'Black Pepper',
            'scientific_name': 'Piper nigrum',
            'description': 'Common spice that enhances nutrient absorption and has warming properties.',
            'properties': ['bioavailability enhancer', 'digestive', 'warming'],
            'contraindications': ['gastric ulcers', 'GERD'],
            'usage_instructions': '''**How to Use Black Pepper:**
1. **With Turmeric:** Always add a pinch of black pepper to turmeric for 2000% better absorption.
2.  **Pepper Tea:** Boil 4-5 crushed peppercorns in water, add honey for cold relief.
3. **In Honey:** Mix 1/4 tsp pepper with honey for cough. 
**Dosage:** 1/4 to 1/2 tsp daily in food or drinks.'''
        },
        {
            'name': 'Garlic',
            'scientific_name': 'Allium sativum',
            'description': 'Pungent bulb with powerful antimicrobial and cardiovascular benefits.',
            'properties': ['antimicrobial', 'cardiovascular', 'immune boosting'],
            'contraindications': ['blood thinners', 'surgery within 2 weeks'],
            'usage_instructions': '''**How to Use Garlic:**
1. **Raw Garlic:** Crush 1-2 cloves, let sit for 10 minutes to activate allicin.  Swallow with water.
2. **Garlic Tea:** Boil crushed garlic in water, add lemon and honey.
3.  **In Food:** Add crushed garlic to cooking at the end for maximum benefit.
**Dosage:** 1-2 raw cloves daily, preferably in morning.'''
        },
        {
            'name': 'Fennel',
            'scientific_name': 'Foeniculum vulgare',
            'description': 'Sweet aromatic seeds excellent for digestion and bloating.',
            'properties': ['digestive', 'carminative', 'cooling'],
            'contraindications': ['hormone-sensitive conditions'],
            'usage_instructions': '''**How to Use Fennel:**
1. **Fennel Tea:** Steep 1 tsp fennel seeds in hot water for 10 minutes.  Drink after meals.
2.  **Chewing Seeds:** Chew 1/2 tsp fennel seeds after meals for digestion. 
3. **Fennel Water:** Soak seeds overnight, drink in morning. 
**Dosage:** 1-3 cups of tea daily or 1 tsp seeds.'''
        },
        {
            'name': 'Chamomile',
            'scientific_name': 'Matricaria chamomilla',
            'description': 'Gentle calming herb for relaxation, sleep, and digestive comfort.',
            'properties': ['calming', 'anti-anxiety', 'digestive'],
            'contraindications': ['ragweed allergy', 'blood thinners'],
            'usage_instructions': '''**How to Use Chamomile:**
1.  **Chamomile Tea:** Steep 1 tbsp dried flowers in hot water for 5-10 minutes.  Drink before bed.
2.  **Chamomile Compress:** Soak cloth in cooled tea, apply to eyes for puffiness.
3. **Bath Soak:** Add strong chamomile tea to bath water for relaxation. 
**Dosage:** 2-3 cups daily. Safe for regular use.'''
        },
        {
            'name': 'Lavender',
            'scientific_name': 'Lavandula angustifolia',
            'description': 'Fragrant herb known for calming anxiety and promoting sleep.',
            'properties': ['calming', 'sleep promoting', 'antimicrobial'],
            'contraindications': ['hormone-sensitive conditions'],
            'usage_instructions': '''**How to Use Lavender:**
1. **Aromatherapy:** Add 2-3 drops lavender oil to pillow before sleep.
2. **Lavender Tea:** Steep 1-2 tsp dried lavender in hot water for 5 minutes.
3. **Bath:** Add 5-10 drops lavender oil to warm bath.
**Dosage:** 1-2 cups tea daily. For oil, always dilute for skin application.'''
        },
        {
            'name': 'Aloe Vera',
            'scientific_name': 'Aloe barbadensis',
            'description': 'Succulent plant with soothing gel for skin and digestive health.',
            'properties': ['soothing', 'wound healing', 'cooling'],
            'contraindications': ['pregnancy', 'kidney disease'],
            'usage_instructions': '''**How to Use Aloe Vera:**
1. **For Burns/Skin:** Apply fresh aloe gel directly to affected area.  Reapply 2-3 times daily.
2.  **Aloe Juice:** Mix 2 tbsp fresh gel in water, drink in morning for digestion.
3.  **Face Mask:** Apply gel to face, leave 15-20 minutes, rinse. 
**Dosage:** For internal use, 2 tbsp gel daily. For skin, as needed.'''
        },
    ]
    
    for herb in herbs:
        HerbRepository.create(
            name=herb['name'],
            scientific_name=herb['scientific_name'],
            description=herb['description'],
            properties=herb['properties'],
            contraindications=herb['contraindications'],
            usage_instructions=herb['usage_instructions']
        )
    
    print(f"   Created {len(herbs)} herbs")
    
    # Diseases
    print("Seeding diseases...")
    diseases = [
        ('Headache', 'R51', ['head pain', 'throbbing', 'tension']),
        ('Cold', 'J00', ['runny nose', 'sneezing', 'congestion']),
        ('Cough', 'R05', ['dry cough', 'wet cough', 'throat irritation']),
        ('Fever', 'R50. 9', ['high temperature', 'chills', 'sweating']),
        ('Nausea', 'R11', ['upset stomach', 'vomiting tendency']),
        ('Anxiety', 'F41. 1', ['worry', 'restlessness', 'tension']),
        ('Insomnia', 'G47.0', ['difficulty sleeping', 'restlessness']),
        ('Indigestion', 'K30', ['bloating', 'gas', 'discomfort']),
        ('Sore Throat', 'J02. 9', ['throat pain', 'difficulty swallowing']),
        ('Stress', 'F43.9', ['tension', 'overwhelm', 'fatigue']),
        ('Acne', 'L70. 0', ['pimples', 'skin inflammation']),
        ('Burns', 'T30.0', ['skin burn', 'redness', 'pain']),
        ('Arthritis', 'M19.90', ['joint pain', 'stiffness', 'swelling']),
        ('Fatigue', 'R53', ['tiredness', 'low energy', 'weakness']),
        ('Toothache', 'K08. 8', ['tooth pain', 'gum pain', 'sensitivity']),
    ]
    
    for name, icd, symptoms in diseases:
        DiseaseRepository.create(name, icd, symptoms)
    
    print(f"   Created {len(diseases)} diseases")
    
    # Evidence links
    print("Seeding evidence links...")
    
    evidence_links = [
        # Headache remedies
        ('Peppermint', 'Headache', 2, ['PMC4960504'], 'Menthol provides cooling analgesic effect, improves blood flow'),
        ('Clove', 'Headache', 3, ['PMC3769004'], 'Eugenol acts as natural analgesic and anti-inflammatory'),
        ('Lavender', 'Headache', 2, ['PMC3612440'], 'Aromatherapy reduces headache severity through relaxation'),
        
        # Cold remedies
        ('Ginger', 'Cold', 2, ['PMC3665023'], 'Anti-inflammatory and warming properties help fight infection'),
        ('Tulsi', 'Cold', 2, ['PMC4296439'], 'Immunomodulatory and antimicrobial properties'),
        ('Honey', 'Cold', 2, ['PMC4264806'], 'Antimicrobial and soothing for throat'),
        ('Garlic', 'Cold', 2, ['PMC4417560'], 'Allicin provides antimicrobial effects'),
        
        # Cough remedies
        ('Honey', 'Cough', 1, ['PMC6513626'], 'Clinical trials show effectiveness for cough suppression'),
        ('Ginger', 'Cough', 2, ['PMC3604064'], 'Anti-inflammatory reduces airway inflammation'),
        ('Tulsi', 'Cough', 3, ['PMC4296439'], 'Traditional expectorant use'),
        
        # Fever remedies
        ('Tulsi', 'Fever', 2, ['PMC4296439'], 'Antipyretic and immunomodulatory properties'),
        ('Neem', 'Fever', 2, ['PMC3695574'], 'Traditional antipyretic with antimicrobial properties'),
        
        # Anxiety remedies
        ('Ashwagandha', 'Anxiety', 1, ['PMC3573577'], 'Clinical trial proven adaptogen for stress and anxiety'),
        ('Chamomile', 'Anxiety', 1, ['PMC2995283'], 'Clinical evidence for generalized anxiety'),
        ('Lavender', 'Anxiety', 2, ['PMC3612440'], 'Aromatherapy reduces anxiety symptoms'),
        
        # Insomnia remedies
        ('Ashwagandha', 'Insomnia', 2, ['PMC6827862'], 'Improves sleep quality and onset'),
        ('Chamomile', 'Insomnia', 2, ['PMC2995283'], 'Mild sedative promotes relaxation'),
        ('Lavender', 'Insomnia', 2, ['PMC3612440'], 'Aromatherapy improves sleep quality'),
        
        # Indigestion remedies
        ('Ginger', 'Indigestion', 1, ['PMC3016669'], 'Clinically proven digestive aid'),
        ('Fennel', 'Indigestion', 2, ['PMC4137549'], 'Carminative reduces bloating and gas'),
        ('Peppermint', 'Indigestion', 2, ['PMC4729798'], 'Relaxes digestive muscles'),
        
        # Sore throat remedies
        ('Honey', 'Sore Throat', 2, ['PMC4264806'], 'Antimicrobial and soothing coating'),
        ('Ginger', 'Sore Throat', 3, ['PMC3665023'], 'Anti-inflammatory soothes throat'),
        ('Tulsi', 'Sore Throat', 3, ['PMC4296439'], 'Antimicrobial and soothing'),
        
        # Stress remedies
        ('Ashwagandha', 'Stress', 1, ['PMC3573577'], 'Adaptogen reduces cortisol levels'),
        ('Tulsi', 'Stress', 2, ['PMC4296439'], 'Adaptogenic properties reduce stress'),
        
        # Burns remedies
        ('Aloe Vera', 'Burns', 1, ['PMC2763764'], 'Clinical evidence for burn healing'),
        ('Honey', 'Burns', 2, ['PMC3941901'], 'Wound healing and antimicrobial'),
        
        # Toothache remedies
        ('Clove', 'Toothache', 1, ['PMC3769004'], 'Eugenol is clinically proven dental analgesic'),
    ]
    
    for herb_name, disease_name, tier, pubmed_ids, mechanism in evidence_links:
        herb = HerbRepository. get_by_name(herb_name)
        disease = DiseaseRepository.get_by_name(disease_name)
        if herb and disease:
            EvidenceRepository.create(herb['id'], disease['id'], tier, pubmed_ids, mechanism)
    
    print(f"   Created {len(evidence_links)} evidence links")
    print("\nKnowledge Graph seeded successfully!")
