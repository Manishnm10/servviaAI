"""
Django command: python manage.py seed_knowledge_graph
"""
from django.core.management.base import BaseCommand
from servvia.knowledge_graph.models import Herb, Disease, HerbDiseaseEvidence
from servvia.knowledge_graph.seed_data import HERBS_DATA, DISEASES_DATA, HERB_DISEASE_EVIDENCE


class Command(BaseCommand):
    help = 'Seed ServVia 2.0 Knowledge Graph'

    def handle(self, *args, **options):
        self.stdout. write('🌿 Seeding Knowledge Graph...\n')
        
        # Create Herbs
        herb_count = 0
        for data in HERBS_DATA:
            herb, created = Herb. objects.update_or_create(
                name=data['name'],
                defaults={
                    'scientific_name': data. get('scientific_name', ''),
                    'description': data.get('description', ''),
                    'traditional_uses': data.get('traditional_uses', []),
                    'contraindications': data. get('contraindications', []),
                    'drug_interactions': data. get('drug_interactions', []),
                }
            )
            if created:
                herb_count += 1
        self.stdout.write(f'✅ Created {herb_count} herbs')
        
        # Create Diseases
        disease_count = 0
        for data in DISEASES_DATA:
            disease, created = Disease.objects.update_or_create(
                name=data['name'],
                defaults={
                    'icd_code': data.get('icd_code', ''),
                    'symptoms': data.get('symptoms', []),
                }
            )
            if created:
                disease_count += 1
        self. stdout.write(f'✅ Created {disease_count} diseases')
        
        # Create Evidence Links
        evidence_count = 0
        for data in HERB_DISEASE_EVIDENCE:
            try:
                herb = Herb.objects. get(name=data['herb'])
                disease = Disease.objects.get(name=data['disease'])
                evidence, created = HerbDiseaseEvidence.objects.update_or_create(
                    herb=herb, disease=disease,
                    defaults={
                        'evidence_tier': data['tier'],
                        'pubmed_ids': data.get('pubmed_ids', []),
                        'mechanism_of_action': data. get('mechanism', ''),
                    }
                )
                evidence. calculate_confidence_score()
                evidence. save()
                if created:
                    evidence_count += 1
            except Exception as e:
                self.stdout.write(f'⚠️ Error: {e}')
        
        self. stdout.write(f'✅ Created {evidence_count} evidence links')
        self.stdout.write(self.style.SUCCESS('\n🎉 Knowledge Graph seeded successfully!'))
