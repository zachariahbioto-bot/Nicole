from django.utils import timezone
from datetime import timedelta
from .models import APIUsageLog, RateLimitConfig
import time

class RateLimiter:
    """Handle rate limiting logic"""
    
    @staticmethod
    def check_rate_limit(user):
        """
        Check if user has exceeded rate limits
        Returns: (is_limited: bool, message: str, stats: dict)
        """
        config = RateLimitConfig.get_or_create_default(user)
        stats = config.get_usage_stats()
        
        if stats['is_rate_limited']:
            if stats['messages_this_hour'] >= config.messages_per_hour:
                reset_time = timezone.now() + timedelta(hours=1)
                return True, f"⏳ Hourly limit reached ({config.messages_per_hour} messages). Reset at {reset_time.strftime('%H:%M')}", stats
            
            if stats['messages_this_day'] >= config.messages_per_day:
                reset_time = timezone.now() + timedelta(days=1)
                return True, f"⏳ Daily limit reached ({config.messages_per_day} messages). Reset at {reset_time.strftime('%H:%M')}", stats
            
            if stats['calls_this_minute'] >= config.api_calls_per_minute:
                return True, f"⚡ Too many requests. Please wait before sending another message.", stats
        
        return False, None, stats
    
    @staticmethod
    def log_api_usage(user, endpoint, response_time=None, status_code=200, tokens_used=0):
        """Log API usage for tracking"""
        APIUsageLog.objects.create(
            user=user,
            endpoint=endpoint,
            response_time=response_time,
            status_code=status_code,
            tokens_used=tokens_used
        )
    
    @staticmethod
    def get_user_stats(user):
        """Get detailed usage stats for user"""
        config = RateLimitConfig.get_or_create_default(user)
        stats = config.get_usage_stats()
        
        # Calculate percentages
        hour_percentage = (stats['messages_this_hour'] / stats['messages_per_hour_limit']) * 100
        day_percentage = (stats['messages_this_day'] / stats['messages_per_day_limit']) * 100
        
        return {
            'tier': 'Premium' if config.is_premium else 'Free',
            'messages_hour': {
                'current': stats['messages_this_hour'],
                'limit': stats['messages_per_hour_limit'],
                'percentage': min(hour_percentage, 100)
            },
            'messages_day': {
                'current': stats['messages_this_day'],
                'limit': stats['messages_per_day_limit'],
                'percentage': min(day_percentage, 100)
            },
            'is_rate_limited': stats['is_rate_limited']
        }