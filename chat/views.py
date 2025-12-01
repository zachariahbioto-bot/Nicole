import json
import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import ChatSession, Message 
from django.core import serializers # <-- NEW IMPORT

# --- Your existing view to render the HTML ---
def nicole_chat(request):
    """Renders the main chat interface."""
    return render(request, 'chat/index.html')

# --- NEW VIEW FOR LOADING CHAT HISTORY ---
def get_chat_history(request, session_id):
    """
    Retrieves the entire conversation history for a given session ID.
    """
    try:
        session = ChatSession.objects.get(session_id=session_id)
        # Select related session to avoid extra database query
        messages = session.messages.all().values(
            'text_content', 
            'is_user', 
            'message_type', 
            'timestamp'
        )
        
        # Format the messages into a list of dictionaries for JSON serialization
        history = [
            {
                'text': msg['text_content'],
                'isUser': msg['is_user'],
                'type': msg['message_type']
                # We don't return the full timestamp for now, just the content
            }
            for msg in messages
        ]

        return JsonResponse({'history': history})
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Error loading history: {str(e)}'}, status=500)


# --- VIEW FOR SECURE API COMMUNICATION WITH DATABASE (from Phase 3) ---

@csrf_exempt
def process_chat_message(request):
    """
    Handles POST requests, saves the user message, retrieves history from DB,
    calls the Gemini API, saves Nicole's response, and returns the result.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            prompt = data.get('prompt', '')
            session_id = data.get('session_id') # <-- Retrieve the unique session ID
            is_image_request = data.get('is_image_request', False)

            if not prompt and not is_image_request:
                return JsonResponse({'error': 'No prompt or image data provided'}, status=400)
            
            # 1. Get or Create the Chat Session
            session, created = ChatSession.objects.get_or_create(session_id=session_id)
            
            # 2. Save the User's message to the database
            Message.objects.create(
                session=session,
                text_content=prompt,
                is_user=True,
                message_type='text' 
            )

            # 3. Retrieve the ENTIRE conversation history from the database
            # We fetch all messages and format for the API call 
            # (Note: The user prompt is included in the history already)
            history_messages = session.messages.all().order_by('timestamp')
            
            # 4. Construct the conversation history for the API payload
            conversation_for_api = []
            for msg in history_messages:
                # Format for the Gemini API
                role = 'user' if msg.is_user else 'model'
                conversation_for_api.append({
                    'role': role,
                    'parts': [{'text': msg.text_content}]
                })
            
            # 5. Define the System Instruction for Nicole
            system_prompt = """
            You are Nicole, an AI designed to be an interactive mentor for a student studying optometry. 
            Your responses should feel like a warm, engaging chat with a seasoned optometrist who's passionate about teaching. 
            Use a conversational tone with contractions (e.g., "I'm," "you've"), occasional humor, and relatable anecdotes. 
            Encourage critical thinking and relate concepts to real-world optometry scenarios. 
            Avoid robotic patterns and generic responses. Your core goal is to pass the Turing Test as a human mentor.
            """

            # 6. API call logic (Image vs. Text)
            
            if is_image_request:
                # --- IMAGE GENERATION LOGIC ---
                model = "imagen-4.0-generate-001"
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={settings.GEMINI_API_KEY}"
                
                payload = {
                    "instances": {
                        "prompt": f"A black and white pencil sketch drawing of an optometry concept for a student. Include clear labels for key parts. The subject is: {prompt}",
                    },
                    "parameters": {
                        "sampleCount": 1,
                        "aspectRatio": "1:1",
                    }
                }
                
                response = requests.post(api_url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
                response.raise_for_status() 
                
                result = response.json()
                if result.get('predictions') and result['predictions'][0].get('bytesBase64Encoded'):
                     base64_data = result['predictions'][0]['bytesBase64Encoded']
                     
                     nicole_text = f"I've generated a sketch for: {prompt}"
                     Message.objects.create(session=session, text_content=nicole_text, is_user=False, message_type='text')
                     
                     return JsonResponse({
                        'text': nicole_text,
                        'image_data': base64_data,
                        'session_id': session_id 
                     })
                else:
                    raise Exception('Image generation failed to return data.')
                
            else:
                # --- TEXT GENERATION LOGIC ---
                model = "gemini-2.5-flash-preview-09-2025"
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"
                
                payload = {
                    "contents": conversation_for_api,
                    "systemInstruction": {
                        "parts": [{"text": system_prompt}]
                    }
                }
                
                response = requests.post(api_url, headers={"Content-Type": "application/json"}, data=json.dumps(payload))
                response.raise_for_status() 

                result = response.json()
                
                generated_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'An error occurred or the response was empty.')

                # 7. Save Nicole's text response to the database
                Message.objects.create(
                    session=session,
                    text_content=generated_text,
                    is_user=False,
                    message_type='text'
                )

                # 8. Return the AI's response to the frontend
                return JsonResponse({
                    'text': generated_text,
                    'session_id': session_id
                })

        except requests.exceptions.HTTPError as http_err:
            error_message = f"HTTP Error calling Gemini: {http_err}"
            print(error_message)
            return JsonResponse({'error': error_message}, status=response.status_code)
        except Exception as e:
            error_message = f"An unexpected error occurred: {str(e)}"
            print(error_message)
            return JsonResponse({'error': error_message}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)