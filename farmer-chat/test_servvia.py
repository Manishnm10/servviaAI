from servvia2. agentic_rag.agent import ServViaAgent

agent = ServViaAgent()
result = agent.enhance_response(
    query='I have a headache',
    user_profile={'first_name': 'Ayaan', 'allergies': [], 'medical_conditions': []},
    location={'latitude':28}
)

print(result['response'])
