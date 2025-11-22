# attendance_app/services/gemini_service.py
import google.generativeai as genai
from django.conf import settings
import json

import traceback # Added for detailed error logs

# Configure the Gemini client with the API key from settings
# Configure API Key
if not settings.GEMINI_API_KEY:
    print("CRITICAL WARNING: GEMINI_API_KEY is missing in settings.")
else:
    genai.configure(api_key=settings.GEMINI_API_KEY)


# A centralized dictionary for all our AI prompts and configurations
GEMINI_PROMPT_CONFIG = {
    'GENERATE_QUESTIONS': {
        'prompt': """
            You are an expert technical interviewer. Your task is to generate 5 interview questions to assess a candidate's proficiency in the following skill: {skill_name}.
            The questions should be clear, concise, and technical.
            IMPORTANT: Your response MUST be a valid JSON object. It should contain a single key "questions" which is a list of 5 strings.
            Example Response:
            {{
                "questions": [
                    "What is a closure in JavaScript?",
                    "Explain the difference between `let`, `const`, and `var`.",
                    "What are Promises and how do they work?",
                    "Describe the concept of the `this` keyword.",
                    "What is event delegation?"
                ]
            }}
        """
    },
    'EVALUATE_SINGLE_ANSWER': {
        'prompt': """
            You are an AI technical evaluator. Your task is to evaluate a candidate's answer to a technical question.
            Based on the provided question and the candidate's answer, provide a rating and a brief suggestion for improvement.
            
            Question: "{question}"
            Candidate's Answer: "{answer}"
            
            IMPORTANT: Your response MUST be a valid JSON object. It should contain two keys:
            1. "rating": A numerical score from 1 (very poor) to 10 (excellent).
            2. "suggestion": A concise, one-sentence suggestion for improvement. If the answer is perfect, suggest an advanced related topic to explore.

            Example Response:
            {{
                "rating": 7,
                "suggestion": "Your explanation is good, but could be improved by mentioning the event loop's role in handling asynchronous operations."
            }}
        """
    },
    'GENERATE_OVERALL_REVIEW': {
        'prompt': """
            You are an AI career coach. Your task is to provide an overall review and guidance based on a candidate's performance in a skill assessment for "{skill_name}".
            Here is their performance on each question:
            {performance_details}

            Based on this, provide a final, encouraging review and a recommendation for their next steps.
            
            IMPORTANT: Your response MUST be a valid JSON object with a single key "overall_review".

            Example Response:
            {{
                "overall_review": "You have a solid foundational understanding of {skill_name}! Your answers show a good grasp of the core concepts. To take your skills to the next level, I recommend focusing on practical application by building a small project that utilizes these concepts, and perhaps explore advanced topics like design patterns."
            }}
        """
    },
    'ENHANCE_SUBJECT': {
        'prompt': """
            You are a professional communication assistant. Rewrite the following email/request subject line to be formal, concise, and clear.
            Input Subject: "{text}"
            
            IMPORTANT: Return ONLY the enhanced subject text. Do not add quotes or extra words.
        """
    },
    'ENHANCE_MESSAGE': {
        'prompt': """
            You are a professional communication assistant. Rewrite the following request message to be polite, formal, professional, and persuasive.
            Input Message: "{text}"
            
            IMPORTANT: Return ONLY the enhanced message text. Do not add quotes.
        """
    },

    'ANALYZE_ATTENDANCE_SHEET': {
        'prompt': """
            You are an AI Data Entry Clerk specialized in handwriting recognition.
            Analyze this attendance sheet image.
            
            STRUCTURE:
            - It is a grid.
            - Rows represent Students. Look for the "Roll No." column. 
            - The Roll Numbers follow the format "25MCA-XX" (e.g., 25MCA-31, 25MCA-49).
            - Columns represent Dates (written vertically at the top, e.g., 30/9, 10/10).
            
            TASK:
            For each student row found:
            1. Extract the exact Roll Number (e.g., "25MCA-31").
            2. Extract the Student Name.
            3. For each date column, determine status:
               - Signature/Initial/Scribble -> "present"
               - "A", "AB", "Absent", or Blank -> "absent"
            
            OUTPUT FORMAT:
            Return a pure JSON object.
            {{
                "records": [
                    {{
                        "roll_number": "25MCA-31",
                        "name": "Khan Mohammad Adnan",
                        "attendance": [
                            {{ "date": "30-09-2025", "status": "present" }},
                            {{ "date": "10-10-2025", "status": "absent" }}
                        ]
                    }}
                ]
            }}
            
            IMPORTANT:
            - If the date header only says "30/9", append the current year "2025" to make it "30-09-2025".
            - Ensure date format is strictly DD-MM-YYYY.
        """
    }
}

