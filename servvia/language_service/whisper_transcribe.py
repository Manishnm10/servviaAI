"""
Whisper-based Transcription Service for ServVia
Supports ALL Indian regional languages with medical context prompting

Current Date: 2025-12-30
"""
import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Initialize OpenAI client
try:
    from openai import OpenAI
    from django.conf import settings
    client = OpenAI(api_key=getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY')))
    WHISPER_AVAILABLE = True
    logger.info("✅ OpenAI Whisper client initialized")
except Exception as e:
    WHISPER_AVAILABLE = False
    client = None
    logger.warning(f"⚠️ OpenAI Whisper not available: {e}")


# =============================================================================
# INDIAN LANGUAGE CONFIGURATION
# =============================================================================

# All Indian languages supported by Whisper with their codes
INDIAN_LANGUAGES = {
    # ISO 639-1 codes -> Whisper codes and names
    'as': {'whisper': 'as', 'name': 'Assamese', 'native': 'অসমীয়া', 'script': 'bengali'},
    'bn': {'whisper': 'bn', 'name': 'Bengali', 'native': 'বাংলা', 'script': 'bengali'},
    'brx': {'whisper': 'en', 'name': 'Bodo', 'native': 'बड़ो', 'script': 'devanagari'},  # Fallback to English
    'doi': {'whisper': 'hi', 'name': 'Dogri', 'native': 'डोगरी', 'script': 'devanagari'},  # Fallback to Hindi
    'gu': {'whisper': 'gu', 'name': 'Gujarati', 'native':  'ગુજરાતી', 'script': 'gujarati'},
    'hi': {'whisper': 'hi', 'name': 'Hindi', 'native': 'हिन्दी', 'script':  'devanagari'},
    'kn': {'whisper': 'kn', 'name': 'Kannada', 'native': 'ಕನ್ನಡ', 'script': 'kannada'},
    'ks': {'whisper': 'ur', 'name': 'Kashmiri', 'native':  'कॉशुर', 'script': 'perso-arabic'},  # Fallback to Urdu
    'gom': {'whisper': 'hi', 'name': 'Konkani', 'native': 'कोंकणी', 'script': 'devanagari'},  # Fallback to Hindi
    'mai': {'whisper': 'hi', 'name': 'Maithili', 'native':  'मैथिली', 'script': 'devanagari'},  # Fallback to Hindi
    'ml': {'whisper': 'ml', 'name': 'Malayalam', 'native': 'മലയാളം', 'script': 'malayalam'},
    'mni': {'whisper': 'en', 'name': 'Manipuri', 'native': 'মৈতৈলোন্', 'script': 'bengali'},  # Fallback
    'mr': {'whisper':  'mr', 'name':  'Marathi', 'native': 'मराठी', 'script': 'devanagari'},
    'ne': {'whisper': 'ne', 'name': 'Nepali', 'native': 'नेपाली', 'script': 'devanagari'},
    'or': {'whisper': 'en', 'name': 'Odia', 'native': 'ଓଡ଼ିଆ', 'script':  'odia'},  # Limited Whisper support
    'pa': {'whisper': 'pa', 'name': 'Punjabi', 'native': 'ਪੰਜਾਬੀ', 'script': 'gurmukhi'},
    'sa': {'whisper': 'sa', 'name': 'Sanskrit', 'native': 'संस्कृतम्', 'script': 'devanagari'},
    'sat': {'whisper': 'hi', 'name': 'Santali', 'native': 'ᱥᱟᱱᱛᱟᱲᱤ', 'script': 'ol_chiki'},  # Fallback
    'sd': {'whisper':  'sd', 'name':  'Sindhi', 'native': 'سنڌي', 'script': 'perso-arabic'},
    'ta': {'whisper': 'ta', 'name': 'Tamil', 'native': 'தமிழ்', 'script': 'tamil'},
    'te': {'whisper': 'te', 'name': 'Telugu', 'native': 'తెలుగు', 'script': 'telugu'},
    'ur': {'whisper': 'ur', 'name': 'Urdu', 'native': 'اردو', 'script': 'perso-arabic'},
    'en': {'whisper': 'en', 'name': 'English', 'native': 'English', 'script': 'latin'},
    
    # BCP-47 variants (with region codes)
    'as-IN': {'whisper': 'as', 'name': 'Assamese', 'native': 'অসমীয়া', 'script': 'bengali'},
    'bn-IN': {'whisper': 'bn', 'name': 'Bengali', 'native': 'বাংলা', 'script': 'bengali'},
    'gu-IN': {'whisper':  'gu', 'name': 'Gujarati', 'native': 'ગુજરાતી', 'script': 'gujarati'},
    'hi-IN': {'whisper': 'hi', 'name': 'Hindi', 'native': 'हिन्दी', 'script': 'devanagari'},
    'kn-IN': {'whisper':  'kn', 'name': 'Kannada', 'native': 'ಕನ್ನಡ', 'script': 'kannada'},
    'ml-IN': {'whisper': 'ml', 'name': 'Malayalam', 'native': 'മലയാളം', 'script': 'malayalam'},
    'mr-IN': {'whisper': 'mr', 'name': 'Marathi', 'native': 'मराठी', 'script': 'devanagari'},
    'or-IN': {'whisper': 'en', 'name': 'Odia', 'native': 'ଓଡ଼ିଆ', 'script': 'odia'},
    'pa-IN': {'whisper': 'pa', 'name': 'Punjabi', 'native': 'ਪੰਜਾਬੀ', 'script': 'gurmukhi'},
    'ta-IN': {'whisper': 'ta', 'name': 'Tamil', 'native': 'தமிழ்', 'script': 'tamil'},
    'te-IN': {'whisper': 'te', 'name': 'Telugu', 'native': 'తెలుగు', 'script':  'telugu'},
    'ur-IN': {'whisper':  'ur', 'name':  'Urdu', 'native': 'اردو', 'script': 'perso-arabic'},
    'en-IN': {'whisper': 'en', 'name': 'English (India)', 'native': 'English', 'script': 'latin'},
    'en-US': {'whisper':  'en', 'name':  'English (US)', 'native': 'English', 'script': 'latin'},
}


# =============================================================================
# MEDICAL PROMPTS FOR ALL INDIAN LANGUAGES
# These prompts guide Whisper to recognize medical terminology correctly
# =============================================================================

MEDICAL_PROMPTS = {
    # ----------------- KANNADA -----------------
    'kn': """ಕನ್ನಡ ವೈದ್ಯಕೀಯ ಸಂಭಾಷಣೆ.  Kannada medical phrases:
nanige jwara ide (ನನಗೆ ಜ್ವರ ಇದೆ - I have fever)
nanige kemmu ide (ನನಗೆ ಕೆಮ್ಮು ಇದೆ - I have cough)
nanige thalenovu ide (ನನಗೆ ತಲೆನೋವು ಇದೆ - I have headache)
nanige hotte novu ide (ನನಗೆ ಹೊಟ್ಟೆ ನೋವು ಇದೆ - I have stomach pain)
nanige gantalu novu ide (ನನಗೆ ಗಂಟಲು ನೋವು ಇದೆ - I have sore throat)
nanige vaanthi aagthide (ನನಗೆ ವಾಂತಿ ಆಗ್ತಿದೆ - I am vomiting)
nanige sheethaagide (ನನಗೆ ಶೀತ ಆಗಿದೆ - I have cold)
nanige bedi aagthide (ನನಗೆ ಬೇದಿ ಆಗ್ತಿದೆ - I have diarrhea)
nanige maisullu novu ide (ನನಗೆ ಮೈಸುಳ್ಳು ನೋವು ಇದೆ - I have body pain)
nanige shakti illa (ನನಗೆ ಶಕ್ತಿ ಇಲ್ಲ - I feel weak)
nanige nidde bartilla (ನನಗೆ ನಿದ್ದೆ ಬರ್ತಿಲ್ಲ - I can't sleep)
nanige usiru aata (ನನಗೆ ಉಸಿರಾಟ - breathing problem)
jwara, kemmu, thalenovu, hotte novu, gantalu novu, vaanthi, sheetha, bedi, novu, arogya""",

    # ----------------- HINDI -----------------
    'hi': """हिंदी चिकित्सा वार्तालाप. Hindi medical phrases:
mujhe bukhar hai (मुझे बुखार है - I have fever)
mujhe khansi hai (मुझे खांसी है - I have cough)
mujhe sir dard hai (मुझे सिर दर्द है - I have headache)
mujhe pet dard hai (मुझे पेट दर्द है - I have stomach pain)
mujhe gala dard hai (मुझे गला दर्द है - I have sore throat)
mujhe ulti ho rahi hai (मुझे उल्टी हो रही है - I am vomiting)
mujhe sardi hai (मुझे सर्दी है - I have cold)
mujhe dast hai (मुझे दस्त है - I have diarrhea)
mujhe badan dard hai (मुझे बदन दर्द है - I have body pain)
mujhe kamzori hai (मुझे कमज़ोरी है - I feel weak)
mujhe neend nahi aati (मुझे नींद नहीं आती - I can't sleep)
mujhe sans lene mein taklif hai (मुझे सांस लेने में तकलीफ है - breathing problem)
bukhar, khansi, dard, pet, sir, gala, ulti, sardi, dast, kamzori, neend, sans, taklif, bimari, dawai""",

    # ----------------- TAMIL -----------------
    'ta': """தமிழ் மருத்துவ உரையாடல். Tamil medical phrases:
enakku kaichal irukku (எனக்கு காய்ச்சல் இருக்கு - I have fever)
enakku irumal irukku (எனக்கு இருமல் இருக்கு - I have cough)
enakku thalai vali irukku (எனக்கு தலைவலி இருக்கு - I have headache)
enakku vayiru vali irukku (எனக்கு வயிறு வலி இருக்கு - I have stomach pain)
enakku thondai vali irukku (எனக்கு தொண்டை வலி இருக்கு - I have sore throat)
enakku vaanthi varuthu (எனக்கு வாந்தி வருது - I am vomiting)
enakku jalam irukku (எனக்கு ஜலம் இருக்கு - I have cold)
enakku vayitru pokku (எனக்கு வயிற்றுப்போக்கு - I have diarrhea)
enakku udambu vali (எனக்கு உடம்பு வலி - I have body pain)
enakku saavu irukku (எனக்கு சோர்வு இருக்கு - I feel weak)
kaichal, irumal, vali, vayiru, thalai, thondai, vaanthi, jalam, udambu, saavu, thookam, moochu""",

    # ----------------- TELUGU -----------------
    'te':  """తెలుగు వైద్య సంభాషణ. Telugu medical phrases:
naaku jwaram undi (నాకు జ్వరం ఉంది - I have fever)
naaku dabbhu undi (నాకు దగ్గు ఉంది - I have cough)
naaku tala noppi undi (నాకు తల నొప్పి ఉంది - I have headache)
naaku kadupu noppi undi (నాకు కడుపు నొప్పి ఉంది - I have stomach pain)
naaku gonthu noppi undi (నాకు గొంతు నొప్పి ఉంది - I have sore throat)
naaku vamthulu vastunnai (నాకు వాంతులు వస్తున్నాయి - I am vomiting)
naaku jalabu chesindi (నాకు జలుబు చేసింది - I have cold)
naaku virechanaalu (నాకు విరేచనాలు - I have diarrhea)
naaku oththi noppi (నాకు ఒళ్ళు నొప్పి - I have body pain)
naaku balagam ledu (నాకు బలగం లేదు - I feel weak)
jwaram, dabbhu, noppi, kadupu, tala, gonthu, vamthulu, jalabu, virechanalu, balagam, nidra""",

    # ----------------- MALAYALAM -----------------
    'ml':  """മലയാളം വൈദ്യ സംഭാഷണം. Malayalam medical phrases:
enikku pani und (എനിക്ക് പനി ഉണ്ട് - I have fever)
enikku chuma und (എനിക്ക് ചുമ ഉണ്ട് - I have cough)
enikku thala vedana und (എനിക്ക് തലവേദന ഉണ്ട് - I have headache)
enikku vayaru vedana und (എനിക്ക് വയറു വേദന ഉണ്ട് - I have stomach pain)
enikku thonda vedana und (എനിക്ക് തൊണ്ട വേദന ഉണ്ട് - I have sore throat)
enikku okkanam varunnu (എനിക്ക് ഓക്കാനം വരുന്നു - I am vomiting)
enikku jaladhosham und (എനിക്ക് ജലദോഷം ഉണ്ട് - I have cold)
enikku vayaru ilakunnu (എനിക്ക് വയറിളക്കം - I have diarrhea)
enikku udal vedana (എനിക്ക് ഉടൽ വേദന - I have body pain)
enikku ksheenam (എനിക്ക് ക്ഷീണം - I feel weak)
pani, chuma, vedana, vayaru, thala, thonda, okkanam, jaladhosham, udal, ksheenam, urakam, shwasam""",

    # ----------------- MARATHI -----------------
    'mr': """मराठी वैद्यकीय संभाषण. Marathi medical phrases:
mala taap aahey (मला ताप आहे - I have fever)
mala khokhla aahey (मला खोकला आहे - I have cough)
mala dokey dukhte (मला डोके दुखते - I have headache)
mala pot dukhte (मला पोट दुखते - I have stomach pain)
mala ghasa dukhto (मला घसा दुखतो - I have sore throat)
mala ulti hote (मला उलटी होते - I am vomiting)
mala sardi zali (मला सर्दी झाली - I have cold)
mala jullab aahey (मला जुलाब आहे - I have diarrhea)
mala ang dukhte (मला अंग दुखते - I have body pain)
mala kamzori vatey (मला कमज़ोरी वाटते - I feel weak)
taap, khokhla, dukhte, pot, dokey, ghasa, ulti, sardi, jullab, ang, kamzori, zhop, shwas""",

    # ----------------- BENGALI -----------------
    'bn':  """বাংলা চিকিৎসা কথোপকথন. Bengali medical phrases:
amar jor hoyeche (আমার জ্বর হয়েছে - I have fever)
amar kashi hoyeche (আমার কাশি হয়েছে - I have cough)
amar matha byatha (আমার মাথা ব্যথা - I have headache)
amar pet byatha (আমার পেট ব্যথা - I have stomach pain)
amar gola byatha (আমার গলা ব্যথা - I have sore throat)
amar bomi hocche (আমার বমি হচ্ছে - I am vomiting)
amar thanda legechhe (আমার ঠান্ডা লেগেছে - I have cold)
amar diarrhea hoyeche (আমার ডায়রিয়া হয়েছে - I have diarrhea)
amar gaye byatha (আমার গায়ে ব্যথা - I have body pain)
amar durbolota (আমার দুর্বলতা - I feel weak)
jor, kashi, byatha, pet, matha, gola, bomi, thanda, gaye, durbolota, ghum, shwas""",

    # ----------------- GUJARATI -----------------
    'gu': """ગુજરાતી તબીબી વાતચીત. Gujarati medical phrases:
mane taav che (મને તાવ છે - I have fever)
mane khansi che (મને ખાંસી છે - I have cough)
mane mathanu dard che (મને માથાનું દર્દ છે - I have headache)
mane petma dard che (મને પેટમાં દર્દ છે - I have stomach pain)
mane gala ma dard che (મને ગળામાં દર્દ છે - I have sore throat)
mane ulti thay che (મને ઉલટી થાય છે - I am vomiting)
mane shardi che (મને શરદી છે - I have cold)
mane julab che (મને ઝાડા છે - I have diarrhea)
mane ange dard che (મને અંગે દર્દ છે - I have body pain)
mane nablai che (મને નબળાઈ છે - I feel weak)
taav, khansi, dard, pet, mathu, galu, ulti, shardi, julab, ang, nablai, nidra, shwas""",

    # ----------------- PUNJABI -----------------
    'pa':  """ਪੰਜਾਬੀ ਮੈਡੀਕਲ ਗੱਲਬਾਤ.  Punjabi medical phrases:
mainu bukhar hai (ਮੈਨੂੰ ਬੁਖਾਰ ਹੈ - I have fever)
mainu khansi hai (ਮੈਨੂੰ ਖੰਘ ਹੈ - I have cough)
mainu sir dard hai (ਮੈਨੂੰ ਸਿਰ ਦਰਦ ਹੈ - I have headache)
mainu pait dard hai (ਮੈਨੂੰ ਪੇਟ ਦਰਦ ਹੈ - I have stomach pain)
mainu gala dard hai (ਮੈਨੂੰ ਗਲਾ ਦਰਦ ਹੈ - I have sore throat)
mainu ulti aundi hai (ਮੈਨੂੰ ਉਲਟੀ ਆਉਂਦੀ ਹੈ - I am vomiting)
mainu zukam hai (ਮੈਨੂੰ ਜ਼ੁਕਾਮ ਹੈ - I have cold)
mainu dast lagge ne (ਮੈਨੂੰ ਦਸਤ ਲੱਗੇ ਨੇ - I have diarrhea)
mainu jism dard hai (ਮੈਨੂੰ ਜਿਸਮ ਦਰਦ ਹੈ - I have body pain)
mainu kamzori hai (ਮੈਨੂੰ ਕਮਜ਼ੋਰੀ ਹੈ - I feel weak)
bukhar, khansi, dard, pait, sir, gala, ulti, zukam, dast, jism, kamzori, nind, saah""",

    # ----------------- ODIA -----------------
    'or':  """ଓଡ଼ିଆ ଚିକିତ୍ସା ବାର୍ତ୍ତାଳାପ. Odia medical phrases:
mora jara heichi (ମୋର ଜ୍ୱର ହେଇଛି - I have fever)
mora khansi heichi (ମୋର କାଶ ହେଇଛି - I have cough)
mora munda bedana (ମୋର ମୁଣ୍ଡ ବେଦନା - I have headache)
mora peta bedana (ମୋର ପେଟ ବେଦନା - I have stomach pain)
mora gala bedana (ମୋର ଗଳା ବେଦନା - I have sore throat)
mora banti heuachi (ମୋର ବାନ୍ତି ହେଉଅଛି - I am vomiting)
mora thanda lagichi (ମୋର ଥଣ୍ଡା ଲାଗିଛି - I have cold)
mora jhada heichi (ମୋର ଝାଡ଼ା ହେଇଛି - I have diarrhea)
mora gaa bedana (ମୋର ଗା ବେଦନା - I have body pain)
mora durbalta (ମୋର ଦୁର୍ବଳତା - I feel weak)
jara, khansi, bedana, peta, munda, gala, banti, thanda, jhada, gaa, durbalta, nidra, swas""",

    # ----------------- ASSAMESE -----------------
    'as':  """অসমীয়া চিকিৎসা বাৰ্তালাপ.  Assamese medical phrases:
mur jor hoise (মোৰ জ্বৰ হৈছে - I have fever)
mur kah hoise (মোৰ কাহ হৈছে - I have cough)
mur mur bisa (মোৰ মূৰ বিষা - I have headache)
mur pet bisa (মোৰ পেট বিষা - I have stomach pain)
mur deha bisa (মোৰ দেহ বিষা - I have body pain)
mur durbolota (মোৰ দুৰ্বলতা - I feel weak)
jor, kah, bisa, pet, mur, deha, durbolota, nidra""",

    # ----------------- URDU -----------------
    'ur':  """اردو طبی گفتگو. Urdu medical phrases:
mujhe bukhar hai (مجھے بخار ہے - I have fever)
mujhe khansi hai (مجھے کھانسی ہے - I have cough)
mujhe sar dard hai (مجھے سر درد ہے - I have headache)
mujhe pait dard hai (مجھے پیٹ درد ہے - I have stomach pain)
mujhe gala dard hai (مجھے گلا درد ہے - I have sore throat)
mujhe ulti ho rahi hai (مجھے الٹی ہو رہی ہے - I am vomiting)
mujhe zukam hai (مجھے زکام ہے - I have cold)
mujhe dast hai (مجھے دست ہے - I have diarrhea)
mujhe jism dard hai (مجھے جسم درد ہے - I have body pain)
mujhe kamzori hai (مجھے کمزوری ہے - I feel weak)
bukhar, khansi, dard, pait, sar, gala, ulti, zukam, dast, jism, kamzori, neend, sans""",

    # ----------------- NEPALI -----------------
    'ne':  """नेपाली चिकित्सा वार्तालाप. Nepali medical phrases:
malai jwaro cha (मलाई ज्वरो छ - I have fever)
malai khoki lagyo (मलाई खोकी लाग्यो - I have cough)
mero tauko dukhyo (मेरो टाउको दुख्यो - I have headache)
mero pet dukhyo (मेरो पेट दुख्यो - I have stomach pain)
mero ghanti dukhyo (मेरो घाँटी दुख्यो - I have sore throat)
malai banta lagyo (मलाई बान्ता लाग्यो - I am vomiting)
malai rugha lagyo (मलाई रुघा लाग्यो - I have cold)
malai disha lagyo (मलाई दिशा लाग्यो - I have diarrhea)
mero jiu dukhyo (मेरो जिउ दुख्यो - I have body pain)
malai kamjori cha (मलाई कमजोरी छ - I feel weak)
jwaro, khoki, dukhyo, pet, tauko, ghanti, banta, rugha, disha, jiu, kamjori, nidra, swas""",

    # ----------------- SINDHI -----------------
    'sd':  """سنڌي طبي ڳالھ ٻولھ. Sindhi medical phrases:
maan khay tav aahe (مون کي تاءُ آهي - I have fever)
maan khay khansi aahe (مون کي کنسي آهي - I have cough)
maan khay sir dard aahe (مون کي سر درد آهي - I have headache)
maan khay pet dard aahe (مون کي پيٽ درد آهي - I have stomach pain)
tav, khansi, dard, pet, sir""",

    # ----------------- SANSKRIT -----------------
    'sa': """संस्कृत चिकित्सा संवादः. Sanskrit medical phrases:
mama jvarah asti (मम ज्वरः अस्ति - I have fever)
mama kasah asti (मम कासः अस्ति - I have cough)
mama shirah vedana (मम शिरः वेदना - I have headache)
mama udara vedana (मम उदर वेदना - I have stomach pain)
jvarah, kasah, vedana, udara, shirah""",

    # ----------------- ENGLISH -----------------
    'en': """Medical conversation.  Common symptoms and conditions:
I have fever, I have cough, I have headache, I have stomach pain,
I have sore throat, I am vomiting, I have cold, I have diarrhea,
I have body pain, I feel weak, I can't sleep, breathing problem,
chest pain, back pain, joint pain, skin rash, allergy, infection,
fever, cough, cold, headache, stomach, throat, vomiting, diarrhea,
body pain, weakness, insomnia, breathing, chest, back, joint, skin, allergy"""
}


# =============================================================================
# CORE TRANSCRIPTION FUNCTIONS
# =============================================================================

def get_whisper_language(language_code:  str) -> str:
    """Get Whisper-compatible language code from input language code"""
    # Clean the code
    lang = language_code.lower().strip()
    
    # Check in our mapping
    if lang in INDIAN_LANGUAGES:
        return INDIAN_LANGUAGES[lang]['whisper']
    
    # Try base language (e.g., 'kn-IN' -> 'kn')
    base_lang = lang.split('-')[0]
    if base_lang in INDIAN_LANGUAGES:
        return INDIAN_LANGUAGES[base_lang]['whisper']
    
    # Default to English
    return 'en'


def get_medical_prompt(language_code: str) -> str:
    """Get medical prompt for the specified language"""
    whisper_lang = get_whisper_language(language_code)
    return MEDICAL_PROMPTS. get(whisper_lang, MEDICAL_PROMPTS['en'])


def get_language_info(language_code: str) -> Dict:
    """Get full language info"""
    lang = language_code. lower().strip()
    
    if lang in INDIAN_LANGUAGES:
        return INDIAN_LANGUAGES[lang]
    
    base_lang = lang.split('-')[0]
    if base_lang in INDIAN_LANGUAGES: 
        return INDIAN_LANGUAGES[base_lang]
    
    return INDIAN_LANGUAGES['en']


def transcribe_with_whisper(
    audio_path: str,
    language:  str = 'en',
    use_medical_prompt: bool = True
) -> Dict:
    """
    Transcribe audio using OpenAI Whisper with language-specific medical prompting
    
    Args:
        audio_path: Path to the audio file
        language: Language code (e.g., 'kn', 'hi', 'ta', 'te', 'ml', 'bn', 'mr', 'gu', 'pa', etc.)
        use_medical_prompt: Whether to use medical context prompting
        
    Returns:
        Dict with transcription results
    """
    if not WHISPER_AVAILABLE:
        return {
            'success': False,
            'transcription': '',
            'confidence': 0,
            'error': 'Whisper not available',
            'method': 'whisper-1'
        }
    
    try:
        # Get Whisper language code
        whisper_lang = get_whisper_language(language)
        lang_info = get_language_info(language)
        
        # Get medical prompt for the language
        prompt = None
        if use_medical_prompt:
            prompt = get_medical_prompt(language)
        
        logger.info(f"🎤 Whisper transcription:  language={whisper_lang} ({lang_info['name']}), prompted={bool(prompt)}")
        
        # Open and transcribe
        with open(audio_path, 'rb') as audio_file:
            # Use transcriptions.create (keeps original language)
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=whisper_lang,
                prompt=prompt,
                response_format="verbose_json"
            )
        
        # Extract results
        transcription = response.text if hasattr(response, 'text') else str(response)
        
        # Calculate confidence
        confidence = 0.85
        if hasattr(response, 'segments') and response.segments:
            confidences = [
                seg.get('avg_logprob', -0.5) 
                for seg in response.segments 
                if isinstance(seg, dict)
            ]
            if confidences:
                # Convert log probability to confidence (rough approximation)
                avg_logprob = sum(confidences) / len(confidences)
                confidence = min(max(1.0 + (avg_logprob / 2), 0.3), 0.99)
        
        logger.info(f"✅ Whisper result ({lang_info['name']}): '{transcription}' (confidence: {confidence:.2%})")
        
        return {
            'success': True,
            'transcription': transcription,
            'confidence': confidence,
            'language': whisper_lang,
            'language_name': lang_info['name'],
            'language_native': lang_info['native'],
            'method': 'whisper-1',
            'prompted': use_medical_prompt
        }
        
    except Exception as e: 
        logger.error(f"❌ Whisper transcription error: {e}", exc_info=True)
        return {
            'success': False,
            'transcription': '',
            'confidence': 0,
            'error': str(e),
            'method': 'whisper-1'
        }


