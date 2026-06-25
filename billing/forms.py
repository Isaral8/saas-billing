from django import forms
from .models import TicketReply


class TicketReplyForm(forms.ModelForm):
    """Form for adding replies to support tickets"""
    
    class Meta:
        model = TicketReply
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'form-control ticket-reply-input',
                'placeholder': 'Type your message here... (minimum 5 characters)',
                'rows': 3,
                'required': True,
            })
        }
    
    def clean_message(self):
        """Validate that message is not empty and has minimum length"""
        message = self.cleaned_data.get('message', '').strip()
        
        if not message:
            raise forms.ValidationError("Message cannot be empty.")
        
        if len(message) < 5:
            raise forms.ValidationError("Message must be at least 5 characters long.")
        
        if len(message) > 5000:
            raise forms.ValidationError("Message cannot exceed 5000 characters.")
        
        return message