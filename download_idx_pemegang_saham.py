"""
Download latest "Pemegang Saham di atas X% (KSEI) [Semua Emiten Saham]" PDF
from IDX Keterbukaan Informasi using Selenium + webdriver-manager.

Usage:
    python download_idx_pemegang_saham.py --persen 5     # Download 5% report latest
    python download_idx_pemegang_saham.py --persen 1     # Download 1% report latest
    python download_idx_pemegang_saham.py --persen 5 --start-date 2026-03-01 --end-date 2026-03-05
"""
import os
import re
import argparse
import time
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


def rename_pdf(filepath, persen, forced_date=None):
    """Rename downloaded PDF to: YYYYMMDD_Pemegang_Saham_Xpersen_KSEI.pdf"""
    filename = os.path.basename(filepath)
    match = re.search(r'(\d{8})', filename)
    date_str = match.group(1) if match else (forced_date or time.strftime('%Y%m%d'))

    base_name = f"{date_str}_Pemegang_Saham_{persen}persen_KSEI"
    new_name = f"{base_name}.pdf"
    new_path = os.path.join(os.path.dirname(filepath), new_name)

    counter = 1
    while os.path.exists(new_path):
        if counter == 1 and forced_date is None and match: 
            return new_path 
        new_name = f"{base_name}_{counter}.pdf"
        new_path = os.path.join(os.path.dirname(filepath), new_name)
        counter += 1

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


def download_pdfs(persen="5", start_date=None, end_date=None):
    """Download the Pemegang Saham di atas X% PDFs based on date filters."""
    search_keyword = f"{persen}%"
    print(f"Setting up Chrome driver...")
    print(f"Target: Pemegang Saham di atas {persen}% (KSEI) [Semua Emiten Saham]")
    if start_date and end_date:
        print(f"Date Range: {start_date} to {end_date}")
        
    driver = setup_driver()
    wait = WebDriverWait(driver, 30)
    downloaded_files = []

    try:
        print(f"Opening: {TARGET_URL}")
        driver.get(TARGET_URL)

        # Wait for Cloudflare challenge to resolve
        print("Waiting for page to fully load...")
        time.sleep(10)

        # Find the search box
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

        if not search_input:
            try:
                print("  Trying explicit wait...")
                search_input = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='cari' i]"))
                )
            except:
                pass

        if not search_input:
            print("Could not find search input!")
            print(f"Page title: {driver.title}")
            return []

        # Entering Search Term
        print(f"Typing '{search_keyword}' in search box...")
        search_input.clear()
        search_input.send_keys(search_keyword)
        time.sleep(1)
        
        # Setting Date Range
        if start_date and end_date:
            print("Setting Date Range...")
            try:
                date_input = driver.find_element(By.CSS_SELECTOR, "input.mx-input[placeholder='Dari - Sampai']")
                date_input.click()
                time.sleep(0.5)
                # Dispatch Vue events
                driver.execute_script(
                    f"arguments[0].value = '{start_date} ~ {end_date}'; "
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true })); "
                    "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", 
                    date_input
                )
                time.sleep(1)
                date_input.send_keys(Keys.ENTER)
                time.sleep(1)
            except Exception as e:
                print(f"Could not set date range: {e}")

        # Execute Search
        search_input.send_keys(Keys.ENTER)
        print("Waiting for search results...")
        time.sleep(8)

        # Find all PDF links
        pdf_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='.pdf']")
        print(f"Found {len(pdf_links)} PDF links")

        # Find targets
        targets = []
        for link in pdf_links:
            text = link.text.strip()
            href = link.get_attribute("href") or ""

            if "Semua Emiten Saham" in text and "lamp1.pdf" in text:
                targets.append((text, href, link))

        # Fallback if specific naming isn't exactly matching
        if not targets:
            print("Primary match failed. Trying fallback...")
            found_ksei = False
            for link in pdf_links:
                text = link.text.strip()
                href = link.get_attribute("href") or ""

                if f"{persen}%" in text and "KSEI" in text:
                    found_ksei = True
                    continue

                if found_ksei and "lamp1" in text:
                    targets.append((text, href, link))
                    found_ksei = False # reset to look for the next block
                    
        if not targets:
            print("Could not find any target PDF link!")
            for link in pdf_links:
                print(f"  {link.text.strip()}: {link.get_attribute('href')}")
            return []
            
        # If no date supplied, we only download the very first (latest)
        if not start_date or not end_date:
            targets = targets[:1]

        print(f"Identified {len(targets)} files to download.")

        cookies = driver.get_cookies()
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])

        headers = {
            "User-Agent": driver.execute_script("return navigator.userAgent"),
            "Referer": TARGET_URL,
        }

        for idx, (target_text, target_link, web_link) in enumerate(targets):
            print(f"\n[{idx+1}/{len(targets)}] Processing: {target_text}")
            
            date_match = re.search(r'(\d{8})', target_text or "")
            expected_file = f"{date_match.group(1)}_Pemegang_Saham_{persen}persen_KSEI.pdf" if date_match else None
            if expected_file:
                expected_path = os.path.join(DATA_DIR, expected_file)
                if os.path.exists(expected_path):
                    print(f"File already exists: {expected_file}. Skipping download.")
                    downloaded_files.append(expected_path)
                    continue

            print(f"Downloading: {target_link}")
            try:
                resp = session.get(target_link, headers=headers, timeout=120)
            except Exception as e:
                print(f"Direct download request failed: {e}")
                resp = None
            
            if resp and resp.status_code == 200 and len(resp.content) > 1000:
                filename = target_text.replace(" ", "_") if target_text else f"download_{idx}.pdf"
                for ch in ['<', '>', ':', '"', '|', '?', '*']:
                    filename = filename.replace(ch, '')
                if not filename.endswith(".pdf"):
                    filename += ".pdf"

                filepath = os.path.join(DATA_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                final_path = rename_pdf(filepath, persen)
                downloaded_files.append(final_path)
            else:
                print("Direct download blocked. Trying click download...")
                existing_files = set(os.listdir(DATA_DIR))
                
                driver.execute_script("arguments[0].click();", web_link)
                
                downloaded = False
                for i in range(30):
                    time.sleep(1)
                    current_files = set(os.listdir(DATA_DIR))
                    new_files = current_files - existing_files
                    completed = [f for f in new_files if f.endswith('.pdf') and not f.endswith('.crdownload')]
                    if completed:
                        junk = [f for f in new_files if not f.endswith('.pdf') or f.endswith('.crdownload')]
                        for jf in junk:
                            try:
                                os.remove(os.path.join(DATA_DIR, jf))
                            except:
                                pass
                        filepath = os.path.join(DATA_DIR, completed[0])
                        final_path = rename_pdf(filepath, persen)
                        downloaded_files.append(final_path)
                        downloaded = True
                        break
                    
                if not downloaded:
                    print("Download timed out.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up residual temp files
        for f in os.listdir(DATA_DIR):
            if f.endswith('.crdownload') or f == 'downloads.htm':
                try:
                    os.remove(os.path.join(DATA_DIR, f))
                except:
                    pass
        driver.quit()
        print("Driver closed.")

    return downloaded_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download IDX Pemegang Saham PDFs.")
    parser.add_argument("--persen", choices=["1", "5"], default="5", help="Percent threshold (1 or 5)")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    results = download_pdfs(args.persen, args.start_date, args.end_date)
    if results:
        print(f"\n{'='*60}")
        print(f"SUCCESS! Downloaded {len(results)} files:")
        for res in results:
            print(f" - {res}")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("FAILED or No files downloaded.")
        print(f"{'='*60}")
