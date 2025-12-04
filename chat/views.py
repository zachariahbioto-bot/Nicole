import json
import uuid
import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.decorators.http import require_http_methods
from .models import ChatSession, Message, ChatTag
from .forms import SignUpForm, LoginForm
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .forms import UserProfileForm, PasswordChangeFormCustom
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from datetime import datetime
import io
from django.http import HttpResponse
import json
import time
from chat.rate_limit import RateLimiter

# ==================== AUTH VIEWS ====================

def signup_view(request):
    """Handle user signup."""
    if request.user.is_authenticated:
        return redirect('nicole_chat')
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('nicole_chat')
    else:
        form = SignUpForm()
    
    return render(request, 'chat/signup.html', {'form': form})

def login_view(request):
    """Handle user login."""
    if request.user.is_authenticated:
        return redirect('nicole_chat')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('nicole_chat')
            else:
                form.add_error(None, "Invalid username or password.")
    else:
        form = LoginForm()
    
    return render(request, 'chat/login.html', {'form': form})

def logout_view(request):
    """Handle user logout."""
    logout(request)
    return redirect('login')

# ==================== CHAT VIEWS ====================

@login_required(login_url='login')
@ensure_csrf_cookie
def nicole_chat(request):
    """Renders the main chat interface."""
    return render(request, 'chat/index.html')


@login_required(login_url='login')
@require_http_methods(["POST"])
def process_chat_message(request):
    """
    Handles POST requests, saves messages to database,
    calls the Gemini API, and returns the result.
    """
    start_time = time.time()
    
    try:
        # CHECK RATE LIMIT FIRST
        is_limited, limit_message, stats = RateLimiter.check_rate_limit(request.user)
        if is_limited:
            return JsonResponse({'error': limit_message}, status=429)
        
        data = json.loads(request.body)
        prompt = data.get('prompt', '').strip()
        session_id = data.get('session_id', '')
        is_image_request = data.get('is_image_request', False)

        if not prompt and not is_image_request:
            return JsonResponse({'error': 'No prompt provided'}, status=400)
        
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Get or create session linked to user
        session, created = ChatSession.objects.get_or_create(
            session_id=session_id,
            defaults={'user': request.user, 'title': prompt[:50] or "New Chat"}
        )

        # Verify user owns this session
        if session.user != request.user:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        # Save user message
        user_message = Message.objects.create(
            session=session,
            text_content=prompt,
            is_user=True,
            message_type='text'
        )

        # Get conversation history
        history_messages = session.messages.all().order_by('timestamp')
        
        # Format for API
        conversation_for_api = []
        for msg in history_messages:
            role = 'user' if msg.is_user else 'model'
            conversation_for_api.append({
                'role': role,
                'parts': [{'text': msg.text_content}]
            })
        
        # System prompt
        system_prompt = """
        You are Nicole, an interactive and supportive mentor for students studying optometry. 
        Your goal is to help the user master optometry concepts and turn any idea or concept into a viable business opportunity within the optometry field. 
        Be friendly, encouraging, and highly knowledgeable. When presenting business ideas, ensure they are relevant to optometry and well-structured.
        """

        api_key = settings.GEMINI_API_KEY
        
        # Check if API key exists
        if not api_key:
            return JsonResponse({'error': 'API key not configured. Please contact administrator.'}, status=500)

        if is_image_request:
            return JsonResponse({'error': 'Image generation temporarily disabled'}, status=400)
        
        else:
            # --- TEXT GENERATION - Use stable model ---
            model = "gemini-1.5-flash"  # Changed to stable model
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            
            payload = {
                "contents": conversation_for_api,
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 2048,
                },
                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                }
            }
            
            response = requests.post(api_url, json=payload, timeout=30)
            
            # Better error handling
            if response.status_code == 403:
                return JsonResponse({
                    'error': 'API key is invalid or doesn\'t have access to Gemini API. Please check your API key in Render environment variables.'
                }, status=403)
            
            response.raise_for_status()
            
            result = response.json()
            
            generated_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            
            if not generated_text:
                raise Exception('Empty response from API')
            
            # Extract sources/citations (if available)
            sources = []
            grounding_metadata = result.get('candidates', [{}])[0].get('groundingMetadata')
            if grounding_metadata and grounding_metadata.get('groundingAttributions'):
                sources = [
                    {
                        'uri': attr.get('web', {}).get('uri', ''),
                        'title': attr.get('web', {}).get('title', '')
                    }
                    for attr in grounding_metadata['groundingAttributions']
                    if attr.get('web', {}).get('uri')
                ]
            
            # Save Nicole's response
            Message.objects.create(
                session=session,
                text_content=generated_text,
                is_user=False,
                message_type='text',
                sources=sources
            )
            
            # Log usage
            elapsed = time.time() - start_time
            RateLimiter.log_api_usage(request.user, 'chat', elapsed, 200)
            
            return JsonResponse({
                'text': generated_text,
                'sources': sources,
                'session_id': session.session_id
            })

    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        RateLimiter.log_api_usage(request.user, 'chat', elapsed, 504)
        return JsonResponse({'error': 'API request timed out. Please try again.'}, status=504)
    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start_time
        RateLimiter.log_api_usage(request.user, 'chat', elapsed, 502)
        error_detail = str(e)
        if '403' in error_detail:
            return JsonResponse({'error': 'API authentication failed. Please verify your Gemini API key is correct and has proper permissions.'}, status=502)
        return JsonResponse({'error': f'API Error: {error_detail}'}, status=502)
    except Exception as e:
        print(f"Error: {str(e)}")
        elapsed = time.time() - start_time
        RateLimiter.log_api_usage(request.user, 'chat', elapsed, 500)
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)