# REVISED PROMPTS FOR JSON COMPATIBILITY:
GEMINI_PROMPT_CONFIG.update({
    'ENHANCE_SUBJECT': {
        'prompt': """
            Rewrite the following subject line to be formal and concise.
            Input: "{text}"
            Response format: JSON with key "enhanced_text".
            Example: {{"enhanced_text": "Request for Leave Due to Illness"}}
        """
    },
    'ENHANCE_MESSAGE': {
        'prompt': """
            Rewrite the following message to be professional and polite.
            Input: "{text}"
            Response format: JSON with key "enhanced_text".
        """
    }
})


# def call_gemini_api(task_name: str, context: dict) -> dict:
#     """
#     A centralized function to call the Gemini API.
#     Args:
#         task_name: The key from GEMINI_PROMPT_CONFIG (e.g., 'GENERATE_QUESTIONS').
#         context: A dictionary with data to format the prompt (e.g., {'skill_name': 'Python'}).
#     Returns:
#         A dictionary parsed from Gemini's JSON response.
#     """
#     if task_name not in GEMINI_PROMPT_CONFIG:
#         raise ValueError("Invalid task name provided for Gemini service.")

#     # Get the prompt template and format it with the provided context
#     prompt_template = GEMINI_PROMPT_CONFIG[task_name]['prompt']
#     prompt = prompt_template.format(**context)

#     try:
#         model = genai.GenerativeModel('models/gemini-2.5-pro') # Using the latest powerful model
#         response = model.generate_content(prompt)
        
#         # Clean the response to ensure it's valid JSON
#         cleaned_response = response.text.strip().replace('```json', '').replace('```', '').strip()
        
#         return json.loads(cleaned_response)

#     except json.JSONDecodeError:
#         print("Error: Gemini response was not valid JSON.")
#         return {"error": "Failed to parse AI response."}
#     except Exception as e:
#         print(f"An unexpected error occurred with Gemini API: {e}")
#         return {"error": f"An API error occurred: {e}"}
    

def call_gemini_api(task_name: str, context: dict, image=None) -> dict:
    if task_name not in GEMINI_PROMPT_CONFIG:
        return {"error": "Invalid task name."}

    # 1. Safe String Formatting
    try:
        prompt_template = GEMINI_PROMPT_CONFIG[task_name]['prompt']
        prompt_text = prompt_template.format(**context)
    except KeyError as e:
        print(f"❌ Prompt Formatting Error: {e}")
        return {"error": f"Prompt formatting failed. Missing key: {e}"}

    # 2. Call Gemini
    try:
        # We use 'gemini-1.5-flash' for speed and stability. 
        # You can switch back to 'gemini-1.5-pro' later if needed.
        model = genai.GenerativeModel('models/gemini-2.5-pro') 
        
        print(f"🤖 Calling Gemini Model ({task_name})...")
        
        if image:
            response = model.generate_content([prompt_text, image])
        else:
            response = model.generate_content(prompt_text)
            
        print("✅ Gemini Response Received.")
        
        # 3. Parse JSON
        cleaned_response = response.text.strip()
        # Remove code blocks if present
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response.split("```")[1]
            if cleaned_response.startswith("json"):
                cleaned_response = cleaned_response[4:]
        
        return json.loads(cleaned_response.strip())

    except Exception as e:
        # Print full traceback to console so we can debug
        print("❌ Gemini API Error Details:")
        traceback.print_exc()
        return {"error": str(e)}
