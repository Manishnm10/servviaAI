import asyncio
from google.cloud import translate_v2 as translate

async def translate_text_to_language(text, target_language_code):
    """
    Translate text to target language
    """
    try:
        translate_client = translate.Client()
        
        # Translate the text
        result = await asyncio.to_thread(
            translate_client.translate,
            text,
            target_language=target_language_code
        )
        
        return result['translatedText']
        
    except Exception as e:
        print(f"Translation to {target_language_code} failed: {e}")
        return text  # Return original text if translation fails