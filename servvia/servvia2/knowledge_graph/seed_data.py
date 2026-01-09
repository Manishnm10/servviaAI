"""
ServVia 2. 0 - Seed Data
"""

HERBS_DATA = [
    {'name': 'Ginger', 'scientific_name': 'Zingiber officinale', 'description': 'Rhizome for nausea and inflammation', 'traditional_uses': ['nausea', 'digestion', 'cold'], 'contraindications': ['bleeding disorders', 'gallstones'], 'drug_interactions': ['blood thinners', 'diabetes medications']},
    {'name': 'Turmeric', 'scientific_name': 'Curcuma longa', 'description': 'Anti-inflammatory with curcumin', 'traditional_uses': ['inflammation', 'arthritis', 'skin'], 'contraindications': ['gallbladder disease', 'bleeding disorders'], 'drug_interactions': ['blood thinners', 'diabetes medications']},
    {'name': 'Honey', 'scientific_name': 'Mel (Apis mellifera)', 'description': 'Natural antimicrobial sweetener', 'traditional_uses': ['cough', 'wound healing', 'sore throat'], 'contraindications': ['infants under 1 year', 'diabetes'], 'drug_interactions': ['diabetes medications']},
    {'name': 'Garlic', 'scientific_name': 'Allium sativum', 'description': 'Antimicrobial and cardiovascular support', 'traditional_uses': ['heart health', 'immune support'], 'contraindications': ['bleeding disorders', 'surgery'], 'drug_interactions': ['blood thinners', 'HIV medications']},
    {'name': 'Aloe Vera', 'scientific_name': 'Aloe barbadensis miller', 'description': 'Succulent for skin and digestive health', 'traditional_uses': ['burns', 'skin healing', 'constipation'], 'contraindications': ['pregnancy', 'kidney disease'], 'drug_interactions': ['diabetes medications', 'diuretics']},
    {'name': 'Peppermint', 'scientific_name': 'Mentha piperita', 'description': 'Cooling mint for digestion', 'traditional_uses': ['headache', 'digestive issues', 'IBS'], 'contraindications': ['GERD', 'hiatal hernia'], 'drug_interactions': ['cyclosporine']},
    {'name': 'Chamomile', 'scientific_name': 'Matricaria chamomilla', 'description': 'Calming flower for sleep', 'traditional_uses': ['anxiety', 'insomnia', 'digestive upset'], 'contraindications': ['ragweed allergy', 'pregnancy'], 'drug_interactions': ['blood thinners', 'sedatives']},
    {'name': 'Eucalyptus', 'scientific_name': 'Eucalyptus globulus', 'description': 'Respiratory support', 'traditional_uses': ['congestion', 'cough', 'cold'], 'contraindications': ['asthma', 'children under 2'], 'drug_interactions': ['diabetes medications']},
    {'name': 'Lavender', 'scientific_name': 'Lavandula angustifolia', 'description': 'Relaxing aromatic', 'traditional_uses': ['anxiety', 'insomnia', 'headache'], 'contraindications': ['hormone-sensitive conditions'], 'drug_interactions': ['sedatives']},
    {'name': 'Echinacea', 'scientific_name': 'Echinacea purpurea', 'description': 'Immune-boosting flower', 'traditional_uses': ['cold', 'flu', 'immune support'], 'contraindications': ['autoimmune diseases'], 'drug_interactions': ['immunosuppressants']},
    {'name': 'Green Tea', 'scientific_name': 'Camellia sinensis', 'description': 'Antioxidant-rich tea', 'traditional_uses': ['weight management', 'alertness'], 'contraindications': ['iron deficiency', 'anxiety'], 'drug_interactions': ['blood thinners', 'stimulants']},
    {'name': 'Ginseng', 'scientific_name': 'Panax ginseng', 'description': 'Adaptogenic root for energy', 'traditional_uses': ['fatigue', 'cognitive function'], 'contraindications': ['insomnia', 'high blood pressure'], 'drug_interactions': ['blood thinners', 'diabetes medications']},
    {'name': 'Cinnamon', 'scientific_name': 'Cinnamomum verum', 'description': 'Blood sugar regulating spice', 'traditional_uses': ['blood sugar', 'digestion'], 'contraindications': ['liver disease', 'pregnancy'], 'drug_interactions': ['diabetes medications', 'blood thinners']},
    {'name': 'Lemon', 'scientific_name': 'Citrus limon', 'description': 'Vitamin C rich citrus', 'traditional_uses': ['cold', 'sore throat', 'digestion'], 'contraindications': ['GERD', 'citrus allergy'], 'drug_interactions': ['certain antibiotics']},
    {'name': 'Coconut Oil', 'scientific_name': 'Cocos nucifera', 'description': 'Antimicrobial tropical oil', 'traditional_uses': ['skin care', 'hair care'], 'contraindications': ['coconut allergy'], 'drug_interactions': []},
    {'name': 'Ashwagandha', 'scientific_name': 'Withania somnifera', 'description': 'Adaptogenic herb', 'traditional_uses': ['stress', 'anxiety', 'fatigue'], 'contraindications': ['thyroid disorders', 'pregnancy'], 'drug_interactions': ['thyroid medications', 'sedatives']},
    {'name': 'Tulsi', 'scientific_name': 'Ocimum tenuiflorum', 'description': 'Holy basil for stress', 'traditional_uses': ['stress', 'respiratory'], 'contraindications': ['pregnancy', 'hypothyroidism'], 'drug_interactions': ['blood thinners']},
    {'name': 'Neem', 'scientific_name': 'Azadirachta indica', 'description': 'Antimicrobial for skin', 'traditional_uses': ['skin conditions', 'oral health'], 'contraindications': ['pregnancy', 'autoimmune diseases'], 'drug_interactions': ['diabetes medications']},
    {'name': 'Fennel', 'scientific_name': 'Foeniculum vulgare', 'description': 'Digestive support', 'traditional_uses': ['bloating', 'colic'], 'contraindications': ['hormone-sensitive conditions'], 'drug_interactions': ['estrogen medications']},
    {'name': 'Moringa', 'scientific_name': 'Moringa oleifera', 'description': 'Nutrient-dense superfood', 'traditional_uses': ['nutrition', 'inflammation'], 'contraindications': ['pregnancy', 'thyroid disorders'], 'drug_interactions': ['thyroid medications']},
    {'name': 'Clove', 'scientific_name': 'Syzygium aromaticum', 'description': 'Analgesic spice', 'traditional_uses': ['toothache', 'oral health'], 'contraindications': ['bleeding disorders'], 'drug_interactions': ['blood thinners']},
    {'name': 'Licorice Root', 'scientific_name': 'Glycyrrhiza glabra', 'description': 'Soothing root', 'traditional_uses': ['sore throat', 'cough'], 'contraindications': ['hypertension', 'heart disease', 'pregnancy'], 'drug_interactions': ['blood pressure meds', 'diuretics']},
    {'name': 'Fenugreek', 'scientific_name': 'Trigonella foenum-graecum', 'description': 'Blood sugar support', 'traditional_uses': ['blood sugar', 'lactation'], 'contraindications': ['pregnancy'], 'drug_interactions': ['blood thinners', 'diabetes medications']},
    {'name': 'Black Pepper', 'scientific_name': 'Piper nigrum', 'description': 'Bioavailability enhancer', 'traditional_uses': ['digestion', 'nutrient absorption'], 'contraindications': ['GI ulcers'], 'drug_interactions': ['enhances drug absorption']},
    {'name': 'Apple Cider Vinegar', 'scientific_name': 'Malus domestica', 'description': 'Fermented apple juice', 'traditional_uses': ['blood sugar', 'weight loss'], 'contraindications': ['GERD', 'low potassium'], 'drug_interactions': ['diabetes medications', 'diuretics']},
]

