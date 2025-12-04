from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from chat.views import (
    nicole_chat, 
    process_chat_message, 
    get_chat_history,
    get_user_sessions,
    delete_session,
    signup_view,
    login_view,
    logout_view,
    profile_view,
    change_password_view,
    delete_account_view,
    search_chats,
    get_usage_stats,
    export_chat_pdf,
    export_chat_json,
    manage_tags,  # ADD THIS
    delete_tag,  # ADD THIS
    add_tag_to_session,  # ADD THIS
    remove_tag_from_session,  # ADD THIS
    get_sessions_by_tag,  # ADD THIS
)


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Auth
    path('signup/', signup_view, name='signup'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'),
    path('change-password/', change_password_view, name='change_password'),
    path('delete-account/', delete_account_view, name='delete_account'),
    
    # Chat
    path('', nicole_chat, name='nicole_chat'),
    path('usage/', lambda r: render(r, 'chat/usage.html'), name='usage'),
    
    # API
    path('api/chat/', process_chat_message, name='api_chat'),
    path('api/history/<str:session_id>/', get_chat_history, name='get_chat_history'),
    path('api/sessions/', get_user_sessions, name='get_user_sessions'),
    path('api/session/<str:session_id>/delete/', delete_session, name='delete_session'),
    path('api/search/', search_chats, name='search_chats'),
    path('api/usage/', get_usage_stats, name='usage_stats'),
    path('api/chat/<str:session_id>/export/pdf/', export_chat_pdf, name='export_pdf'),
    path('api/chat/<str:session_id>/export/json/', export_chat_json, name='export_json'),
    path('api/tags/', manage_tags, name='manage_tags'),
    path('api/tags/<int:tag_id>/delete/', delete_tag, name='delete_tag'),
    path('api/session/<str:session_id>/tag/', add_tag_to_session, name='add_tag'),
    path('api/session/<str:session_id>/untag/', remove_tag_from_session, name='remove_tag'),
    path('api/tags/<int:tag_id>/sessions/', get_sessions_by_tag, name='get_sessions_by_tag'),
]


