
from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
import threading
import time

from app.config import config
from app.database import get_db, User, Message, ScheduledMessage, AutomationRule
from app.whatsapp_client import WhatsAppClient
from app.openai_handler import OpenAIHandler
from app.scheduler import MessageScheduler

app = FastAPI(title="WhatsApp OpenAI Automation")

# Setup static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize components
whatsapp_client = WhatsAppClient()
openai_handler = OpenAIHandler()
scheduler = MessageScheduler(whatsapp_client, openai_handler)

# Global state
automation_active = False

@app.on_event("startup")
async def startup_event():
    print(">>> Starting WhatsApp client...")
    whatsapp_client = WhatsAppClient()
    print(">>> Opening WhatsApp Web...")
    whatsapp_client.driver.get("https://web.whatsapp.com")
    input(">>> Scan the QR code in Chrome, then press Enter here to continue...")
    print(">>> WhatsApp is now ready.")


def message_handler(message_data):
    """Handle incoming WhatsApp messages"""
    global automation_active
    
    if not automation_active:
        return
    
    db = next(get_db())
    try:
        sender = message_data['sender']
        message_text = message_data['message']
        
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
        
    except Exception as e:
        print(f"Error handling message: {e}")
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    messages = db.query(Message).order_by(Message.timestamp.desc()).limit(10).all()
    scheduled_messages = db.query(ScheduledMessage).filter(ScheduledMessage.is_active == True).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "messages": messages,
        "scheduled_messages": scheduled_messages,
        "whatsapp_connected": whatsapp_client.is_connected,
        "automation_active": automation_active
    })

@app.get("/qr-code")
async def get_qr_code():
    qr_code = whatsapp_client.get_qr_code()
    if qr_code:
        return {"qr_code": qr_code}
    else:
        raise HTTPException(status_code=500, detail="Failed to generate QR code")

@app.post("/check-connection")
async def check_connection():
    connected = whatsapp_client.check_connection()
    if connected and not automation_active:
        # Start message monitoring
        whatsapp_client.start_message_monitoring(message_handler)
        scheduler.start_scheduler()
    
    return {"connected": connected}

@app.post("/toggle-automation")
async def toggle_automation():
    global automation_active
    automation_active = not automation_active
    return {"automation_active": automation_active}

@app.post("/send-message")
async def send_message(
    contact: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db)
):
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
        
        return {"success": True, "message": "Message sent successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send message")

@app.post("/schedule-message")
async def schedule_message(
    contact: str = Form(...),
    message: str = Form(...),
    schedule_time: str = Form(...),
):
    success = scheduler.add_scheduled_message(contact, message, schedule_time)
    
    if success:
        return {"success": True, "message": "Message scheduled successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to schedule message")

@app.post("/add-automation-rule")
async def add_automation_rule(
    trigger_keyword: str = Form(...),
    response_template: str = Form(...),
    use_ai: bool = Form(True),
    db: Session = Depends(get_db)
):
    try:
        new_rule = AutomationRule(
            trigger_keyword=trigger_keyword,
            response_template=response_template,
            use_ai=use_ai
        )
        db.add(new_rule)
        db.commit()
        
        return {"success": True, "message": "Automation rule added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add rule: {e}")

@app.get("/api/messages")
async def get_messages(db: Session = Depends(get_db)):
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

@app.on_event("shutdown")
async def shutdown_event():
    whatsapp_client.close()
    scheduler.stop_scheduler()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT, debug=config.DEBUG)