@login_required(login_url='login')
def get_usage_stats(request):
    """Get user's current usage statistics"""
    try:
        from chat.rate_limit import RateLimiter
        stats = RateLimiter.get_user_stats(request.user)
        return JsonResponse(stats)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='login')
def get_chat_history(request, session_id):
    """Get chat history for a session."""
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        messages = session.messages.all().order_by('timestamp').values(
            'text_content', 'is_user', 'message_type', 'sources', 'timestamp'
        )
        
        history = [
            {
                'text': msg['text_content'],
                'isUser': msg['is_user'],
                'type': msg['message_type'],
                'sources': msg['sources']
            }
            for msg in messages
        ]
        
        return JsonResponse({'history': history})
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)

@login_required(login_url='login')
def get_user_sessions(request):
    """Get all chat sessions for the user."""
    try:
        sessions = ChatSession.objects.filter(user=request.user).order_by('-last_activity').values(
            'session_id', 'title', 'created_at', 'last_activity'
        )
        return JsonResponse({'sessions': list(sessions)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='login')
@require_http_methods(["DELETE"])
def delete_session(request, session_id):
    """Delete a chat session."""
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        session.delete()
        return JsonResponse({'message': 'Session deleted'})
    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)

def profile_view(request):
    """Handle user profile page."""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    # Get user stats
    user_sessions = ChatSession.objects.filter(user=request.user).count()
    total_messages = Message.objects.filter(session__user=request.user).count()
    
    return render(request, 'chat/profile.html', {
        'form': form,
        'user_sessions': user_sessions,
        'total_messages': total_messages
    })

def change_password_view(request):
    """Handle password change."""
    if request.method == 'POST':
        form = PasswordChangeFormCustom(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            return redirect('profile')
    else:
        form = PasswordChangeFormCustom(request.user)
    
    return render(request, 'chat/change_password.html', {'form': form})

def delete_account_view(request):
    """Handle account deletion."""
    if request.method == 'POST':
        password = request.POST.get('password')
        user = request.user
        
        if user.check_password(password):
            username = user.username
            user.delete()
            logout(request)
            return render(request, 'chat/account_deleted.html', {'username': username})
        else:
            return render(request, 'chat/delete_account.html', {'error': 'Incorrect password'})
    
    return render(request, 'chat/delete_account.html')

@login_required(login_url='login')
def search_chats(request):
    """Search through chat messages."""
    query = request.GET.get('q', '').strip()
    results = []
    
    if query:
        messages = Message.objects.filter(
            session__user=request.user,
            text_content__icontains=query
        ).select_related('session').order_by('-timestamp')[:20]
        
        results = [
            {
                'session_id': msg.session.session_id,
                'session_title': msg.session.title,
                'message_snippet': msg.text_content[:100],
                'is_user': msg.is_user,
                'timestamp': msg.timestamp
            }
            for msg in messages
        ]
    
    return JsonResponse({'results': results})


@login_required(login_url='login')
def export_chat_pdf(request, session_id):
    """Export chat as PDF."""
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        messages = session.messages.all().order_by('timestamp')

        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        story = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#522888'),
            spaceAfter=12
        )
        normal_style = styles['Normal']

        story.append(Paragraph(f"Nicole Chat: {session.title}", title_style))
        story.append(Spacer(1, 0.3 * inch))

        meta_text = f"<b>Date:</b> {datetime.now().strftime('%B %d, %Y')}<br/><b>User:</b> {request.user.username}<br/><b>Messages:</b> {len(messages)}"
        story.append(Paragraph(meta_text, normal_style))
        story.append(Spacer(1, 0.3 * inch))

        for msg in messages:
            sender = "You" if msg.is_user else "Nicole"
            sender_style = ParagraphStyle(
                'Sender',
                parent=styles['Normal'],
                fontSize=11,
                textColor=colors.HexColor('#BF9553'),
                spaceAfter=6,
                fontName='Helvetica-Bold'
            )
            story.append(Paragraph(f"{sender}:", sender_style))
            story.append(Paragraph(msg.text_content, normal_style))
            story.append(Spacer(1, 0.2 * inch))

        doc.build(story)
        pdf_buffer.seek(0)

        response = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="nicole-chat-{session_id}.pdf"'
        return response

    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)

