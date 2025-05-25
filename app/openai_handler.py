from typing import List, Dict
import json
import os

class OpenAIHandler:
    def __init__(self):
        self.client = None
        self.conversation_history = {}
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client with error handling"""
        try:
            from openai import OpenAI
            from app.config import config
            
            api_key = getattr(config, 'OPENAI_API_KEY', None) or os.getenv('OPENAI_API_KEY')
            
            if not api_key:
                print("Warning: No OpenAI API key found. AI features will be disabled.")
                return
            
            self.client = OpenAI(api_key=api_key)
            print("OpenAI client initialized successfully")
            
        except ImportError as e:
            print(f"OpenAI library not found: {e}")
            print("Install with: pip install openai")
        except Exception as e:
            print(f"Failed to initialize OpenAI client: {e}")
            print("AI features will be disabled")
    
    def generate_response(self, message: str, contact: str, context: str = None) -> str:
        """Generate AI response using OpenAI GPT"""
        if not self.client:
            return "AI is currently unavailable. Please check your OpenAI API configuration."
        
        try:
            # Initialize conversation history for contact if not exists
            if contact not in self.conversation_history:
                self.conversation_history[contact] = []
            
            # Add user message to history
            self.conversation_history[contact].append({
                "role": "user",
                "content": message
            })
            
            # Keep only last 10 messages to avoid token limits
            if len(self.conversation_history[contact]) > 10:
                self.conversation_history[contact] = self.conversation_history[contact][-10:]
            
            # System prompt
            system_prompt = """You are a helpful WhatsApp assistant. 
            Keep responses concise and friendly. 
            Respond naturally as if you're texting on WhatsApp.
            Use emojis when appropriate but don't overuse them."""
            
            if context:
                system_prompt += f"\nAdditional context: {context}"
            
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(self.conversation_history[contact])
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=150,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Add AI response to conversation history
            self.conversation_history[contact].append({
                "role": "assistant",
                "content": ai_response
            })
            
            return ai_response
            
        except Exception as e:
            print(f"Error generating AI response: {e}")
            return "Sorry, I'm having trouble responding right now. Please try again later."
    
    def generate_scheduled_message(self, template: str, contact: str, **kwargs) -> str:
        """Generate personalized scheduled message"""
        if not self.client:
            return template  # Fallback to original template
            
        try:
            prompt = f"""
            Create a personalized message based on this template: "{template}"
            Make it feel natural and personal for WhatsApp.
            Additional info: {json.dumps(kwargs)}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.8
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating scheduled message: {e}")
            return template  # Fallback to original template
    
    def analyze_sentiment(self, message: str) -> Dict:
        """Analyze message sentiment"""
        if not self.client:
            return {"sentiment": "neutral", "confidence": 0.5}
            
        try:
            prompt = f"""
            Analyze the sentiment of this message: "{message}"
            Respond with JSON format: {{"sentiment": "positive/negative/neutral", "confidence": 0.0-1.0}}
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content.strip())
            return result
            
        except Exception as e:
            print(f"Error analyzing sentiment: {e}")
            return {"sentiment": "neutral", "confidence": 0.5}
