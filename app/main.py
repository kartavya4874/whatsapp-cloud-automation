from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
import threading
import time
import logging

from app.config import config
from app.database import get_db, User, Message, ScheduledMessage, AutomationRule
from app.whatsapp_client import WhatsAppClient
from app.openai_handler import OpenAIHandler
from app.scheduler import MessageScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp OpenAI Automation")

# Setup static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize components
whatsapp_client = None
openai_handler = OpenAIHandler()
scheduler = None

# Global state
automation_active = False
whatsapp_setup_complete = False

def message_handler(message_data):
    """Handle incoming WhatsApp messages"""
    global automation_active
    
    if not automation_active:
        return
    
    db = next(get_db())
    try:
        sender = message_data['sender']
        message_text = message_data['message']
        
        logger.info(f"Processing message from {sender}: {message_text}")
        
        # Save incoming message
        new_message = Message(
            contact=sender,
            message=message_text,
            is_automated=False
        )
        db.add(new_message)
        db.commit()
        
        # Check automation rules
        rules = db.query(AutomationRule).filter(AutomationRule.is_active == True).all()
        
        should_respond = False
        response_template = None
        use_ai = True
        
        for rule in rules:
            if rule.trigger_keyword.lower() in message_text.lower():
                should_respond = True
                response_template = rule.response_template
                use_ai = rule.use_ai
                break
        
        # Generate and send response
        if should_respond:
            if use_ai:
                ai_response = openai_handler.generate_response(
                    message_text, sender, response_template
                )
            else:
                ai_response = response_template
            
            # Send response
            if whatsapp_client.send_message(sender, ai_response):
                # Save response
                new_message.response = ai_response
                db.commit()
                
                # Save as separate message record
                response_msg = Message(
                    contact=sender,
                    message=ai_response,
                    is_automated=True
                )
                db.add(response_msg)
                db.commit()
                
                logger.info(f"Sent automated response to {sender}")
        
    except Exception as e:
        logger.error(f"Error handling message: {e}")
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint - redirect based on setup status"""
    global whatsapp_setup_complete
    
    if not whatsapp_setup_complete:
        return RedirectResponse(url="/setup", status_code=302)
    else:
        return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    """Setup page for QR code scanning"""
    return templates.TemplateResponse("setup.html", {
        "request": request,
        "whatsapp_connected": whatsapp_client.is_connected if whatsapp_client else False
    })

@app.post("/initialize-whatsapp")
async def initialize_whatsapp():
    """Initialize WhatsApp client and open web interface"""
    global whatsapp_client, scheduler
    
    try:
        logger.info("Initializing WhatsApp client...")
        
        if whatsapp_client:
            whatsapp_client.close()
        
        whatsapp_client = WhatsAppClient()
        
        # Open WhatsApp Web
        if whatsapp_client.open_whatsapp_web():
            return {"success": True, "message": "WhatsApp Web opened. Please scan the QR code."}
        else:
            return {"success": False, "message": "Failed to open WhatsApp Web"}
            
    except Exception as e:
        logger.error(f"Error initializing WhatsApp: {e}")
        return {"success": False, "message": f"Error: {e}"}

@app.post("/check-qr-status")
async def check_qr_status():
    """Check if QR code has been scanned"""
    global whatsapp_client, scheduler, whatsapp_setup_complete
    
    if not whatsapp_client:
        return {"connected": False, "message": "WhatsApp client not initialized"}
    
    try:
        # Check connection status
        if whatsapp_client.check_connection():
            if not whatsapp_setup_complete:
                # Initialize scheduler
                scheduler = MessageScheduler(whatsapp_client, openai_handler)
                scheduler.start_scheduler()
                
                # Start message monitoring
                whatsapp_client.start_message_monitoring(message_handler)
                
                whatsapp_setup_complete = True
                logger.info("WhatsApp setup completed successfully!")
            
            return {"connected": True, "message": "WhatsApp connected successfully!"}
        else:
            return {"connected": False, "message": "Still waiting for QR code scan..."}
            
    except Exception as e:
        logger.error(f"Error checking QR status: {e}")
        return {"connected": False, "message": f"Error: {e}"}

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard page"""
    global whatsapp_setup_complete
    
    if not whatsapp_setup_complete:
        return RedirectResponse(url="/setup", status_code=302)
    
    messages = db.query(Message).order_by(Message.timestamp.desc()).limit(10).all()
    scheduled_messages = db.query(ScheduledMessage).filter(ScheduledMessage.is_active == True).all()
    automation_rules = db.query(AutomationRule).filter(AutomationRule.is_active == True).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "messages": messages,
        "scheduled_messages": scheduled_messages,
        "automation_rules": automation_rules,
        "whatsapp_connected": whatsapp_client.is_connected if whatsapp_client else False,
        "automation_active": automation_active
    })

