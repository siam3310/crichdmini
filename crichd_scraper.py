
import cloudscraper
import re
import logging
import sys
import requests # For exception handling

# --- Configuration ---
INITIAL_URL = "https://streamcrichd.com/update/willowcricket.php"
STRICT_REFERRER = "https://streamcrichd.com/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
REQUESTS_TIMEOUT = 20 # Increased timeout for potential challenges

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

def extract_willow_stream():
    """
    Uses cloudscraper to bypass Cloudflare and mimic a browser session,
    handling cookies and headers to extract the stream URL.
    """
    logging.info("--- Creating a new cloudscraper session ---")
    
    # Use cloudscraper to create a session object that can bypass Cloudflare
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    # The default headers in cloudscraper are good, but we must set the correct Referer.
    scraper.headers.update({
        'User-Agent': USER_AGENT,
        'Referer': STRICT_REFERRER
    })

    try:
        logging.info(f"--- Step 1: Fetching initial page: {INITIAL_URL} ---")
        initial_response = scraper.get(INITIAL_URL, timeout=REQUESTS_TIMEOUT)
        initial_response.raise_for_status()
        initial_content = initial_response.text

        logging.info("--- Step 2: Fetching premium.js script ---")
        premium_js_match = re.search(r'src=(["\'])//executeandship.com/premium.js\1', initial_content)
        if not premium_js_match:
            logging.error("Could not find 'premium.js' script. Aborting.")
            return None

        premium_js_url = "https:" + "//executeandship.com/premium.js"
        # This request 'warms up' the session for the target domain
        scraper.get(premium_js_url, timeout=REQUESTS_TIMEOUT).raise_for_status()
        logging.info("--- Session 'warmed up' for executeandship.com ---")

        logging.info("--- Step 3: Extracting iframe URL ---")
        fid_match = re.search(r'fid=(["\'])([^"\']+)\1', initial_content)
        if not fid_match:
            logging.error("Could not find 'fid' in the initial page. Aborting.")
            return None

        fid = fid_match.group(2)
        iframe_url = f"https://executeandship.com/premiumcr.php?player=desktop&live={fid}"

        logging.info(f"--- Step 4: Fetching player iframe page: {iframe_url} ---")
        # This is the crucial request that was previously failing
        player_page_response = scraper.get(iframe_url, timeout=REQUESTS_TIMEOUT)
        player_page_response.raise_for_status()
        player_page_content = player_page_response.text
        logging.info("--- Successfully fetched player page content ---")

        logging.info("--- Step 5: Extracting final stream URL ---")
        stream_array_match = re.search(r"return \(\[(.*?)\]\.join", player_page_content, re.DOTALL)
        if not stream_array_match:
            logging.error("Could not find the stream URL array. Aborting.")
            return None

        char_list_str = stream_array_match.group(1)
        char_list = re.findall(r'"([^"]*)"', char_list_str)
        final_url = "".join(char_list).replace("\\/", "/")

        return final_url

    # Catching the base exception is sufficient as cloudscraper's exceptions inherit from it.
    except requests.exceptions.RequestException as e:
        logging.error(f"A network error or Cloudflare challenge failed: {e}")
        return None

if __name__ == "__main__":
    logging.info("--- STARTING WILLOW CRICKET STREAM EXTRACTOR (Cloudscraper) ---")
    stream_url = extract_willow_stream()

    if stream_url:
        logging.info("--- EXTRACTION SUCCESSFUL ---")
        print(f"\nFinal Stream URL:\n{stream_url}\n")
        # Let's create the M3U file as requested previously
        try:
            with open("siamscrichd.m3u", "w") as f:
                f.write("#EXTM3U\n")
                f.write("#EXTINF:-1,WILLOW HD\n")
                f.write(stream_url + "\n")
            logging.info("--- Successfully created siamscrichd.m3u file ---")
        except IOError as e:
            logging.error(f"Failed to write M3U file: {e}")

    else:
        logging.error("--- EXTRACTION FAILED ---")
        sys.exit(1)
