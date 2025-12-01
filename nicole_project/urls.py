"""
URL configuration for nicole_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from chat.views import nicole_chat, process_chat_message, get_chat_history # Import the new function

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', nicole_chat, name='home'), 
    path('api/chat/', process_chat_message, name='api_chat'),
    path('api/history/<str:session_id>/', get_chat_history, name='get_chat_history'), # <-- NEW HISTORY ENDPOINT
]



