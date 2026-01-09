import asyncio
import datetime
import json
import logging
import os
import uuid

from common.constants import Constants
from common.utils import (
    create_or_update_user_by_email,
    decode_base64_to_binary,
    encode_binary_to_base64,
    fetch_corresponding_multilingual_text,
    fetch_multilingual_texts_for_static_text_messages,
    get_message_object_by_id,
    get_or_create_latest_conversation,
    get_or_create_user_by_email,
    get_user_by_email,
    get_user_chat_history,
    insert_message_record,
    postprocess_and_translate_query_response,
    save_message_obj,
    send_request,
)
from database.database_config import db_conn
from database.db_operations import update_record
from database.models import User
from django_core.config import Config
from intent_classification.intent import process_user_intent
from language_service.asr import transcribe_and_translate
from language_service.translation import (
    a_translate_to,
    detect_language_and_translate_to_english,
)
from language_service.tts import synthesize_speech
from language_service.utils import get_language_by_id
from rag_service.execute_rag import execute_rag_pipeline

logger = logging.getLogger(__name__)


def authenticate_user_based_on_email(email_id):
    """Authenticate user - bypass Farmstack auth when WITH_DB_CONFIG=False"""
    authenticated_user = None
    try:
        if not Config.WITH_DB_CONFIG:
            if email_id and '@' in email_id:
                logger.info(f"Creating mock authenticated user for: {email_id}")
                return {
                    "email": email_id,
                    "first_name": "User",
                    "phone_number": None,
                    "last_name": "",
                    "access_token": "bypass-mode"
                }
            return None
        
        # Original Farmstack authentication
        authentication_url = f"{Config.CONTENT_DOMAIN_URL}{Config.CONTENT_AUTHENTICATE_ENDPOINT}"
        response = send_request(
            authentication_url,
            data={"email": email_id},
            content_type="JSON",
            request_type="POST",
            total_retry=3,
        )
        authenticated_user = (
            json.loads(response.text)
            if response and response.status_code == 200
            else None
        )
    except Exception as error:
        logger.error(error, exc_info=True)
    return authenticated_user


def preprocess_user_data(
    original_query,
    email_id,
    authenticated_user={},
    with_db_config=Config.WITH_DB_CONFIG,
    message_input_type=Constants.MESSAGE_INPUT_TYPE_TEXT,
):
    user_name, message_id, message_obj, user_id = None, None, None, None
    user_data, message_data_to_insert_or_update = {}, {}
    try:
        if len(authenticated_user) >= 1:
            user_data.update({"user_name": authenticated_user.get("first_name")})

        if with_db_config and len(authenticated_user) >= 1:
            user_obj = create_or_update_user_by_email(
                {
                    "email": email_id,
                    "phone": authenticated_user.get("phone_number", None),
                    "first_name": authenticated_user.get("first_name", None),
                    "last_name": authenticated_user.get("last_name", None),
                }
            )
            user_id = user_obj.id
            user_name = user_obj.first_name

            conversation_obj = get_or_create_latest_conversation(
                {"user_id": user_id, "title": original_query}
            )
            message_obj = insert_message_record(
                {"original_message": original_query, "conversation_id": conversation_obj}
            )
            message_id = message_obj.id
            message_data_to_insert_or_update["input_type"] = message_input_type
            message_data_to_insert_or_update["message_input_time"] = datetime.datetime.now()

            user_data.update({"user_id": user_id, "user_name": user_name, "message_id": message_id})

    except Exception as error:
        logger.error(error, exc_info=True)
    finally:
        if message_obj and message_id:
            save_message_obj(message_id, message_data_to_insert_or_update)
    return user_data, message_obj


