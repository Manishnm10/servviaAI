"""
ServVia — Medical ASR Priming Prompt
====================================

Ported from the original ``language_service/whisper_transcribe.py`` MEDICAL_PROMPTS
technique that made regional-language speech recognition robust.

The idea: prime the speech model with common spoken symptom phrases (romanized +
native script) across Indian languages. This biases the model toward correct
medical terminology AND, critically, toward the correct LANGUAGE — e.g. it stops
Kannada being mis-detected as Hindi.

Used by both engines in ``voice_asr.py``:
  * Gemini  — passed as the text part alongside the audio.
  * Whisper — passed as the ``prompt`` argument.
"""

# Strong, language-disambiguating priming prompt with verbatim symptom phrases.
MEDICAL_ASR_PROMPT = """This is a short MEDICAL voice query from a patient, most likely in an Indian regional language or English. Recognise the spoken symptom and transcribe it VERBATIM in the speaker's own language and native script. Detect the language CAREFULLY — do NOT confuse Kannada with Hindi, or Tamil with Telugu.

Common spoken phrases per language (romanized = native script = meaning):

KANNADA (kn): nanige jwara ide (ನನಗೆ ಜ್ವರ ಇದೆ = I have fever); nanige kemmu ide (ನನಗೆ ಕೆಮ್ಮು ಇದೆ = cough); nanige thalenovu ide (ನನಗೆ ತಲೆನೋವು ಇದೆ = headache); nanige hotte novu ide (ಹೊಟ್ಟೆ ನೋವು = stomach pain); nanige gantalu novu ide (ಗಂಟಲು ನೋವು = sore throat); nanige vaanthi aagthide (ವಾಂತಿ = vomiting); nanige sheethaagide (ಶೀತ = cold); nanige bedi aagthide (ಬೇದಿ = diarrhea).

HINDI (hi): mujhe bukhar hai (मुझे बुखार है = fever); mujhe khansi hai (खांसी = cough); mujhe sir dard hai (सिर दर्द = headache); mujhe pet dard hai (पेट दर्द = stomach pain).

TAMIL (ta): enakku kaichal irukku (எனக்கு காய்ச்சல் இருக்கு = fever); enakku irumal irukku (இருமல் = cough); enakku thalai vali irukku (தலைவலி = headache).

TELUGU (te): naaku jwaram undi (నాకు జ్వరం ఉంది = fever); naaku dabbhu undi (దగ్గు = cough); naaku tala noppi undi (తల నొప్పి = headache).

MALAYALAM (ml): enikku pani und (എനിക്ക് പനി ഉണ്ട് = fever); enikku chuma und (ചുമ = cough); enikku thala vedana und (തലവേദന = headache).

BENGALI (bn): amar jor hoyeche (আমার জ্বর হয়েছে = fever); amar kashi hoyeche (কাশি = cough); amar matha byatha (মাথা ব্যথা = headache).

MARATHI (mr): mala taap aahey (मला ताप आहे = fever); mala khokhla aahey (खोकला = cough); mala dokey dukhte (डोके दुखते = headache).

GUJARATI (gu): mane taav che (મને તાવ છે = fever); mane khansi che (ખાંસી = cough).

PUNJABI (pa): mainu bukhar hai (ਮੈਨੂੰ ਬੁਖਾਰ ਹੈ = fever); mainu khansi hai (ਖੰਘ = cough).

URDU (ur): mujhe bukhar hai (مجھے بخار ہے = fever); mujhe khansi hai (کھانسی = cough).

ENGLISH (en): I have fever / cough / headache / stomach pain / sore throat / body pain / cold.

If the speech is none of the above, still transcribe it verbatim in its own language and native script."""

# JSON-output instruction appended for engines we parse structured output from (Gemini).
MEDICAL_ASR_PROMPT_JSON = (
    MEDICAL_ASR_PROMPT
    + '\n\nRespond with ONLY a JSON object, no markdown, no commentary:\n'
    '{"transcript": "<verbatim text in native script>", "language": "<ISO 639-1 code>"}'
)