DISEASES_DATA = [
    {'name': 'Common Cold', 'icd_code': 'J00', 'symptoms': ['runny nose', 'sore throat', 'cough']},
    {'name': 'Headache', 'icd_code': 'R51', 'symptoms': ['head pain', 'pressure']},
    {'name': 'Indigestion', 'icd_code': 'K30', 'symptoms': ['bloating', 'nausea', 'heartburn']},
    {'name': 'Insomnia', 'icd_code': 'G47. 0', 'symptoms': ['difficulty sleeping', 'fatigue']},
    {'name': 'Anxiety', 'icd_code': 'F41', 'symptoms': ['worry', 'restlessness']},
    {'name': 'Arthritis', 'icd_code': 'M13', 'symptoms': ['joint pain', 'stiffness']},
    {'name': 'Cough', 'icd_code': 'R05', 'symptoms': ['coughing', 'throat irritation']},
    {'name': 'Skin Inflammation', 'icd_code': 'L30', 'symptoms': ['redness', 'itching']},
    {'name': 'Nausea', 'icd_code': 'R11', 'symptoms': ['stomach discomfort']},
    {'name': 'Sore Throat', 'icd_code': 'J02', 'symptoms': ['throat pain']},
    {'name': 'High Blood Sugar', 'icd_code': 'R73', 'symptoms': ['increased thirst']},
    {'name': 'Minor Burns', 'icd_code': 'T30', 'symptoms': ['redness', 'pain']},
    {'name': 'Muscle Pain', 'icd_code': 'M79. 1', 'symptoms': ['muscle aches']},
    {'name': 'Fatigue', 'icd_code': 'R53', 'symptoms': ['tiredness', 'low energy']},
    {'name': 'Acne', 'icd_code': 'L70', 'symptoms': ['pimples', 'oily skin']},
]

