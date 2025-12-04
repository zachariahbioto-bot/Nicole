from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class ChatTag(models.Model):
    """Tags/Categories for organizing chats"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_tags')
    name = models.CharField(max_length=50, help_text="Tag name (e.g., 'Refraction', 'Business')")
    color = models.CharField(max_length=7, default='#522888', help_text="Hex color for the tag")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'name')
        ordering = ['name']
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"

class ChatSession(models.Model):
    """
    Represents a unique conversation thread (like a single chat in Gemini/ChatGPT).
    Now linked to a Django User and tags.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    session_id = models.CharField(max_length=100, unique=True, db_index=True, help_text="A unique ID for the conversation thread.")
    title = models.CharField(max_length=255, default="New Chat", help_text="User-given title for the chat session.")
    tags = models.ManyToManyField(ChatTag, blank=True, related_name='sessions', help_text="Tags for organizing chats")
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"Session: {self.title} ({self.session_id})"

class Message(models.Model):
    """
    Represents a single message within a conversation thread.
    Now includes optional sources/citations.
    """
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', help_text="The conversation thread this message belongs to.")
    text_content = models.TextField(help_text="The content of the message.")
    is_user = models.BooleanField(default=False, help_text="True if sent by the user, False if sent by Nicole.")
    message_type = models.CharField(max_length=10, default='text', help_text="e.g., 'text', 'image', 'chart'.")
    sources = models.JSONField(default=list, blank=True, help_text="List of citation sources from grounding.")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        sender = "User" if self.is_user else "Nicole"
        return f"{sender} in {self.session.title}: {self.text_content[:50]}..."

class APIUsageLog(models.Model):
    """Track API usage for rate limiting and analytics"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_usage')
    endpoint = models.CharField(max_length=100, help_text="API endpoint called (e.g., 'chat', 'search')")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    response_time = models.FloatField(null=True, blank=True, help_text="Response time in seconds")
    status_code = models.IntegerField(default=200, help_text="HTTP status code")
    tokens_used = models.IntegerField(default=0, help_text="Approximate tokens used from API")
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.endpoint} - {self.timestamp}"

class RateLimitConfig(models.Model):
    """Configure rate limits per user"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='rate_limit_config')
    # Messages per hour
    messages_per_hour = models.IntegerField(default=30, help_text="Max messages per hour")
    # Messages per day
    messages_per_day = models.IntegerField(default=200, help_text="Max messages per day")
    # API calls per minute
    api_calls_per_minute = models.IntegerField(default=5, help_text="Max API calls per minute")
    # Account created date (for Pro tier calculation)
    is_premium = models.BooleanField(default=False, help_text="Is this a premium user?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        tier = "Premium" if self.is_premium else "Free"
        return f"{self.user.username} - {tier} Tier"
    
    @classmethod
    def get_or_create_default(cls, user):
        """Get or create default rate limit config for user"""
        config, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'messages_per_hour': 30,
                'messages_per_day': 200,
                'api_calls_per_minute': 5,
            }
        )
        return config

    def get_usage_stats(self):
        """Get current usage stats"""
        now = timezone.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        minute_ago = now - timedelta(minutes=1)
        
        messages_this_hour = APIUsageLog.objects.filter(
            user=self.user,
            endpoint='chat',
            timestamp__gte=hour_ago
        ).count()
        
        messages_this_day = APIUsageLog.objects.filter(
            user=self.user,
            endpoint='chat',
            timestamp__gte=day_ago
        ).count()
        
        calls_this_minute = APIUsageLog.objects.filter(
            user=self.user,
            timestamp__gte=minute_ago
        ).count()
        
        return {
            'messages_this_hour': messages_this_hour,
            'messages_per_hour_limit': self.messages_per_hour,
            'messages_this_day': messages_this_day,
            'messages_per_day_limit': self.messages_per_day,
            'calls_this_minute': calls_this_minute,
            'calls_per_minute_limit': self.api_calls_per_minute,
            'is_rate_limited': (
                messages_this_hour >= self.messages_per_hour or
                messages_this_day >= self.messages_per_day or
                calls_this_minute >= self.api_calls_per_minute
            )
        }
    