@app.post("/toggle-automation")
async def toggle_automation():
    """Toggle automation on/off"""
    global automation_active
    
    if not whatsapp_setup_complete or not whatsapp_client or not whatsapp_client.is_connected:
        raise HTTPException(status_code=400, detail="WhatsApp not connected")
    
    automation_active = not automation_active
    logger.info(f"Automation {'activated' if automation_active else 'deactivated'}")
    
    return {"automation_active": automation_active}

@app.post("/send-message")
async def send_message(
    contact: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db)
):
    """Send a manual message"""
    if not whatsapp_client or not whatsapp_client.is_connected:
        raise HTTPException(status_code=400, detail="WhatsApp not connected")
    
    try:
        success = whatsapp_client.send_message(contact, message)
        
        if success:
            # Save message to database
            new_message = Message(
                contact=contact,
                message=message,
                is_automated=False
            )
            db.add(new_message)
            db.commit()
            
            logger.info(f"Manual message sent to {contact}")
            return {"success": True, "message": "Message sent successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send message")
            
    except Exception as e:
        logger.error(f"Error sending manual message: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {e}")

@app.post("/schedule-message")
async def schedule_message(
    contact: str = Form(...),
    message: str = Form(...),
    schedule_time: str = Form(...),
    db: Session = Depends(get_db)
):
    """Schedule a message"""
    try:
        if not scheduler:
            raise HTTPException(status_code=400, detail="Scheduler not initialized")
        
        success = scheduler.add_scheduled_message(contact, message, schedule_time)
        
        if success:
            logger.info(f"Message scheduled for {contact} at {schedule_time}")
            return {"success": True, "message": "Message scheduled successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to schedule message")
            
    except Exception as e:
        logger.error(f"Error scheduling message: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {e}")

@app.post("/add-automation-rule")
async def add_automation_rule(
    trigger_keyword: str = Form(...),
    response_template: str = Form(...),
    use_ai: bool = Form(True),
    db: Session = Depends(get_db)
):
    """Add new automation rule"""
    try:
        new_rule = AutomationRule(
            trigger_keyword=trigger_keyword,
            response_template=response_template,
            use_ai=use_ai
        )
        db.add(new_rule)
        db.commit()
        
        logger.info(f"New automation rule added: {trigger_keyword}")
        return {"success": True, "message": "Automation rule added successfully"}
        
    except Exception as e:
        logger.error(f"Error adding automation rule: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add rule: {e}")

@app.get("/api/messages")
async def get_messages(db: Session = Depends(get_db)):
    """Get recent messages"""
    messages = db.query(Message).order_by(Message.timestamp.desc()).limit(50).all()
    return {"messages": [
        {
            "id": msg.id,
            "contact": msg.contact,
            "message": msg.message,
            "response": msg.response,
            "timestamp": msg.timestamp.isoformat(),
            "is_automated": msg.is_automated
        }
        for msg in messages
    ]}

@app.get("/api/status")
async def get_status():
    """Get current system status"""
    return {
        "whatsapp_connected": whatsapp_client.is_connected if whatsapp_client else False,
        "automation_active": automation_active,
        "setup_complete": whatsapp_setup_complete,
        "scheduler_running": scheduler is not None
    }

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global whatsapp_client, scheduler
    
    logger.info("Shutting down application...")
    
    if scheduler:
        scheduler.stop_scheduler()
    
    if whatsapp_client:
        whatsapp_client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT, debug=config.DEBUG)
