"""
Download latest "Pemegang Saham di atas X% (KSEI) [Semua Emiten Saham]" PDF
from IDX Keterbukaan Informasi using Selenium + webdriver-manager.

Usage:
    python download_idx_pemegang_saham.py 5     # Download 5% report
    python download_idx_pemegang_saham.py 1     # Download 1% report
    python download_idx_pemegang_saham.py       # Default: 5%
"""
import os
import re
import sys
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


def rename_pdf(filepath, persen):
    """Rename downloaded PDF to: YYYYMMDD_Pemegang_Saham_Xpersen_KSEI.pdf"""
    filename = os.path.basename(filepath)
    match = re.match(r'(\d{8})', filename)
    date_str = match.group(1) if match else time.strftime('%Y%m%d')

    new_name = f"{date_str}_Pemegang_Saham_{persen}persen_KSEI.pdf"
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


def download_pdf(persen="5"):
    """Download the latest Pemegang Saham di atas X% PDF."""
    search_keyword = f"{persen}%"
    print(f"Setting up Chrome driver...")
    print(f"Target: Pemegang Saham di atas {persen}% (KSEI) [Semua Emiten Saham]")
    driver = setup_driver()
    wait = WebDriverWait(driver, 30)

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
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
                )
            except:
                pass

        if not search_input:
            print("Could not find search input!")
            print(f"Page title: {driver.title}")
            return None

        # Search
        print(f"Typing '{search_keyword}' in search box...")
        search_input.clear()
        search_input.send_keys(search_keyword)
        time.sleep(1)
        search_input.send_keys(Keys.ENTER)
        print("Waiting for search results...")
        time.sleep(8)

        # Find all PDF links
        pdf_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='.pdf']")
        print(f"Found {len(pdf_links)} PDF links")

        # Find the target: first "Semua Emiten Saham...lamp1.pdf" attachment
        target_link = None
        target_text = None

        for link in pdf_links:
            text = link.text.strip()
            href = link.get_attribute("href") or ""

            if "Semua Emiten Saham" in text and "lamp1.pdf" in text:
                target_link = href
                target_text = text
                print(f"\n>>> Found target: {text}")
                print(f"    URL: {href}")
                break

        if not target_link:
            # Fallback: first lamp1 after a "X% (KSEI)" heading
            print("Primary match failed. Trying fallback...")
            found_ksei = False
            for link in pdf_links:
                text = link.text.strip()
                href = link.get_attribute("href") or ""

                if f"{persen}%" in text and "KSEI" in text:
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

        # Check if file for this date already exists
        date_match = re.match(r'(\d{8})', target_text or "")
        if date_match:
            expected_file = f"{date_match.group(1)}_Pemegang_Saham_{persen}persen_KSEI.pdf"
            expected_path = os.path.join(DATA_DIR, expected_file)
            if os.path.exists(expected_path):
                print(f"\nFile sudah ada: {expected_file}")
                print(f"Skip download. Gunakan file yang sudah ada.")
                return expected_path

        # Try direct download with session cookies first
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
            filename = target_text.replace(" ", "_") if target_text else "download.pdf"
            for ch in ['<', '>', ':', '"', '|', '?', '*']:
                filename = filename.replace(ch, '')
            if not filename.endswith(".pdf"):
                filename += ".pdf"

            filepath = os.path.join(DATA_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(resp.content)
            print(f"\nSaved to: {filepath}")
            print(f"File size: {len(resp.content):,} bytes")
            return rename_pdf(filepath, persen)
        else:
            print("Direct download blocked by Cloudflare. Trying click download...")

            existing_files = set(os.listdir(DATA_DIR))

            for link in pdf_links:
                if (link.get_attribute("href") or "") == target_link:
                    driver.execute_script("arguments[0].click();", link)
                    print("Clicked download link. Waiting for download...")
                    break

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
                    print(f"\nDownloaded: {filepath}")
                    print(f"File size: {os.path.getsize(filepath):,} bytes")
                    return rename_pdf(filepath, persen)
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
        # Clean up residual temp files
        for f in os.listdir(DATA_DIR):
            if f.endswith('.crdownload') or f == 'downloads.htm':
                try:
                    os.remove(os.path.join(DATA_DIR, f))
                except:
                    pass
        driver.quit()
        print("Driver closed.")


if __name__ == "__main__":
    # Default to 5%, or pass 1 or 5 as argument
    persen = sys.argv[1] if len(sys.argv) > 1 else "5"
    if persen not in ("1", "5"):
        print(f"Usage: python {os.path.basename(__file__)} [1|5]")
        print(f"  1 = Download Pemegang Saham di atas 1%")
        print(f"  5 = Download Pemegang Saham di atas 5% (default)")
        sys.exit(1)

    result = download_pdf(persen)
    if result:
        print(f"\n{'='*60}")
        print(f"SUCCESS! Downloaded: {result}")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("FAILED to download the PDF.")
        print(f"{'='*60}")