def process_query(original_query, email_id, authenticated_user={}):
    """
    Process query with user profile integration and RAG pipeline (no intent gating).
    """
    message_obj, chat_history = None, None
    (response_map, message_data_to_insert_or_update, message_data_update_post_rag_pipeline) = ({}, {}, {})
    
    try:
        logger.info(f"Processing query for {email_id}: {original_query}")
        
        user_data, message_obj = preprocess_user_data(original_query, email_id, authenticated_user)

        user_id = user_data.get("user_id", None)
        user_name = user_data.get("user_name", None)
        message_id = user_data.get("message_id", None)
        chat_history = get_user_chat_history(user_id) if user_id else None

        # Translate to English
        message_data_to_insert_or_update["input_translation_start_time"] = datetime.datetime.now()
        query_in_english, input_language_detected = asyncio.run(
            detect_language_and_translate_to_english(original_query)
        )
        logger.info(f"Detected language: {input_language_detected}")
        
        message_data_to_insert_or_update["translated_message"] = query_in_english
        message_data_to_insert_or_update["input_translation_end_time"] = datetime.datetime.now()
        message_data_to_insert_or_update["input_language_detected"] = input_language_detected

        # BYPASS INTENT GATING - Always use RAG
        proceed_to_rag = True
        logger.info("Intent gating bypassed; executing RAG pipeline.")

        # Load user profile for personalized responses
        user_profile_data = None
        if email_id:
            try:
                from user_profile.models import UserProfile
                profile = UserProfile.objects.get(email=email_id)
                user_profile_data = {
                    'allergies': profile.get_allergies_list(),
                    'medical_conditions': profile.get_conditions_list(),
                    'current_medications': profile.get_medications_list(),
                    'first_name': profile.first_name,
                    'age': profile.age,
                    'sex': profile.sex,
                    'age_group': profile.get_age_group(),
                }
                if profile.first_name:
                    user_name = profile.first_name
            
                logger.info(f"Loaded profile for {email_id}: {profile.first_name}, age:  {profile.age}, sex: {profile.sex}")
                if user_profile_data. get('allergies'):
                    logger.info(f"User allergies: {user_profile_data['allergies']}")
            except Exception as e:
                logger.info(f"No profile found for {email_id}:  {e}")
                user_profile_data = None
            

            # Execute RAG pipeline with user profile
            response_map, message_data_update_post_rag_pipeline = execute_rag_pipeline(
                query_in_english,
                input_language_detected,
                email_id,
                user_name=user_name,
                message_id=message_id,
                chat_history=chat_history,
                user_profile=user_profile_data,
            )
        else:
            response_map.update({"generated_final_response": None})

        # Translate response back to input language
        (
            translated_response,
            final_response,
            follow_up_question_options,
            follow_up_question_data_to_insert,
        ) = asyncio.run(
            postprocess_and_translate_query_response(
                response_map.get("generated_final_response"),
                input_language_detected,
                str(message_id),
            )
        )

        response_map.update(
            {
                "translated_response": translated_response,
                "final_response": final_response,
                "source": response_map.get("source", None),
                "follow_up_questions": follow_up_question_options,
            }
        )

        message_data_to_insert_or_update["message_response"] = final_response
        message_data_to_insert_or_update["message_translated_response"] = translated_response
        message_data_to_insert_or_update.update(message_data_update_post_rag_pipeline)
        
        logger.info(f"Query processed successfully for {email_id}")

    except Exception as error:
        logger.error(error, exc_info=True)
    finally:
        if message_obj and message_id:
            save_message_obj(message_id, message_data_to_insert_or_update)
    return response_map


def process_input_audio_to_base64(
    original_text,
    message_id=None,
    language_code=Constants.LANGUAGE_SHORT_CODE_NATIVE,
    with_db_config=Config.WITH_DB_CONFIG,
):
    input_audio, input_audio_file = None, None
    try:
        translated_text = asyncio.run(a_translate_to(original_text, language_code))
        input_audio_file = asyncio.run(synthesize_speech(str(translated_text), language_code, message_id))
        input_audio = encode_binary_to_base64(input_audio_file)
    except Exception as error:
        logger.error(error, exc_info=True)
    finally:
        if input_audio_file:
            os.remove(input_audio_file)
    return input_audio