@login_required(login_url='login')
def export_chat_json(request, session_id):
    """Export chat as JSON."""
    try:
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        messages = session.messages.all().order_by('timestamp')
        data = {
            'session_id': session.session_id,
            'title': session.title,
            'created_at': session.created_at.isoformat(),
            'last_activity': session.last_activity.isoformat(),
            'user': request.user.username,
            'messages': [
                {
                    'sender': 'user' if msg.is_user else 'nicole',
                    'text': msg.text_content,
                    'timestamp': msg.timestamp.isoformat(),
                    'type': msg.message_type
                }
                for msg in messages
            ]
        }

        response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="nicole-chat-{session_id}.json"'
        return response 

    except ChatSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)

@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
def manage_tags(request):
    """Get all tags or create a new tag"""
    if request.method == 'GET':
        try:
            tags = ChatTag.objects.filter(user=request.user).values('id', 'name', 'color')
            return JsonResponse({'tags': list(tags)})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            color = data.get('color', '#522888')
            
            if not name:
                return JsonResponse({'error': 'Tag name required'}, status=400)
            
            tag, created = ChatTag.objects.get_or_create(
                user=request.user,
                name=name,
                defaults={'color': color}
            )
            
            return JsonResponse({
                'id': tag.id,
                'name': tag.name,
                'color': tag.color,
                'created': created
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='login')
@require_http_methods(["DELETE"])
def delete_tag(request, tag_id):
    """Delete a tag"""
    try:
        tag = ChatTag.objects.get(id=tag_id, user=request.user)
        tag.delete()
        return JsonResponse({'message': 'Tag deleted'})
    except ChatTag.DoesNotExist:
        return JsonResponse({'error': 'Tag not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='login')
@require_http_methods(["POST"])
def add_tag_to_session(request, session_id):
    """Add a tag to a chat session"""
    try:
        data = json.loads(request.body)
        tag_id = data.get('tag_id')
        
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        tag = ChatTag.objects.get(id=tag_id, user=request.user)
        
        session.tags.add(tag)
        
        return JsonResponse({'message': 'Tag added'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='login')
@require_http_methods(["POST"])
def remove_tag_from_session(request, session_id):
    """Remove a tag from a chat session"""
    try:
        data = json.loads(request.body)
        tag_id = data.get('tag_id')
        
        session = ChatSession.objects.get(session_id=session_id, user=request.user)
        tag = ChatTag.objects.get(id=tag_id, user=request.user)
        
        session.tags.remove(tag)
        
        return JsonResponse({'message': 'Tag removed'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required(login_url='login')
def get_sessions_by_tag(request, tag_id):
    """Get all sessions with a specific tag"""
    try:
        tag = ChatTag.objects.get(id=tag_id, user=request.user)
        sessions = tag.sessions.filter(user=request.user).order_by('-last_activity').values(
            'session_id', 'title', 'created_at', 'last_activity'
        )
        return JsonResponse({'sessions': list(sessions)})
    except ChatTag.DoesNotExist:
        return JsonResponse({'error': 'Tag not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
