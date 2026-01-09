from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from django.http import JsonResponse

# Import your views
from api.views import ChatAPIViewSet, LanguageViewSet
from api.audio_endpoint import transcribe_audio
from api.tts_endpoint import synthesise_audio, fast_audio

# Router for ViewSets
router = DefaultRouter()
router.register(r"chat", ChatAPIViewSet, basename="chat")
router.register(r"language", LanguageViewSet, basename="language")

urlpatterns = [
    # ============================================================
    # SPEECH-TO-TEXT (STT) ENDPOINTS - MUST COME FIRST! 
    # ============================================================
    path("chat/transcribe_audio/", transcribe_audio, name="transcribe-audio-single"),
    path("api/chat/transcribe_audio/", transcribe_audio, name="transcribe-audio"),
    path("speech/transcribe/", transcribe_audio, name="speech-transcribe"),

    # ============================================================
    # TEXT-TO-SPEECH (TTS) ENDPOINTS
    # ============================================================
    path("chat/synthesise_audio/", synthesise_audio, name="synthesise-audio"),
    path("chat/fast_audio/", fast_audio, name="fast-audio"),
    path("/synthesise_audio/", synthesise_audio, name="synthesise-audio"),
    path("speech/synthesize/", synthesise_audio, name="speech-synthesize"),

    # ============================================================
    # LANGUAGE SUPPORT ENDPOINT
    # ============================================================
    path("speech/languages/", 
         lambda request: JsonResponse({"success": True, "languages": get_supported_languages()}),
         name="speech-languages"),
    
    # ============================================================
    # ViewSet routes (MUST COME LAST!)
    # ============================================================
    path("", include(router.urls)),
]