HERB_DISEASE_EVIDENCE = [
    {'herb': 'Ginger', 'disease': 'Nausea', 'tier': 1, 'pubmed_ids': ['30680163', '24642205'], 'mechanism': 'Gingerols block 5-HT3 receptors'},
    {'herb': 'Turmeric', 'disease': 'Arthritis', 'tier': 1, 'pubmed_ids': ['27533649', '29065496'], 'mechanism': 'Curcumin inhibits NF-kB and COX-2'},
    {'herb': 'Chamomile', 'disease': 'Anxiety', 'tier': 1, 'pubmed_ids': ['27912871'], 'mechanism': 'Apigenin binds GABA-A receptors'},
    {'herb': 'Peppermint', 'disease': 'Indigestion', 'tier': 1, 'pubmed_ids': ['26310198'], 'mechanism': 'Menthol relaxes GI smooth muscle'},
    {'herb': 'Honey', 'disease': 'Cough', 'tier': 2, 'pubmed_ids': ['20618098'], 'mechanism': 'Coats throat, antimicrobial'},
    {'herb': 'Garlic', 'disease': 'Common Cold', 'tier': 2, 'pubmed_ids': ['25386977'], 'mechanism': 'Allicin antimicrobial properties'},
    {'herb': 'Eucalyptus', 'disease': 'Common Cold', 'tier': 2, 'pubmed_ids': ['24909715'], 'mechanism': 'Eucalyptol loosens mucus'},
    {'herb': 'Lavender', 'disease': 'Insomnia', 'tier': 2, 'pubmed_ids': ['22612017'], 'mechanism': 'Linalool modulates GABA'},
    {'herb': 'Aloe Vera', 'disease': 'Minor Burns', 'tier': 2, 'pubmed_ids': ['30287380'], 'mechanism': 'Promotes wound healing'},
    {'herb': 'Cinnamon', 'disease': 'High Blood Sugar', 'tier': 2, 'pubmed_ids': ['31826751'], 'mechanism': 'Improves insulin sensitivity'},
    {'herb': 'Peppermint', 'disease': 'Headache', 'tier': 2, 'pubmed_ids': ['26677570'], 'mechanism': 'Menthol cooling analgesic'},
    {'herb': 'Lemon', 'disease': 'Sore Throat', 'tier': 3, 'pubmed_ids': [], 'mechanism': 'Vitamin C and acidic pH'},
    {'herb': 'Clove', 'disease': 'Headache', 'tier': 3, 'pubmed_ids': ['22610115'], 'mechanism': 'Eugenol analgesic'},
    {'herb': 'Ashwagandha', 'disease': 'Fatigue', 'tier': 2, 'pubmed_ids': ['23439798'], 'mechanism': 'Adaptogenic cortisol modulation'},
    {'herb': 'Neem', 'disease': 'Acne', 'tier': 3, 'pubmed_ids': [], 'mechanism': 'Antimicrobial properties'},
    {'herb': 'Turmeric', 'disease': 'Skin Inflammation', 'tier': 2, 'pubmed_ids': ['27213821'], 'mechanism': 'Curcumin reduces cytokines'},
    {'herb': 'Echinacea', 'disease': 'Common Cold', 'tier': 2, 'pubmed_ids': ['24554461'], 'mechanism': 'Stimulates immune cells'},
    {'herb': 'Ginseng', 'disease': 'Fatigue', 'tier': 2, 'pubmed_ids': ['23613825'], 'mechanism': 'Ginsenosides enhance ATP'},
    {'herb': 'Fenugreek', 'disease': 'High Blood Sugar', 'tier': 2, 'pubmed_ids': ['24403841'], 'mechanism': 'Fiber slows carb absorption'},
    {'herb': 'Licorice Root', 'disease': 'Sore Throat', 'tier': 3, 'pubmed_ids': ['19857084'], 'mechanism': 'Demulcent coats throat'},
    {'herb': 'Fennel', 'disease': 'Indigestion', 'tier': 3, 'pubmed_ids': [], 'mechanism': 'Anethole relaxes GI tract'},
    {'herb': 'Tulsi', 'disease': 'Anxiety', 'tier': 3, 'pubmed_ids': ['28471731'], 'mechanism': 'Adaptogenic HPA modulation'},
    {'herb': 'Green Tea', 'disease': 'Fatigue', 'tier': 2, 'pubmed_ids': ['28864169'], 'mechanism': 'L-theanine caffeine synergy'},
    {'herb': 'Coconut Oil', 'disease': 'Skin Inflammation', 'tier': 3, 'pubmed_ids': [], 'mechanism': 'Lauric acid anti-inflammatory'},
    {'herb': 'Moringa', 'disease': 'High Blood Sugar', 'tier': 3, 'pubmed_ids': ['29065618'], 'mechanism': 'Isothiocyanates improve insulin'},
]