def translate_audio_to_english(
    audio_path: str,
    source_language: str = 'auto'
) -> Dict:
    """
    Transcribe audio in any Indian language and translate to English
    
    Args:
        audio_path: Path to the audio file
        source_language: Source language code (or 'auto' for auto-detect)
        
    Returns: 
        Dict with English translation
    """
    if not WHISPER_AVAILABLE: 
        return {
            'success':  False,
            'translation': '',
            'confidence': 0,
            'error': 'Whisper not available'
        }
    
    try:
        # Get medical prompt
        prompt = get_medical_prompt(source_language) if source_language != 'auto' else MEDICAL_PROMPTS['en']
        
        with open(audio_path, 'rb') as audio_file:
            # Use translations.create (translates to English)
            response = client.audio.translations.create(
                model="whisper-1",
                file=audio_file,
                prompt=prompt,
                response_format="verbose_json"
            )
        
        translation = response.text if hasattr(response, 'text') else str(response)
        
        logger.info(f"✅ Whisper translation to English: '{translation}'")
        
        return {
            'success': True,
            'translation':  translation,
            'source_language': source_language,
            'target_language': 'en',
            'confidence': 0.85,
            'method': 'whisper-1-translate'
        }
        
    except Exception as e:
        logger.error(f"❌ Whisper translation error: {e}", exc_info=True)
        return {
            'success': False,
            'translation':  '',
            'confidence': 0,
            'error': str(e)
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_supported_languages() -> Dict:
    """Get all supported Indian languages"""
    languages = {}
    for code, info in INDIAN_LANGUAGES.items():
        if '-' not in code:  # Only base language codes
            languages[code] = {
                'name': info['name'],
                'native': info['native'],
                'whisper_supported': info['whisper'] == code
            }
    return languages


def is_language_supported(language_code: str) -> bool:
    """Check if a language is supported"""
    lang = language_code.lower().strip()
    return lang in INDIAN_LANGUAGES or lang. split('-')[0] in INDIAN_LANGUAGES