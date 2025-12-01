from django.db import models

# Create your models here.

class ChatSession(models.Model):
    """
    Represents a unique conversation thread (like a single chat in Gemini/ChatGPT).
    This allows a user to have multiple separate conversations.
    We are not associating this with a Django User yet, just a unique session ID.
    """
    session_id = models.CharField(max_length=100, unique=True, db_index=True, help_text="A unique ID for the conversation thread.")
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Session: {self.session_id}"

class Message(models.Model):
    """
    Represents a single message within a conversation thread.
    """
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', help_text="The conversation thread this message belongs to.")
    text_content = models.TextField(help_text="The content of the message.")
    is_user = models.BooleanField(default=False, help_text="True if sent by the user, False if sent by Nicole.")
    message_type = models.CharField(max_length=10, default='text', help_text="e.g., 'text', 'image', 'chart'.")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Optional field for image URL/base64 if needed, but we'll stick to text for simplicity now.
    # image_data = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        sender = "User" if self.is_user else "Nicole"
        return f"{sender} in {self.session.session_id}: {self.text_content[:50]}..."