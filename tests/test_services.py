import pytest
from accounts.models import CustomUser, Notification
from accounts.services import NotificationService, NotificationFactory

@pytest.mark.django_db
class TestNotificationService:
    """Test Notification Service"""
    
    def setup_method(self):
        """Setup before each test"""
        self.user = CustomUser.objects.create_user(
            email='user@example.com',
            password='pass123'
        )
    
    def test_create_notification(self):
        """Test creating a notification"""
        notification = NotificationService.create_notification(
            user=self.user,
            title='Test Notification',
            message='This is a test notification',
            notification_type='system_info',
            async_task=False
        )
        assert notification.title == 'Test Notification'
        assert notification.user == self.user
        assert notification.is_read == False
        print(f"✅ Notification created: {notification.title}")
    
    def test_notification_factory_success(self):
        """Test NotificationFactory success message"""
        notification = NotificationFactory.system_success(
            user=self.user,
            title='Success!',
            message='Operation completed',
            async_task=False
        )
        assert notification.color == 'success'
        print(f"✅ Factory notification created: {notification.title}")
    
    def test_mark_notification_as_read(self):
        """Test marking notification as read"""
        notification = NotificationService.create_notification(
            user=self.user,
            title='Test',
            message='Test',
            async_task=False
        )
        notification.mark_as_read()
        assert notification.is_read == True
        print("✅ Notification marked as read")
    
    def test_get_unread_notifications(self):
        """Test getting unread notifications"""
        # Create 3 notifications
        for i in range(3):
            NotificationService.create_notification(
                user=self.user,
                title=f'Test {i}',
                message=f'Message {i}',
                async_task=False
            )
        
        unread = NotificationService.get_unread_notifications(self.user)
        assert len(unread) >= 3
        print(f"✅ Got {len(unread)} unread notifications")