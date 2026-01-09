import os
import base64
import json
import openai
from django.conf import settings

# Try to import PDF and OCR libraries
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("Warning: pdfplumber not installed.  PDF support disabled.")

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("Warning: pytesseract/PIL not installed. OCR support disabled.")


class EnhancedMedicalAI:
    """Enhanced AI service for medical image and lab report analysis"""
    
    def __init__(self):
        self. client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def analyze_skin_condition(self, image_path, user_profile=None):
        """Enhanced skin condition analysis with user profile awareness"""
        
        try:
            with open(image_path, "rb") as img:
                image_base64 = base64.b64encode(img.read()).decode('utf-8')
            
            # Build personalized prompt
            profile_context = ""
            if user_profile:
                allergies = ', '.join(user_profile.allergies) if user_profile.allergies else 'None'
                conditions = ', '.join(user_profile.medical_conditions) if user_profile. medical_conditions else 'None'
                medications = ', '.join(user_profile.current_medications) if user_profile. current_medications else 'None'
                profile_context = f"""
USER'S HEALTH PROFILE:
- Known Allergies: {allergies}
- Existing Medical Conditions: {conditions}
- Current Medications: {medications}
"""
            
            vision_prompt = f"""Analyze this skin condition image and provide a detailed JSON response.  

{profile_context}

Provide your analysis as valid JSON with these exact keys:
{{
    "condition_name": "Most likely skin condition",
    "confidence_level": 85,
    "description": "Detailed description of what you observe in the image",
    "severity": "low/medium/high",
    "key_characteristics": ["visible characteristic 1", "visible characteristic 2"],
    "safe_home_remedies": ["remedy 1 (verified safe for user)", "remedy 2"],
    "remedies_to_avoid": ["remedy to avoid (reason: allergy/condition)", "another one"],
    "when_to_see_doctor": ["warning sign 1", "warning sign 2"],
    "needs_immediate_attention": false,
    "general_care_tips": ["tip 1", "tip 2"]
}}

CRITICAL SAFETY RULES:
1. If user has allergies to any ingredient, DO NOT suggest remedies containing it
2. Consider existing medical conditions when suggesting remedies
3. If user takes medications, warn about potential interactions
4. Always prioritize user safety over treatment effectiveness
5.  Recommend doctor consultation for any serious or uncertain conditions

Return ONLY the JSON object, no additional text before or after."""

            response = self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                }],
                max_tokens=1000,
                temperature=0.2
            )
            
            content = response.choices[0].message.content. strip()
            
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Response content: {content}")
            return {
                'condition_name': 'Analysis Error - Invalid Response Format',
                'confidence_level': 0,
                'description': f'Could not parse AI response: {str(e)}',
                'severity': 'unknown',
                'safe_home_remedies': [],
                'needs_immediate_attention': True
            }
        except Exception as e:
            print(f"Error in skin analysis: {e}")
            return {
                'condition_name': 'Analysis Error',
                'confidence_level': 0,
                'description': str(e),
                'severity': 'unknown',
                'safe_home_remedies': [],
                'needs_immediate_attention': True
            }
    
    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF lab report"""
        if not PDF_AVAILABLE:
            return "PDF extraction not available.  Please install pdfplumber."
        
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"Error extracting PDF: {e}")
            return f"Error extracting PDF: {str(e)}"
        return text
    
    def extract_text_from_image(self, image_path):
        """Extract text from image using OCR"""
        if not OCR_AVAILABLE:
            return "OCR not available. Please install pytesseract and PIL."
        
        try:
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            return text
        except Exception as e:
            print(f"Error with OCR: {e}")
            return f"Error with OCR: {str(e)}"
    
    def analyze_lab_report(self, file_path, file_extension, user_profile=None):
        """Analyze lab report with user profile context"""
        
        # Extract text based on file type
        if file_extension. lower() == '.pdf':
            extracted_text = self.extract_text_from_pdf(file_path)
        elif file_extension. lower() in ['.jpg', '.jpeg', '. png']:
            extracted_text = self. extract_text_from_image(file_path)
        else:
            return {'error': 'Unsupported file format.  Please use PDF or image files.'}
        
        if not extracted_text. strip() or extracted_text.startswith('Error'):
            return {'error': extracted_text or 'Could not extract text from report'}
        
        # Build user context
        profile_context = ""
        if user_profile:
            allergies = ', '.join(user_profile. allergies) if user_profile. allergies else 'None'
            conditions = ', '.join(user_profile.medical_conditions) if user_profile.medical_conditions else 'None'
            medications = ', '.join(user_profile. current_medications) if user_profile.current_medications else 'None'
            age_group = user_profile.age_group or 'Not specified'
            
            profile_context = f"""
USER'S HEALTH PROFILE:
- Age Group: {age_group}
- Current Medical Conditions: {conditions}
- Current Medications: {medications}
- Known Allergies: {allergies}

IMPORTANT: Tailor your analysis and recommendations specifically for this user's profile.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert medical lab report analyzer. 
Analyze lab reports and provide clear, actionable insights in JSON format.
Always prioritize patient safety and recommend medical consultation when needed.
Be empathetic and explain medical terms in simple language."""
                    },
                    {
                        "role": "user",
                        "content": f"""Analyze this lab report and provide detailed insights as valid JSON. 

{profile_context}

LAB REPORT TEXT:
{extracted_text[:4000]}

Provide analysis as JSON with these exact keys:
{{
    "report_type": "Type of lab test (e.g., CBC, Metabolic Panel)",
    "test_date": "Date if found in report, or 'Not specified'",
    "summary": "Clear 2-3 sentence summary of overall health status based on results",
    "key_values": [
        {{"test": "Test Name", "value": "Result Value", "normal_range": "Normal Range", "status": "normal/high/low", "unit": "unit"}}
    ],
    "abnormal_findings": [
        {{"test": "Test Name", "value": "Result", "significance": "What this means in simple terms", "severity": "low/medium/high"}}
    ],
    "personalized_recommendations": [
        "Specific recommendation based on user's profile",
        "Another personalized suggestion"
    ],
    "lifestyle_suggestions": [
        "Diet suggestion based on results",
        "Exercise or lifestyle change"
    ],
    "needs_doctor_consultation": false,
    "urgency_level": "routine/moderate/urgent",
    "explanation": "Simple explanation of what these results mean for the patient"
}}

Return ONLY valid JSON, no additional text."""
                    }
                ],
                temperature=0.2,
                max_tokens=1500
            )
            
            content = response.choices[0].message. content.strip()
            
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            result['extracted_text'] = extracted_text
            return result
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Response content: {content}")
            return {
                'error': f'Could not parse AI response: {str(e)}',
                'extracted_text': extracted_text
            }
        except Exception as e:
            print(f"Error analyzing lab report: {e}")
            return {
                'error': str(e),
                'extracted_text': extracted_text
            }