from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import qrcode
import io
import base64
import threading
from typing import Dict, List

class WhatsAppClient:
    def __init__(self):
        self.driver = None
        self.is_connected = False
        self.message_handlers = []
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')
        # Comment out headless for development, uncomment for production
        # chrome_options.add_argument('--headless')
        
        self.driver = webdriver.Chrome(
          service=Service(ChromeDriverManager().install()),
          options=chrome_options
        )
    
    def get_qr_code(self) -> str:
        """Get QR code for WhatsApp Web login"""
        try:
            print("Opening WhatsApp Web...")
            self.driver.get("https://web.whatsapp.com")
            print("Waiting for QR code scan...")

            # Wait for QR code to appear
            qr_element = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-ref]'))
            )
            
            # Get QR code data
            qr_data = qr_element.get_attribute('data-ref')
            
            # Generate QR code image
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            print(f"Error getting QR code: {e}")
            return None
    
    def check_connection(self) -> bool:
        """Check if WhatsApp is connected"""
        try:
            # Look for the main chat interface
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="chat-list"]'))
            )
            self.is_connected = True
            return True
        except:
            self.is_connected = False
            return False
    
    def send_message(self, contact: str, message: str) -> bool:
        """Send message to a contact"""
        try:
            # Search for contact
            search_box = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="chat-list-search"]')
            search_box.clear()
            search_box.send_keys(contact)
            time.sleep(2)
            
            # Click on contact
            contact_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, f'[title="{contact}"]'))
            )
            contact_element.click()
            
            # Type message
            message_box = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="conversation-compose-box-input"]'))
            )
            message_box.clear()
            message_box.send_keys(message)
            
            # Send message
            send_button = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="send"]')
            send_button.click()
            
            return True
            
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
    
    def get_new_messages(self) -> List[Dict]:
        """Get new messages from WhatsApp"""
        try:
            # This is a simplified version - in reality, you'd need more complex logic
            # to track which messages are new
            messages = []
            
            # Find all message elements
            message_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="msg-container"]')
            
            # Process last few messages (simplified)
            for element in message_elements[-5:]:
                try:
                    text_element = element.find_element(By.CSS_SELECTOR, '.copyable-text')
                    message_text = text_element.text
                    
                    # Get sender info (simplified)
                    sender = "Unknown"
                    
                    messages.append({
                        'sender': sender,
                        'message': message_text,
                        'timestamp': time.time()
                    })
                except:
                    continue
            
            return messages
            
        except Exception as e:
            print(f"Error getting messages: {e}")
            return []
    
    def start_message_monitoring(self, callback):
        """Start monitoring for new messages"""
        def monitor():
            while self.is_connected:
                try:
                    new_messages = self.get_new_messages()
                    for message in new_messages:
                        callback(message)
                    time.sleep(5)  # Check every 5 seconds
                except Exception as e:
                    print(f"Error in message monitoring: {e}")
                    time.sleep(10)
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
    
    def close(self):
        """Close the driver"""
        if self.driver:
            self.driver.quit()