def seed_knowledge_graph():
    """Seed the knowledge graph with data"""
    from servvia2.knowledge_graph.models import (
        init_knowledge_graph_tables, HerbRepository, DiseaseRepository, EvidenceRepository
    )
    
    print("🌿 Initializing Knowledge Graph...")
    init_knowledge_graph_tables()
    
    print("🌱 Seeding herbs...")
    herb_ids = {}
    for herb in HERBS_DATA:
        herb_id = HerbRepository.create(**herb)
        herb_ids[herb['name']] = herb_id
    print(f"   ✅ Created {len(HERBS_DATA)} herbs")
    
    print("🏥 Seeding diseases...")
    disease_ids = {}
    for disease in DISEASES_DATA:
        disease_id = DiseaseRepository. create(**disease)
        disease_ids[disease['name']] = disease_id
    print(f"   ✅ Created {len(DISEASES_DATA)} diseases")
    
    print("🔗 Seeding evidence links...")
    for ev in HERB_DISEASE_EVIDENCE:
        herb = HerbRepository.get_by_name(ev['herb'])
        disease = DiseaseRepository.get_by_name(ev['disease'])
        if herb and disease:
            EvidenceRepository.create(
                herb_id=herb['id'],
                disease_id=disease['id'],
                evidence_tier=ev['tier'],
                pubmed_ids=ev['pubmed_ids'],
                mechanism=ev['mechanism']
            )
    print(f"   ✅ Created {len(HERB_DISEASE_EVIDENCE)} evidence links")
    
    print("\n🎉 Knowledge Graph seeded successfully!")


if __name__ == '__main__':
    seed_knowledge_graph()
