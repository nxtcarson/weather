from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
from datetime import datetime
import logging
import os

#doesnt work for now

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Schools to monitor - using simpler terms for matching
SCHOOLS_TO_MONITOR = {
    'URSULINE': ['URSULINE', 'URSULINE HIGH'],
    'BOARDMAN': ['BOARDMAN', 'BOARDMAN LOCAL'],
    'MCCTC': ['MCCTC', 'MAHONING COUNTY CAREER', 'CAREER AND TECHNICAL', 'MAHONING COUNTY CTC'],
    'POLAND': ['POLAND', 'POLAND LOCAL'],
    'BEAVER': ['BEAVER', 'BEAVER LOCAL', 'BEAVER SCHOOLS'],
    'GIRARD': ['GIRARD', 'GIRARD LOCAL', 'GIRARD SCHOOLS']
}

def setup_driver():
    try:
        logging.info("Setting up Chrome options...")
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-web-security')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-webgl')
        options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        # Additional options to handle graphics and USB errors
        options.add_argument('--disable-gpu-sandbox')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-usb')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        # Specify the path to the manually downloaded ChromeDriver
        chromedriver_path = os.path.join(os.path.dirname(__file__), 'chromedriver.exe')
        
        logging.info(f"Using ChromeDriver at: {chromedriver_path}")
        
        logging.info("Creating Chrome service...")
        service = Service(chromedriver_path)
        
        logging.info("Starting Chrome browser...")
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        logging.info("Chrome browser started successfully")
        
        return driver
    except Exception as e:
        logging.error(f"Error setting up driver: {str(e)}")
        raise

def check_website(driver, url, element_selector, element_type):
    try:
        logging.info(f"Accessing {url}")
        driver.get(url)
        
        # Wait for content to load with explicit wait
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((element_selector, element_type)))
        
        # Get page source after JavaScript has run
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Try to find the closings list specifically
        closings_elements = soup.find_all(['div', 'p', 'span', 'li', 'tr', 'td'])  # Look in various elements
        
        closings = []
        
        # Search through each element's text
        for element in closings_elements:
            element_text = element.get_text().upper()
            for school_name, search_terms in SCHOOLS_TO_MONITOR.items():
                for term in search_terms:
                    if term.upper() in element_text:
                        # Look for full closing phrase
                        closing_phrase = f"{term.upper()}: CLOSED"
                        if closing_phrase in element_text:
                            closings.append(school_name)
                            logging.info(f"Found: {school_name}")
                            logging.debug(f"Context: {element_text}")
                            break
                        # Also check for delays
                        delay_phrase = f"{term.upper()}: 2-HOUR DELAY" 
                        if delay_phrase in element_text:
                            closings.append(f"{school_name} (DELAY)")
                            logging.info(f"Found: {school_name} (DELAY)")
                            logging.debug(f"Context: {element_text}")
                            break
        
        return list(set(closings))  # Remove duplicates
    except Exception as e:
        logging.error(f"Error checking {url}: {str(e)}")
        return []

def main():
    print("Starting school closing monitor...")
    print(f"Monitoring schools: {', '.join(SCHOOLS_TO_MONITOR.keys())}")
    
    # Create status file
    status_file = os.path.join(os.path.dirname(__file__), '..', '..', 'logs', 'weather_status.txt')
    
    while True:  # Retry loop for browser setup
        try:
            # Setup the browser
            print("Setting up web browser...")
            driver = setup_driver()
            
            # Keep track of already notified closings to avoid duplicates
            notified_closings = set()
            
            while True:
                try:
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"\nChecking closings at {current_time}")
                    
                    # Check both websites with timeouts
                    wkbn_closings = check_website(driver, 'https://www.wkbn.com/weather/closings/', By.CLASS_NAME, "article-list")
                    time.sleep(2)  # Small delay between requests
                    wfmj_closings = check_website(driver, 'https://www.wfmj.com/school-closings', By.TAG_NAME, "table")
                    all_closings = set(wkbn_closings + wfmj_closings)
                    
                    # Write status to file
                    try:
                        with open(status_file, 'w') as f:
                            if all_closings:
                                f.write("CLOSED")  # Green
                            elif any('2-HOUR DELAY' in status for status in all_closings):
                                f.write("DELAY")  # Yellow
                            else:
                                f.write("NONE")   # Red
                    except Exception as e:
                        logging.error(f"Error writing status: {e}")
                    
                    # Find new closings
                    new_closings = all_closings - notified_closings
                    
                    # Notify about new closings
                    if new_closings:
                        print("\n🚨 NEW SCHOOL CLOSINGS DETECTED! 🚨")
                        for school in new_closings:
                            print(f"CLOSED: {school}")
                        notified_closings.update(new_closings)
                    else:
                        print("No new closings found for monitored schools.")
                        logging.info("Checked for closings - none found")
                    
                    # Wait before next check
                    time.sleep(10)
                    
                except Exception as e:
                    logging.error(f"Error in main loop: {str(e)}")
                    time.sleep(5)  # Wait before retrying
                    continue
                    
        except Exception as e:
            logging.error(f"Browser error: {str(e)}")
            time.sleep(5)  # Wait before retrying browser setup
            continue
            
        finally:
            try:
                driver.quit()
            except:
                pass

if __name__ == "__main__":
    main()
