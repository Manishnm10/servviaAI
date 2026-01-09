"""
ServVIA TTS Endpoints
=====================
- synthesise_audio: Original endpoint (full audio, slower)
- fast_audio: New fast-start endpoint (chunked, instant playback)
"""

from django.http import JsonResponse
from django. views.decorators. csrf import csrf_exempt
import json
import logging
import base64

logger = logging.getLogger(__name__)

# Import the TTS processing function
from api.utils import process_output_audio


@csrf_exempt
def synthesise_audio(request):
    """
    Original TTS endpoint - Generate full audio from text. 
    Used as fallback when fast_audio fails.
    """
    
    # Handle OPTIONS request (CORS preflight)
    if request.method == "OPTIONS":
        response = JsonResponse({})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response
    
    # Handle POST request
    if request.method == "POST": 
        try:
            # Parse POST request data
            if request. content_type == 'application/json': 
                data = json.loads(request. body) if request.body else {}
            else:
                data = dict(request. POST)
            
            # Extract text and message_id from request
            original_text = data.get('text', '')
            message_id = data.get('message_id', None)
            email_id = data.get('email_id', 'user@servvia. com')
            
            # Handle list values (from form data)
            if isinstance(original_text, list):
                original_text = original_text[0] if original_text else ''
            if isinstance(message_id, list):
                message_id = message_id[0] if message_id else None
            if isinstance(email_id, list):
                email_id = email_id[0] if email_id else 'user@servvia.com'
            
            logger.info(f"TTS:  Processing '{original_text[: 50]}...'")
            
            if not original_text or not str(original_text).strip():
                return JsonResponse({
                    "success": False,
                    "error": True,
                    "message": "Please submit text for audio synthesis.",
                    "audio": None
                }, status=400)

            # Process the text to audio
            response_audio = process_output_audio(original_text, message_id)

            if not response_audio: 
                logger.error("Failed to generate audio")
                return JsonResponse({
                    "success": False,
                    "error": True,
                    "message": "Unable to generate audio currently.",
                    "audio": None
                }, status=500)

            logger.info("Audio synthesis successful")
            
            response = JsonResponse({
                "success": True,
                "error": False,
                "text": original_text,
                "audio":  response_audio,
                "message": "Audio synthesis successful"
            })
            response["Access-Control-Allow-Origin"] = "*"
            return response
                
        except Exception as e: 
            logger.error(f"TTS Error: {e}", exc_info=True)
            return JsonResponse({
                "success": False,
                "error": True,
                "message": f"Error:  {str(e)}",
                "audio": None
            }, status=500)
    
    # Handle other methods
    return JsonResponse({
        "error": "Method not allowed",
        "allowed_methods":  ["POST", "OPTIONS"]
    }, status=405)


@csrf_exempt
def fast_audio(request):
    """
    Fast-start TTS endpoint - Returns audio in chunks for instant playback.
    
    Modes:
        'first':  Returns first chunk quickly (~2-3 seconds) for immediate playback
        'remaining': Returns remaining chunks (called while first chunk plays)
        'full': Returns complete audio (fallback)
    
    Usage:
        1. Frontend calls with mode='first' → gets first chunk, starts playing
        2. Frontend calls with mode='remaining' in background
        3. When first chunk ends, seamlessly plays remaining audio
    """
    
    # Handle OPTIONS request (CORS preflight)
    if request.method == "OPTIONS":
        response = JsonResponse({})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        return response
    
    if request.method != "POST":
        return JsonResponse({
            "error": "Method not allowed",
            "allowed_methods": ["POST", "OPTIONS"]
        }, status=405)
    
    try: 
        # Parse request data
        if request. content_type == 'application/json': 
            data = json.loads(request. body) if request.body else {}
        else:
            data = dict(request. POST)
        
        text = data.get('text', '')
        mode = data.get('mode', 'first')  # 'first', 'remaining', or 'full'
        
        # Handle list values
        if isinstance(text, list):
            text = text[0] if text else ''
        if isinstance(mode, list):
            mode = mode[0] if mode else 'first'
        
        if not text or not str(text).strip():
            return JsonResponse({
                "success": False,
                "error": "No text provided"
            }, status=400)
        
        # Import fast TTS functions
        from language_service. fast_tts import (
            generate_first_chunk_fast,
            generate_remaining_chunks,
            generate_full_audio
        )
        
        if mode == 'first':
            # =============================================
            # FIRST CHUNK - For immediate playback (~2-3s)
            # =============================================
            logger.info(f"FastTTS [first]: {len(text)} chars")
            
            first_audio, has_more = generate_first_chunk_fast(text, voice="nova")
            
            if first_audio:
                response = JsonResponse({
                    "success":  True,
                    "audio": base64.b64encode(first_audio).decode('utf-8'),
                    "has_more": has_more,
                    "mode": "first"
                })
                response["Access-Control-Allow-Origin"] = "*"
                return response
            else: 
                return JsonResponse({
                    "success": False,
                    "error":  "Failed to generate first chunk"
                }, status=500)
        
        elif mode == 'remaining':
            # =============================================
            # REMAINING CHUNKS - Called while first plays
            # =============================================
            logger. info(f"FastTTS [remaining]:  {len(text)} chars")
            
            remaining_audio = generate_remaining_chunks(text, voice="nova")
            
            response = JsonResponse({
                "success": True,
                "audio": base64.b64encode(remaining_audio).decode('utf-8') if remaining_audio else None,
                "mode": "remaining"
            })
            response["Access-Control-Allow-Origin"] = "*"
            return response
        
        else:  # mode == 'full'
            # =============================================
            # FULL AUDIO - Fallback, returns everything
            # =============================================
            logger. info(f"FastTTS [full]:  {len(text)} chars")
            
            full_audio = generate_full_audio(text, voice="nova")
            
            if full_audio: 
                response = JsonResponse({
                    "success": True,
                    "audio":  base64.b64encode(full_audio).decode('utf-8'),
                    "mode": "full"
                })
                response["Access-Control-Allow-Origin"] = "*"
                return response
            else:
                return JsonResponse({
                    "success": False,
                    "error": "Failed to generate audio"
                }, status=500)
    
    except Exception as e:
        logger.error(f"FastTTS error: {e}", exc_info=True)
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)