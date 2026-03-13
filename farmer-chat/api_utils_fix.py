# Add this to the top of api/utils.py if not already there:
from django_core.config import Config

# Replace the authenticate_user_based_on_email function with this:
def authenticate_user_based_on_email(email_id):
    """
    Authenticate user based on email.
    When WITH_DB_CONFIG=False, bypass database authentication.
    """
    # Bypass authentication when database is disabled
    if not Config.WITH_DB_CONFIG:
        if email_id and '@' in email_id:
            logger.info(f"Bypassing database authentication for email: {email_id}")
            return {"email": email_id, "authenticated": True, "user_id": 1, "first_name": "Farmer"}
        return None
    
    # Original database authentication
    from common.utils import get_or_create_user_by_email
    from retrieval.search import get_access_token
    
    authenticated_user = None
    try:
        access_token = get_access_token(email_id)
        if access_token:
            user_data = {"email": email_id}
            authenticated_user = get_or_create_user_by_email(user_data)
    except Exception as error:
        logger.error(error, exc_info=True)
    
    return authenticated_user
