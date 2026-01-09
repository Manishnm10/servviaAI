from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def get_supported_languages(request):
    """
    Return supported languages for ServVIA - Pure Django implementation
    """
    
    supported_languages = [
        {"code": "en", "name": "English", "native_name": "English"},
        {"code": "es", "name": "Spanish", "native_name": "Español"},
        {"code": "fr", "name": "French", "native_name": "Français"},
        {"code": "de", "name": "German", "native_name": "Deutsch"},
        {"code": "it", "name": "Italian", "native_name": "Italiano"},
        {"code": "pt", "name": "Portuguese", "native_name": "Português"},
        {"code": "ar", "name": "Arabic", "native_name": "العربية"},
        {"code": "hi", "name": "Hindi", "native_name": "हिन्दी"},
        {"code": "zh", "name": "Chinese", "native_name": "中文"},
        {"code": "ja", "name": "Japanese", "native_name": "日本語"},
        {"code": "ru", "name": "Russian", "native_name": "Русский"},
    ]
    
    return JsonResponse({
        "success": True,
        "languages": supported_languages,
        "default_language": "en",
        "message": "Languages loaded successfully"
    })