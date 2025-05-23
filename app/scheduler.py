import schedule
import time
import threading
from datetime import datetime
from app.database import SessionLocal, ScheduledMessage
from app.whatsapp_client import WhatsAppClient
from app.openai_handler import OpenAIHandler

class MessageScheduler:
    def __init__(self, whatsapp_client: WhatsAppClient, openai_handler: OpenAIHandler):
        self.whatsapp_client = whatsapp_client
        self.openai_handler = openai_handler
        self.running = False
        self.setup_scheduled_jobs()
    
    def setup_scheduled_jobs(self):
        """Setup all scheduled jobs from database"""
        db = SessionLocal()
        try:
            scheduled_messages = db.query(ScheduledMessage).filter(
                ScheduledMessage.is_active == True
            ).all()
            
            for msg in scheduled_messages:
                # Parse schedule time (simplified - you can make this more robust)
                if "daily" in msg.scheduled_time.lower():
                    time_part = msg.scheduled_time.split("at")[1].strip()
                    schedule.every().day.at(time_part).do(
                        self.send_scheduled_message,
                        msg.contact,
                        msg.message
                    )
                elif "weekly" in msg.scheduled_time.lower():
                    # Handle weekly schedules
                    pass
                
        except Exception as e:
            print(f"Error setting up scheduled jobs: {e}")
        finally:
            db.close()
    
    def send_scheduled_message(self, contact: str, message_template: str):
        """Send a scheduled message"""
        try:
            # Generate personalized message using AI
            personalized_message = self.openai_handler.generate_scheduled_message(
                message_template, contact
            )
            
            # Send via WhatsApp
            success = self.whatsapp_client.send_message(contact, personalized_message)
            
            if success:
                print(f"Scheduled message sent to {contact}")
            else:
                print(f"Failed to send scheduled message to {contact}")
                
        except Exception as e:
            print(f"Error sending scheduled message: {e}")
    
    def start_scheduler(self):
        """Start the scheduler in a separate thread"""
        def run_scheduler():
            self.running = True
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        print("Message scheduler started")
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        self.running = False
        print("Message scheduler stopped")
    
    def add_scheduled_message(self, contact: str, message: str, schedule_time: str):
        """Add a new scheduled message"""
        db = SessionLocal()
        try:
            scheduled_msg = ScheduledMessage(
                contact=contact,
                message=message,
                scheduled_time=schedule_time
            )
            db.add(scheduled_msg)
            db.commit()
            
            # Add to schedule
            if "daily" in schedule_time.lower():
                time_part = schedule_time.split("at")[1].strip()
                schedule.every().day.at(time_part).do(
                    self.send_scheduled_message, contact, message
                )
            
            return True
            
        except Exception as e:
            print(f"Error adding scheduled message: {e}")
            return False
        finally:
            db.close()

