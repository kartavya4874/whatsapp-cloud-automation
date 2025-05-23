import openai
from app.config import config
from typing import List, Dict
import json

class OpenAIHandler:
    def __init__(self):
        openai.api_key = config.OPENAI_API_KEY
        self.conversation_history = {}
    
    def generate_response(self, message: str, contact: str, context: str = None) -> str:
        """Generate AI response using OpenAI GPT"""
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
            
            response = openai.ChatCompletion.create(
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
        try:
            prompt = f"""
            Create a personalized message based on this template: "{template}"
            Make it feel natural and personal for WhatsApp.
            Additional info: {json.dumps(kwargs)}
            """
            
            response = openai.ChatCompletion.create(
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
        try:
            prompt = f"""
            Analyze the sentiment of this message: "{message}"
            Respond with JSON format: {{"sentiment": "positive/negative/neutral", "confidence": 0.0-1.0}}
            """
            
            response = openai.ChatCompletion.create(
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