def process_output_audio(original_text, message_id=None, with_db_config=Config.WITH_DB_CONFIG):
    """
    Synthesise output text to audio in detected language, and encode to base64 string.
    Uses SmartTTS for English (faster - reads only essential content).
    """
    response_audio = None
    input_language_detected = "en"

    try:
        # Detect language
        if not message_id: 
            try:
                query_in_english, input_language_detected = asyncio.run(
                    detect_language_and_translate_to_english(original_text)
                )
                logger.info(f"Detected language for TTS: {input_language_detected}")
            except Exception as lang_error:
                logger. warning(f"Language detection failed: {lang_error}, using English")
                input_language_detected = "en"
        
        logger.info(f"Synthesizing speech:  {len(original_text)} chars, language: {input_language_detected}")
        
        # ============================================
        # USE SMART TTS FOR ENGLISH (FASTER!)
        # ============================================
        if input_language_detected == "en":
            try:
                from language_service.fast_tts import generate_fast_tts_sync
                
                response_audio = generate_fast_tts_sync(original_text, voice="nova")
                
                if response_audio:
                    logger.info(f"✅ SmartTTS success")
                    return response_audio
                    
            except Exception as smart_tts_error:
                logger.warning(f"SmartTTS failed, falling back to standard:  {smart_tts_error}")
        
        # ============================================
        # FALLBACK:  STANDARD TTS (for other languages)
        # ============================================
        from language_service.tts import synthesize_speech
        
        response_audio_file = asyncio.run(
            synthesize_speech(str(original_text), input_language_detected, message_id)
        )

        if response_audio_file and os.path.exists(response_audio_file):
            response_audio = encode_binary_to_base64(response_audio_file)
            logger.info(f"✅ Standard TTS success: {os.path.getsize(response_audio_file)} bytes")
            
            # Cleanup temp file
            try:
                os.remove(response_audio_file)
            except Exception as e:
                logger.warning(f"Could not delete temp file: {e}")
        else:
            logger.error(f"Audio file not created: {response_audio_file}")

    except Exception as error: 
        logger.error(f"process_output_audio error: {error}", exc_info=True)

    return response_audio


def handle_input_query(input_query):
    file_name, input_query_file = None, None
    input_query_file = decode_base64_to_binary(input_query)
    if input_query_file:
        file_name = f"{uuid.uuid4()}_audio_input.{Constants.MP3}"
        with open(file_name, "wb") as output_file_buffer:
            output_file_buffer.write(input_query_file)
    return file_name


def process_transcriptions(
    voice_file,
    email_id,
    authenticated_user={},
    language_code=Constants.LANGUAGE_SHORT_CODE_NATIVE,
    language_bcp_code=Constants.LANGUAGE_BCP_CODE_NATIVE,
    message_input_type=Constants.MESSAGE_INPUT_TYPE_VOICE,
    with_db_config=Config.WITH_DB_CONFIG,
):
    message_id, message_obj = None, None
    response_map, message_data_to_insert_or_update, language_dict = {}, {}, {}
    try:
        if with_db_config:
            user = get_user_by_email(email_id)
            user_id = user.get("user_id")
            language_dict = get_language_by_id(user.get("preferred_language_id"))
            language_code = language_dict.get("code", language_code)

        text_codes_list_with_multilingual_texts = fetch_multilingual_texts_for_static_text_messages(
            [Constants.COULD_NOT_UNDERSTAND_MESSAGE], language_code
        )
        could_not_understand_message = fetch_corresponding_multilingual_text(
            Constants.COULD_NOT_UNDERSTAND_MESSAGE, text_codes_list_with_multilingual_texts
        )

        message_data_to_insert_or_update["message_input_time"] = datetime.datetime.now()
        message_data_to_insert_or_update["input_speech_to_text_start_time"] = datetime.datetime.now()
        transcriptions, detected_language, confidence_score = asyncio.run(
            transcribe_and_translate(voice_file, language_bcp_code)
        )
        message_data_to_insert_or_update["input_speech_to_text_end_time"] = datetime.datetime.now()

        response_map["confidence_score"] = confidence_score
        response_map["transcriptions"] = transcriptions

        if confidence_score < Constants.ASR_DEFAULT_CONFIDENCE_SCORE:
            message_data_to_insert_or_update["message_response"] = could_not_understand_message
            message_data_to_insert_or_update["message_translated_response"] = could_not_understand_message
            message_data_to_insert_or_update["message_response_time"] = datetime.datetime.now()
            message_data_to_insert_or_update["input_type"] = message_input_type
            response_map["transcriptions"] = could_not_understand_message

        user_data, message_obj = preprocess_user_data(transcriptions, email_id, authenticated_user)
        message_id = user_data.get("message_id", None)
        response_map["message_id"] = message_id

    except Exception as error:
        logger.error(error, exc_info=True)
    finally:
        if message_obj and message_id:
            save_message_obj(message_id, message_data_to_insert_or_update)
        if voice_file:
            os.remove(voice_file)
    return response_map
