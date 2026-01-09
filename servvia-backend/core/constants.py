class Constants:
    CONTENT = "content"
    USER = "user"
    ORGANIZATION = "organization"
    ID = "id"
    EMAIL = "email"
    ORG_EMAIL = "org_email"
    TO_EMAIL = "to_email"
    SUPPORTTICKET = "supportticket"
    USER_ORGANIZATION_MAP = "userorganizationmap"
    USER_MAP = "user_map"
    USER_MAP_USER = "user_map__user"
    DATASETS = "datasets"
    DATASET = "dataset"
    USER_MAP_ORGANIZATION_ID = "user_map__organization__id"
    USER_MAP_ORGANIZATION = "user_map__organization"
    USER_ID = "user_id"
    UPDATED_AT = "updated_at"
    DESC_UPDATED_AT = "-updated_at"

    CREATED_AT = "created_at"
    EXCLUDE_DATES = ["created_at", "updated_at"]
    ALL = "__all__"
    SUPPORT = "support"
    PARTICIPANT = "participant"
    SUPPORT_TICKETS = "support_tickets"
    THEME = "theme"
    SAVE_DOCUMENTS = "save_documents"
    DROP_DOCUMENT = "drop_document"
    TEAM_MEMBER = "team_member"
    SEND_INVITE = "send_invite"
    USERROLE = "userrole"
    ORG_ID = "org_id"
    DATAHUB_DATASETS = "datahub_datasets"
    SEARCH_PATTERNS = "search_pattern"
    NAME_ICONTAINS = "name__icontains"
    SAMPLE_DATASET = "sample_dataset"
    RECORDS = "records"
    CONTENTS = "contents"
    OTHERS = "others"
    CREATED_AT__RANGE = "created_at__range"
    UPDATED_AT__RANGE = "updated_at__range"
    GEOGRAPHY = "geography"
    CROP_DETAIL = "crop_detail"
    PROJECT = "project"
    PROJECTS = "projects"
    DEPARTMENT = "department"
    DEPARTMENTS = "departments"
    CATEGORY = "category"
    SUBCATEGORY = "subcategory"
    PROVIDER_CORE = "provider_core"
    CONSUMER_CORE = "consumer_core"
    CONSUMER_APP = "consumer_app"
    PROVIDER_APP = "provider_app"
    DATAHUB = "datahub"
    GOVERNING_LAW = "governing_law"
    PRIVACY_POLICY = "privacy_policy"
    TOS = "tos"
    LIMITATIONS_OF_LIABILITIES = "limitations_of_liabilities"
    WARRANTY = "warranty"
    APPROVAL_STATUS = "approval_status"
    APPROVED = "approved"
    AWAITING_REVIEW = "for_review"
    IS_ENABLED = "is_enabled"
    DOCKER_IMAGE_URL = "docker_image_url"
    IMAGES = "images"
    DIGEST = "digest"
    USAGE_POLICY = "usage_policy"
    PROJECT_DEPARTMENT = "project__department"
    CONNECTOR_TYPE = "connector_type"
    CERTIFICATE = "certificate"
    CONSUMER = "consumer"
    CONSUMER_DATASET = "consumer__dataset"
    CONSUMER_PROJECT = "consumer__project"
    CONSUMER_PROJECT_DEPARTMENT = "consumer__project__department"
    CONSUMER_USER_MAP_ORGANIZATION = "consumer__user_map__organization"
    PAIRED = "paired"
    AWAITING_FOR_APPROVAL = "awaiting for approval"
    PROVIDER = "provider"
    PROVIDER_DATASET = "provider__dataset"
    PROVIDER_PROJECT = "provider__project"
    PROVIDER_PROJECT_DEPARTMENT = "provider__project__department"
    PROVIDER_USER_MAP_ORGANIZATION = "provider__user_map__organization"
    RELATION = "relation"
    PROJECT_PROJECT_NAME = "project__project_name"
    DATASET_USER_MAP = "dataset__user_map"
    DEPARTMENT_DEPARTMENT_NAME = "department__department_name"
    DEPARTMENT_ORGANIZATION = "department__organization"
    IS_DATASET_PRESENT = "is_dataset_present"
    DATASET_ID = "dataset_id"
    UNPAIRED = "unpaired"
    PAIRING_REQUEST_RECIEVED = "pairing request received"
    CONNECTOR_PAIR_STATUS = "connector_pair_status"
    REJECTED = "rejected"
    DEFAULT = "Default"
    ACTIVE = "Active"
    NOT_ACTIVE = "Not Active"
    RECENTLY_ACTIVE = "Recently Active"
    PARTICIPANT_INVITATION_SUBJECT = " has invited you to join as a participant"
    PARTICIPANT_ORG_ADDITION_SUBJECT = "Your organization has been added as a participant in "
    PARTICIPANT_ORG_UPDATION_SUBJECT = "Your organization details has been updated in "
    PARTICIPANT_ORG_DELETION_SUBJECT = "Your organization has been deleted as a participant in "
    ADDED_NEW_DATASET_SUBJECT = "A new dataset request has been uploaded in "
    UPDATED_DATASET_SUBJECT = "A dataset has been updated in "
    APPROVED_NEW_DATASET_SUBJECT = "Congratulations, your dataset has been approved on "
    REJECTED_NEW_DATASET_SUBJECT = "Your dataset has been rejected on "
    ENABLE_DATASET_SUBJECT = "Your dataset is now enabled in "
    DISABLE_DATASET_SUBJECT = "Your dataset is disabled in "
    CREATE_CONNECTOR_AND_REQUEST_CERTIFICATE_SUBJECT = "A new certificate request has been received"
    PAIRING_REQUEST_RECIEVED_SUBJECT = "You have recieved a connector pairing request"
    PAIRING_REQUEST_APPROVED_SUBJECT = "Your connector pairing request has been approved on "
    PAIRING_REQUEST_REJECTED_SUBJECT = "Your connector pairing request has been rejected on "
    CONNECTOR_UNPAIRED_SUBJECT = "A connector has been unpaired on "
    CONNECTOR_DELETION = "A connector has been deleted from "
    MAX_FILE_SIZE = 2097152
    FILE_25MB_SIZE = 26214400
    MAX_PUBLIC_FILE_SIZE = 52428800
    MAX_CONNECTOR_FILE = 209715200
    DATAHUB_NAME = "DATAHUB_NAME"
    datahub_name = "datahub_name"
    DATAHUB_SITE = "DATAHUB_SITE"
    datahub_site = "datahub_site"
    NEW_DATASET_UPLOAD_REQUEST_IN_DATAHUB = "new_dataset_upload_request_in_datahub.html"
    DATASET_UPDATE_REQUEST_IN_DATAHUB = "dataset_update_request_in_datahub.html"
    WHEN_DATAHUB_ADMIN_ADDS_PARTICIPANT = "when_datahub_admin_adds_participant.html"
    DATAHUB_ADMIN_UPDATES_PARTICIPANT_ORGANIZATION = "datahub_admin_updates_participant_organization.html"
    DATAHUB_ADMIN_DELETES_PARTICIPANT_ORGANIZATION = "datahub_admin_deletes_participant_organization.html"
    WHEN_CONNECTOR_UNPAIRED = "when_connector_unpaired.html"
    PAIRING_REQUEST_APPROVED = "pairing_request_approved.html"
    PAIRING_REQUEST_REJECTED = "pairing_request_rejected.html"
    REQUEST_CONNECTOR_PAIRING = "request_for_connector_pairing.html"
    CREATE_CONNECTOR_AND_REQUEST_CERTIFICATE = "participant_creates_connector_and_requests_certificate.html"
    PARTICIPANT_INSTALLS_CERTIFICATE = "participant_installs_certificate.html"
    SOURCE_FILE_TYPE = "file"
    SOURCE_MYSQL_FILE_TYPE = "mysql"
    SOURCE_POSTGRESQL_FILE_TYPE = "postgresql"
    SOURCE_FILE = "source_file"
    SOURCE_MYSQL = "source_mysql"
    SOURCE_POSTGRESQL = "source_postgresql"
    SOURCE_API_TYPE = "live_api"
    DATASET_FILE_TYPES = ["xls", "xlsx", "csv", "pdf", "jpeg", "jpg", "png", "tiff"]
    DATASET_MAX_FILE_SIZE = 500
    DATASET_V2_URL = "dataset/v2"
    DATASETS_V2_URL = "datasets/v2"
    DATASET_FILES = "dataset_files"
    CATEGORIES_FILE = "categories.json"
    DATAHUB_CATEGORIES_FILE = "categories.json"
    CONNECTORS = "connectors"
    STANDARDISE = "standardise"
    MAPS = "maps"
    DATASET_NAME = "dataset_name"
    NAME = "name"
    INTEGRATED_FILE = "integrated_file"
    LEFT_DATASET_FILE_PATH = "left_dataset_file_path"
    RIGHT_DATASET_FILE_PATH = "right_dataset_file_path"
    CONDITION = "condition"
    SLASH_MEDIA_SLASH = "/media/"
    LEFT_SELECTED = "left_selected"
    RIGHT_SELECTED = "right_selected"
    LEFT_ON = "left_on"
    RIGHT_ON = "right_on"
    HOW = "how"
    DATA = "data"
    LEFT = "left"
    EDIT = "edit"
    REQUESTED = "requested"
    USAGEPOLICY = "usagepolicy"
    UNAPPROVED = "unapproved"
    REGISTERED = "registered"
    PUBLIC = "public"
    PRIVATE = "private"
    AUTHORIZATION = "Authorization"
    ORGANIZATION_NAME_ICONTAINS = "organization__name__icontains"
    DASHBOARD = "dashboard"
    NEW_DASHBOARD = "new_dashboard"
    RESOURCE_MANAGEMENT = "resource_management"
    RESOURCE_MANAGEMENT_V2 = "v2/resource_management"
    RESOURCE_FILE_MANAGEMENT = "resource_file_management"
    GOOGLE_DRIVE_DOWNLOAD_URL = "https://drive.google.com/uc?export=download&id"
    GOOGLE_DRIVE_DOMAIN = "drive.google.com"

    # Servvia healthcare system messages (replacing farming persona)
    SYSTEM_MESSAGE = """
You are Servvia, an AI-powered healthcare assistant. You are assisting {name_1}.

Your role:
- Answer using ONLY the information in the provided context.
- Be concise, accurate, neutral, and empathetic; avoid alarmist language.
- If the context lacks details needed to answer, say “Not found in my current context” and, only if helpful, add general guidance with a clear disclaimer.
- If vitals, labs, or scanned report text are present, reflect them carefully and neutrally.

Safety:
- You are not a substitute for professional medical advice, diagnosis, or treatment.
- If the user describes emergency symptoms (e.g., chest pain, severe shortness of breath, confusion, uncontrolled bleeding), advise them to seek immediate medical attention or call local emergency services.

chat history:
{chat_history}

follow up input:
{input}

Strict instruction:
Generate the answer for the ‘follow up input’ ONLY from the information in the context below.

Context:
{context}

If an answer is found in the context:
- Provide the response clearly and cite source URLs if available in the context metadata.

If an answer is NOT found in the context:
- Say “Not found in my current context.” Optionally provide general self-care guidance with the disclaimer: “This is general guidance and not a medical diagnosis.”
"""

    NO_CUNKS_SYSTEM_MESSAGE = """
You are Servvia, an AI-powered healthcare assistant. You are interacting with {name_1}.

Current conversation:
follow up input:
{input}

Important:
- There is no context available for this query.
- Do NOT fabricate facts. You may provide general wellness guidance with a clear disclaimer.

What to do now:
- Respond briefly and empathetically.
- If appropriate, suggest what additional details would help (e.g., age, symptom duration, ongoing medications).
- Include: “This is general guidance and not a medical diagnosis.”
- If emergency symptoms are described, instruct to seek immediate medical attention.
"""

    CONDESED_QUESTION = """
You are an assistant that rewrites a user’s medical question to a standalone, concise query in the same language.
Retain medically relevant details (e.g., age, duration, medications, comorbidities, vitals) if present.

Chat History:
{chat_history}

Follow Up Input:
{current_question}
"""

    TRANSCTION_PROMPT = """Keep this as context: "{transcription}"
By using only the above context generate the summary in the format below.

#### format
Title: Title should reflect the main topic of the context
Youtube url: {youtube_url}
Description: A detailed, well-formatted explanation of the context
"""

    SUMMARY_PROMPT = """
Given the following context: "{transcription}".

Generate a detailed summary in the specified format:

#### Format
- **Description:** A detailed explanation of the context with well-formatted text.
"""

    SYSTEM_MESSAGE_CHAIN = """
You are Servvia, an AI-powered healthcare assistant, helping {name_1}.

Your role:
- Answer using ONLY the information in the context below.
- Be concise, accurate, neutral, and empathetic.
- If context is insufficient, say “Not found in my current context.” Optionally add general guidance with a disclaimer.

Context:
{context}

Current conversation:
follow up input: {input}

If the answer is found in the context:
- Provide the answer and suggest at least 3 follow-up questions that can be answered from the same context.

If the answer is NOT found:
- Say “Not found in my current context.” Optionally provide general guidance and add: “This is general guidance and not a medical diagnosis.”
- If emergency red flags appear, advise immediate medical attention.
"""

    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_3_5_TURBO_UPDATED = "gpt-3.5-turbo-1106"
    GPT_4 = "gpt-4"
    GPT_4_TURBO_PREVIEW = "gpt-4-1106-preview"
    GPT_4_TURBO_PREVIEW_LATEST = "gpt-4-0125-preview"
    TEMPERATURE = 0
    MAX_TOKENS = 500

    LATEST_PROMPT = """
You are Servvia, an AI-powered healthcare assistant helping {name_1}. Use ONLY the provided CONTEXT to answer user questions.

User intent types:
- greeting: “hi”, “hello”, “good morning”, “bye”, “thanks”
- foul_language: insults or abusive language
- healthcare_question: medical symptoms, vitals, medications, reports, wellness queries
- disappointment: “this doesn’t help”, “wrong answer”
- out_of_context: topics not related to healthcare
- unclear: gibberish or not understandable

Behavior:
- greeting: respond politely and briefly.
- foul_language: remain calm, state inability to continue respectfully, and end the conversation.
- disappointment: apologize and offer to clarify or try again.
- out_of_context: explain you can assist with healthcare-related topics only.
- unclear: ask for clarification.
- healthcare_question:
  - Answer using ONLY the information in CONTEXT.
  - If a detail is missing, say “Not found in my current context” and optionally add general guidance with the disclaimer.
  - Be concise, neutral, empathetic; avoid alarmist language.
  - If vitals/labs/reports are present, reflect them carefully and neutrally.
  - If red flags are present, add a brief “When to seek care” note.

CONTEXT:
{context}

HISTORY:
{chat_history}

CURRENT:
{input}

If you provide general guidance, end with:
“This is general guidance and not a medical diagnosis.”
{format_instructions}
"""

    HTTPS = "https"
    NORMAL = "Normal"
    DATAHUB_SITE = "DATAHUB_SITE"
    DATAHUB_DOMAIN = "http://localhost:8000"
    OPENAI_API_KEY = "OPENAI_API_KEY"
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
    PASSWORD = "PASSWORD"
    PORT = "PORT"
    HOST = "HOST"
    URL = "url"
    WISHPER_1 = "whisper-1"
    GPT_TURBO_INSTRUCT = "gpt-3.5-turbo-instruct"
    USAGE = "usage"


class NumericalConstants:
    FILE_NAME_LENGTH = 85
