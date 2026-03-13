"""
Test script for Warfarin-Turmeric temporal safety block.
This script tests that the Agentic RAG Controller properly blocks
turmeric recommendations when the user is on warfarin started recently.
"""

import os
import sys
import asyncio
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from asgiref.sync import sync_to_async
from core_temporal.agentic_rag.controller import ServViaAgenticRAG
from user_profile.models import UserProfile, MedicationHistory
from django.utils import timezone
from datetime import timedelta


@sync_to_async
def setup_test_user():
    """Create test user with warfarin medication history"""
    user, created = UserProfile.objects.get_or_create(
        email="test_user@example.com",
        defaults={
            "first_name": "Test",
            "last_name": "User"
        }
    )
    
    # Create warfarin medication history (started 5 days ago)
    med, med_created = MedicationHistory.objects.get_or_create(
        user=user,
        medication_name="Warfarin",
        defaults={
            "generic_name": "warfarin",
            "dosage": "5mg",
            "frequency": "daily",
            "start_date": timezone.now() - timedelta(days=5),
            "status": "active"
        }
    )
    
    if created:
        print(f"✅ Created test user: {user.email}")
    if med_created:
        print(f"✅ Added warfarin medication (started 5 days ago)")
    
    return user


async def test_warfarin_turmeric_block():
    """
    Test that turmeric is blocked when user started warfarin recently.
    This should trigger the temporal safety gate.
    """
    print("=" * 70)
    print("TEST: Warfarin + Turmeric Temporal Safety Block")
    print("=" * 70)
    print()
    
    # Create the Agentic RAG Controller
    controller = ServViaAgenticRAG()
    
    # Simulate retrieved chunks that would suggest turmeric
    # (This simulates what would come from the vector database)
    retrieved_chunks = [
        {
            'text': 'Turmeric (Curcuma longa) contains curcumin which has anti-inflammatory properties. '
                    'Studies show it may help with joint pain and arthritis. '
                    'PMID: 25402637. Traditional use in Ayurvedic medicine for centuries.',
            'source': 'Ayurvedic Knowledge Base'
        },
        {
            'text': 'Curcumin provides anti-inflammatory benefits similar to NSAIDs. '
                    'Effective for osteoarthritis pain. Mechanism: COX-2 inhibition.',
            'source': 'PubMed Research'
        }
    ]
    
    # Test query - user started warfarin 5 days ago and has joint pain
    test_query = "I have joint pain. I started taking warfarin 5 days ago. Can I take turmeric?"
    
    # User context
    user_name = "TestUser"
    user_id = "test_user@example.com"
    allergies = []
    medical_conditions = ["arthritis"]
    location = None
    
    print(f"Query: {test_query}")
    print(f"User: {user_name} ({user_id})")
    print(f"Conditions: {medical_conditions}")
    print()
    
    # Call the controller (now async)
    print("Calling Agentic RAG Controller...")
    print("-" * 70)
    
    result = await controller.process(
        query=test_query,
        retrieved_chunks=retrieved_chunks,
        user_name=user_name,
        user_id=user_id,
        allergies=allergies,
        medical_conditions=medical_conditions,
        location=location
    )
    
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()
    
    # Check if response was blocked
    was_blocked = result.get('temporal_safety_blocked', False)
    
    print(f"Safety Block Triggered: {'YES' if was_blocked else 'NO'}")
    print()
    
    if was_blocked:
        print("✅ TEST PASSED: Temporal safety gate correctly blocked turmeric!")
        print()
        print("Response Preview:")
        print("-" * 70)
        response = result.get('response', '')
        # Show first 500 chars
        print(response[:500] + "..." if len(response) > 500 else response)
        print()
        
        violations = result.get('temporal_violations', [])
        if violations:
            print("Violations Detected:")
            for v in violations:
                print(f"  - {v}")
    else:
        print("❌ TEST FAILED: Expected turmeric to be blocked due to warfarin")
        print()
        print("Remedies Returned:")
        remedies = result.get('remedies', [])
        for r in remedies:
            print(f"  - {r.get('herb_name', 'Unknown')}")
    
    print()
    print("=" * 70)
    
    return was_blocked


async def test_safe_recommendation():
    """
    Test that normal recommendations work when no temporal issues.
    """
    print("=" * 70)
    print("TEST: Normal Recommendation (No Safety Issues)")
    print("=" * 70)
    print()
    
    controller = ServViaAgenticRAG()
    
    retrieved_chunks = [
        {
            'text': 'Ginger (Zingiber officinale) is effective for nausea. '
                    'Multiple clinical trials show it reduces pregnancy-induced nausea. '
                    'PMID: 24390544. Safe in pregnancy up to 1g daily.',
            'source': 'Clinical Research'
        }
    ]
    
    test_query = "I have nausea. What can help?"
    
    result = await controller.process(
        query=test_query,
        retrieved_chunks=retrieved_chunks,
        user_name="TestUser",
        user_id="test_user2@example.com",
        allergies=[],
        medical_conditions=[],
        location=None
    )
    
    was_blocked = result.get('temporal_safety_blocked', False)
    remedies = result.get('remedies', [])
    
    print(f"Safety Block Triggered: {'YES' if was_blocked else 'NO'}")
    print(f"Remedies Recommended: {len(remedies)}")
    
    if not was_blocked and len(remedies) > 0:
        print("✅ TEST PASSED: Normal recommendation flow works!")
        for r in remedies:
            print(f"  - {r.get('herb_name', 'Unknown')}")
    else:
        print("❌ TEST FAILED: Expected normal recommendation")
    
    print()
    print("=" * 70)
    
    return not was_blocked and len(remedies) > 0


async def main():
    """Main test runner"""
    print()
    print("🔬 ServVia Temporal Safety Gate Test Suite")
    print("Testing Objective 2: Warfarin-Turmeric Interaction Block")
    print()
    
    # Setup test user with medication history
    print("Setting up test user...")
    await setup_test_user()
    print()
    
    # Run tests
    test1_passed = await test_warfarin_turmeric_block()
    print()
    test2_passed = await test_safe_recommendation()
    
    # Summary
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print()
    print(f"Warfarin Block Test: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Normal Flow Test:    {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print()
    
    if test1_passed and test2_passed:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
