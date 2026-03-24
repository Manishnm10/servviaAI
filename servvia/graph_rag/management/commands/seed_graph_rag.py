"""
Django management command: seed_graph_rag

Usage:
    python manage.py seed_graph_rag
    python manage.py seed_graph_rag --verify
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed the Neo4j AuraDB knowledge graph with remedy/symptom/bio-state data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--verify",
            action="store_true",
            help="After seeding, run a test query to verify the graph is working",
        )

    def handle(self, *args, **options):
        self.stdout.write("Graph RAG: connecting to Neo4j AuraDB...")

        try:
            from graph_rag.seeder import seed_graph
            stats = seed_graph()
        except KeyError as e:
            self.stderr.write(self.style.ERROR(
                f"Missing Neo4j credential: {e}\n"
                "Ensure NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD are set in .env"
            ))
            return
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Seeding failed: {e}"))
            raise

        self.stdout.write(self.style.SUCCESS(
            f"Graph RAG seeded successfully:\n"
            f"  Remedy nodes:         {stats['remedies']}\n"
            f"  Symptom nodes:        {stats['symptoms']}\n"
            f"  BiologicalState nodes:{stats['bio_states']}\n"
            f"  TREATS edges:         {stats['treats_edges']}\n"
            f"  ENHANCED_BY edges:    {stats['enhanced_by_edges']}"
        ))

        if options["verify"]:
            self.stdout.write("\nGraph RAG: running verification query...")
            try:
                from graph_rag.client import KnowledgeGraphClient
                with KnowledgeGraphClient() as client:
                    results = client.retrieve_ranked_remedies(
                        symptoms=["fatigue", "headache"],
                        bio_state="morning",
                    )
                if results:
                    self.stdout.write(self.style.SUCCESS(
                        f"Verification passed — top remedy: {results[0]['remedy']} "
                        f"(rank={results[0]['rank']:.2f})"
                    ))
                    for r in results[:5]:
                        self.stdout.write(
                            f"  {r['remedy']:<20} base={r['base_score']:.2f}  "
                            f"enhancement={r['enhancement']:.2f}  rank={r['rank']:.2f}"
                        )
                else:
                    self.stdout.write(self.style.WARNING(
                        "Verification query returned 0 results — check seed data"
                    ))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Verification failed: {e}"))
