"""
Download "Pemegang Saham di atas 5% (KSEI) [Semua Emiten Saham]" - latest PDF
from IDX using Selenium + webdriver-manager.
"""
import os
import re
import time
import glob
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

TARGET_URL = "https://www.idx.co.id/id/perusahaan-tercatat/keterbukaan-informasi"


def rename_pdf(filepath):
    """Rename downloaded PDF to a cleaner format: YYYYMMDD_Pemegang_Saham_5persen_KSEI.pdf"""
    filename = os.path.basename(filepath)
    # Extract date (YYYYMMDD) from the original filename
    match = re.match(r'(\d{8})', filename)
    if match:
        date_str = match.group(1)
    else:
        date_str = time.strftime('%Y%m%d')
    
    new_name = f"{date_str}_Pemegang_Saham_5persen_KSEI.pdf"
    new_path = os.path.join(os.path.dirname(filepath), new_name)
    
    os.rename(filepath, new_path)
    print(f"Renamed: {filename} -> {new_name}")
    return new_path


def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    prefs = {
        "download.default_directory": DATA_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
    }
    options.add_experimental_option("prefs", prefs)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # Enable downloads in headless mode via CDP
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": DATA_DIR
    })
    
    return driver


def download_pdf():
    print("Setting up Chrome driver...")
    driver = setup_driver()
    wait = WebDriverWait(driver, 30)
    
    try:
        print(f"Opening: {TARGET_URL}")
        driver.get(TARGET_URL)
        
        # Wait longer for Cloudflare challenge to resolve in headless
        print("Waiting for page to fully load...")
        time.sleep(10)
        
        # Find the search box with explicit wait
        print("Looking for search input...")
        search_input = None
        selectors = [
            "input[type='text']",
            "input.form-control",
            "input[placeholder*='cari' i]",
            "input[placeholder*='search' i]",
        ]
        for sel in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elements:
                    if elem.is_displayed():
                        search_input = elem
                        print(f"  Found with selector: {sel}")
                        break
            except:
                pass
            if search_input:
                break
        
        # If still not found, try WebDriverWait
        if not search_input:
            try:
                print("  Trying explicit wait...")
                search_input = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
                )
            except:
                pass
        
        if not search_input:
            print("Could not find search input!")
            driver.save_screenshot(os.path.join(DATA_DIR, "debug.png"))
            print(f"Page title: {driver.title}")
            return None
        
        # Search for "5%"
        print("Typing '5%' in search box...")
        search_input.clear()
        search_input.send_keys("5%")
        time.sleep(1)
        search_input.send_keys(Keys.ENTER)
        print("Waiting for search results...")
        time.sleep(8)
        
        # Find all PDF links and their text
        pdf_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='.pdf']")
        print(f"Found {len(pdf_links)} PDF links")
        
        # We want the FIRST "20260306_Semua Emiten Saham_Pengumuman Bursa_32041440_lamp1.pdf" link
        # which is the latest (most recent) attachment of "Pemegang Saham di atas 5% (KSEI)"
        target_link = None
        target_text = None
        
        for link in pdf_links:
            text = link.text.strip()
            href = link.get_attribute("href") or ""
            
            # Match the attachment PDF link (not the title link)
            # The attachment has filename like "20260306_Semua Emiten Saham_Pengumuman Bursa_XXXXX_lamp1.pdf"
            if "Semua Emiten Saham" in text and "lamp1.pdf" in text:
                target_link = href
                target_text = text
                print(f"\n>>> Found target: {text}")
                print(f"    URL: {href}")
                break
        
        if not target_link:
            # Fallback: look for the first link that contains "lamp1" after a "5% (KSEI)" heading
            print("Primary match failed. Trying fallback...")
            found_ksei = False
            for link in pdf_links:
                text = link.text.strip()
                href = link.get_attribute("href") or ""
                
                if "5%" in text and "KSEI" in text:
                    found_ksei = True
                    continue
                
                if found_ksei and "lamp1" in text:
                    target_link = href
                    target_text = text
                    print(f"\n>>> Found target (fallback): {text}")
                    print(f"    URL: {href}")
                    break
        
        if not target_link:
            print("Could not find target PDF link!")
            for link in pdf_links:
                print(f"  {link.text.strip()}: {link.get_attribute('href')}")
            return None
        
        # Download using requests with Selenium cookies
        print(f"\nDownloading: {target_text}")
        cookies = driver.get_cookies()
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        
        headers = {
            "User-Agent": driver.execute_script("return navigator.userAgent"),
            "Referer": TARGET_URL,
        }
        
        resp = session.get(target_link, headers=headers, timeout=120)
        print(f"Response status: {resp.status_code}, size: {len(resp.content):,} bytes")
        
        if resp.status_code == 200 and len(resp.content) > 1000:
            # Use the link text as filename (clean it up)
            filename = target_text.replace(" ", "_") if target_text else "download.pdf"
            # Remove invalid chars
            for ch in ['<', '>', ':', '"', '|', '?', '*']:
                filename = filename.replace(ch, '')
            
            if not filename.endswith(".pdf"):
                filename += ".pdf"
            
            filepath = os.path.join(DATA_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(resp.content)
            print(f"\nSaved to: {filepath}")
            print(f"File size: {len(resp.content):,} bytes")
            return rename_pdf(filepath)
        else:
            print(f"Direct download blocked by Cloudflare. Trying click download...")
            
            # Snapshot files before click
            existing_files = set(os.listdir(DATA_DIR))
            
            # Click the link directly
            for link in pdf_links:
                if (link.get_attribute("href") or "") == target_link:
                    driver.execute_script("arguments[0].click();", link)
                    print("Clicked download link. Waiting for download...")
                    break
            
            # Wait for download to complete (check for new files)
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                current_files = set(os.listdir(DATA_DIR))
                new_files = current_files - existing_files
                # Filter out temp download files (.crdownload, .tmp)
                completed = [f for f in new_files if f.endswith('.pdf') and not f.endswith('.crdownload')]
                if completed:
                    # Clean up residual temp files (.crdownload, .htm, etc.)
                    junk = [f for f in new_files if not f.endswith('.pdf') or f.endswith('.crdownload')]
                    for jf in junk:
                        try:
                            os.remove(os.path.join(DATA_DIR, jf))
                        except:
                            pass
                    
                    filepath = os.path.join(DATA_DIR, completed[0])
                    print(f"\nDownloaded: {filepath}")
                    print(f"File size: {os.path.getsize(filepath):,} bytes")
                    return rename_pdf(filepath)
                if i % 5 == 0 and i > 0:
                    print(f"  Still waiting... ({i}s)")
        
            print("Download timed out.")
        
        return None
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Clean up any residual temp files (.crdownload, .htm, etc.)
        for f in os.listdir(DATA_DIR):
            if f.endswith('.crdownload') or f == 'downloads.htm':
                try:
                    os.remove(os.path.join(DATA_DIR, f))
                except:
                    pass
        driver.quit()
        print("Driver closed.")


if __name__ == "__main__":
    result = download_pdf()
    if result:
        print(f"\n{'='*60}")
        print(f"SUCCESS! Downloaded: {result}")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("FAILED to download the PDF.")
        print(f"{'='*60}")
