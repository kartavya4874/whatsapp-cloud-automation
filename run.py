import uvicorn
from app.main import app
from app.config import config

if __name__ == "__main__":
    print("Starting WhatsApp OpenAI Automation Server...")
    print(f"Server will run on http://{config.HOST}:{config.PORT}")
    print("Make sure to set your OPENAI_API_KEY in the .env file!")
    
    uvicorn.run(
        "app.main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )
