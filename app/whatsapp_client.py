from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import threading
from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhatsAppClient:
    def __init__(self):
        self.driver = None
        self.is_connected = False
        self.message_handlers = []
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--user-data-dir=/data')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1200,800')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Keep browser visible for QR scanning
            chrome_options.add_argument('--headless')  # Comment out for QR scanning
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Chrome driver setup completed")
            
        except Exception as e:
            logger.error(f"Error setting up Chrome driver: {e}")
            raise
    
    def open_whatsapp_web(self):
        """Open WhatsApp Web and wait for QR scan"""
        try:
            logger.info("Opening WhatsApp Web...")
            self.driver.get("https://web.whatsapp.com")
            
            # Wait a moment for page to load
            time.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"Error opening WhatsApp Web: {e}")
            return False
    
    def wait_for_qr_scan(self, timeout=300):  # 5 minutes timeout
        """Wait for QR code to be scanned"""
        try:
            logger.info("Waiting for QR code scan...")
            
            # Wait for QR code to disappear (indicating successful scan)
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    # Check if we can find the main chat interface
                    if self.check_connection():
                        logger.info("QR code scanned successfully! WhatsApp is connected.")
                        self.is_connected = True
                        return True
                    
                    # Check if QR code is still present
                    qr_elements = self.driver.find_elements(By.CSS_SELECTOR, 'canvas[aria-label="Scan me!"]')
                    if not qr_elements:
                        # QR might be gone, check for login
                        time.sleep(2)
                        if self.check_connection():
                            logger.info("Login successful!")
                            self.is_connected = True
                            return True
                    
                    time.sleep(2)
                    
                except Exception as e:
                    logger.debug(f"Still waiting for QR scan: {e}")
                    time.sleep(2)
                    continue
            
            logger.error("Timeout waiting for QR code scan")
            return False
            
        except Exception as e:
            logger.error(f"Error waiting for QR scan: {e}")
            return False
    
    def check_connection(self) -> bool:
        """Check if WhatsApp is connected"""
        try:
            # Look for the main chat interface elements
            selectors_to_check = [
                '[data-testid="chat-list"]',
                'div[id="app"] div[data-testid="chat-list"]',
                '[aria-label="Chat list"]',
                'div[role="application"]'
            ]
            
            for selector in selectors_to_check:
                try:
                    element = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if element:
                        self.is_connected = True
                        logger.info("WhatsApp connection verified")
                        return True
                except:
                    continue
            
            self.is_connected = False
            return False
            
        except Exception as e:
            logger.debug(f"Connection check failed: {e}")
            self.is_connected = False
            return False
    
    def send_message(self, contact: str, message: str) -> bool:
        """Send message to a contact"""
        try:
            if not self.is_connected:
                logger.error("WhatsApp not connected")
                return False
            
            logger.info(f"Sending message to {contact}")
            
            # Multiple selectors for search box
            search_selectors = [
                'div[contenteditable="true"][data-tab="3"]',
                '[data-testid="chat-list-search"]',
                'div[title="Search input textbox"]',
                'div[role="textbox"][data-tab="3"]'
            ]
            
            search_box = None
            for selector in search_selectors:
                try:
                    search_box = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if not search_box:
                logger.error("Could not find search box")
                return False
            
            # Clear and search for contact
            search_box.click()
            search_box.clear()
            search_box.send_keys(contact)
            time.sleep(2)
            
            # Click on contact - try multiple selectors
            contact_selectors = [
                f'span[title="{contact}"]',
                f'div[title="{contact}"]',
                f'[data-testid="cell-frame-title"][title="{contact}"]'
            ]
            
            contact_clicked = False
            for selector in contact_selectors:
                try:
                    contact_element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    contact_element.click()
                    contact_clicked = True
                    break
                except:
                    continue
            
            if not contact_clicked:
                logger.error(f"Could not find contact: {contact}")
                return False
            
            time.sleep(1)
            
            # Find message input box
            message_selectors = [
                'div[contenteditable="true"][data-tab="10"]',
                '[data-testid="conversation-compose-box-input"]',
                'div[contenteditable="true"][role="textbox"]'
            ]
            
            message_box = None
            for selector in message_selectors:
                try:
                    message_box = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if not message_box:
                logger.error("Could not find message input box")
                return False
            
            # Type and send message
            message_box.click()
            message_box.clear()
            message_box.send_keys(message)
            
            # Send message
            send_selectors = [
                '[data-testid="send"]',
                'button[data-tab="11"]',
                'span[data-icon="send"]'
            ]
            
            for selector in send_selectors:
                try:
                    send_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    send_button.click()
                    logger.info(f"Message sent to {contact}")
                    return True
                except:
                    continue
            
            logger.error("Could not find send button")
            return False
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def get_new_messages(self) -> List[Dict]:
        """Get new messages from WhatsApp"""
        try:
            if not self.is_connected:
                return []
            
            messages = []
            
            # Find message containers
            message_selectors = [
                'div[data-testid="msg-container"]',
                'div[data-testid="conversation-panel-messages"] > div > div',
                'div.message-in, div.message-out'
            ]
            
            message_elements = []
            for selector in message_selectors:
                try:
                    message_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if message_elements:
                        break
                except:
                    continue
            
            # Process recent messages
            for element in message_elements[-5:]:
                try:
                    # Try to get message text
                    text_selectors = [
                        'span.copyable-text',
                        'div.copyable-text',
                        'span[data-testid="conversation-text"]'
                    ]
                    
                    message_text = ""
                    for text_sel in text_selectors:
                        try:
                            text_element = element.find_element(By.CSS_SELECTOR, text_sel)
                            message_text = text_element.text
                            break
                        except:
                            continue
                    
                    if message_text:
                        messages.append({
                            'sender': 'Unknown',  # You'll need to implement sender detection
                            'message': message_text,
                            'timestamp': time.time()
                        })
                        
                except Exception as e:
                    logger.debug(f"Error processing message element: {e}")
                    continue
            
            return messages
            
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return []
    
    def start_message_monitoring(self, callback):
        """Start monitoring for new messages"""
        def monitor():
            logger.info("Starting message monitoring...")
            last_message_count = 0
            
            while self.is_connected:
                try:
                    if not self.check_connection():
                        logger.warning("Connection lost, stopping monitoring")
                        break
                    
                    new_messages = self.get_new_messages()
                    
                    # Simple way to detect new messages
                    if len(new_messages) > last_message_count:
                        for message in new_messages[last_message_count:]:
                            callback(message)
                    
                    last_message_count = len(new_messages)
                    time.sleep(5)  # Check every 5 seconds
                    
                except Exception as e:
                    logger.error(f"Error in message monitoring: {e}")
                    time.sleep(10)
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        logger.info("Message monitoring thread started")
    
    def close(self):
        """Close the driver"""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("WhatsApp client closed")
        except Exception as e:
            logger.error(f"Error closing driver: {e}")
