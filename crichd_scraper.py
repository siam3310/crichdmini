
import requests
import re
import logging
import sys

# --- Configuration ---
INITIAL_URL = "https://streamcrichd.com/update/willowcricket.php"
# Per your instruction, this referrer will be used for ALL requests.
STRICT_REFERRER = "https://streamcrichd.com/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
REQUESTS_TIMEOUT = 15

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

def get_page_content(url, referrer=None):
    """Fetches content for a given URL using the requests library."""
    logging.info(f"Fetching URL: {url}")
    headers = {
        'User-Agent': USER_AGENT,
        'Referer': referrer
    }
    try:
        response = requests.get(url, headers=headers, timeout=REQUESTS_TIMEOUT)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def extract_willow_stream():
    """
    Follows the chain of requests and script executions to find the final
    HLS stream URL for the Willow Cricket channel.
    """
    # Step 1: Get the initial page
    logging.info("--- Step 1: Fetching initial page ---")
    initial_content = get_page_content(INITIAL_URL, referrer=STRICT_REFERRER)
    if not initial_content:
        logging.error("Failed to fetch initial page. Aborting.")
        return None

    # Step 2: Find and fetch the premium.js script
    logging.info("--- Step 2: Fetching premium.js script ---")
    premium_js_match = re.search(r'src="(//executeandship.com/premium.js)"', initial_content)
    if not premium_js_match:
        logging.error("Could not find 'premium.js' script in the initial page. Aborting.")
        return None

    premium_js_url = "https:" + premium_js_match.group(1)
    premium_js_content = get_page_content(premium_js_url, referrer=STRICT_REFERRER)
    if not premium_js_content:
        logging.error("Failed to fetch premium.js content. Aborting.")
        return None

    # Step 3: Extract the iframe URL from the premium.js content
    logging.info("--- Step 3: Extracting iframe URL ---")
    fid_match = re.search(r'fid="([^"]+)"', initial_content)
    if not fid_match:
        logging.error("Could not find 'fid' in the initial page. Aborting.")
        return None
    fid = fid_match.group(1)
    iframe_url = f"https://executeandship.com/premiumcr.php?player=desktop&live={fid}"

    # Step 4: Fetch the iframe content (the player page)
    logging.info("--- Step 4: Fetching player iframe page ---")
    player_page_content = get_page_content(iframe_url, referrer=STRICT_REFERRER)
    if not player_page_content:
        logging.error("Failed to fetch player page content. Aborting.")
        return None

    # Step 5: Extract the obfuscated stream URL
    logging.info("--- Step 5: Extracting final stream URL ---")
    stream_array_match = re.search(r'return \(\[(.*?)\]\.join', player_page_content, re.DOTALL)
    if not stream_array_match:
        logging.error("Could not find the stream URL array in the player page. Aborting.")
        return None

    char_list_str = stream_array_match.group(1)
    # Use regex to reliably extract all characters from the JavaScript array
    char_list = re.findall(r'"([^"]*)"', char_list_str)
    
    # Join the characters to form the URL
    final_url = "".join(char_list)
    # The result contains escaped slashes (\/), so we must replace them
    final_url = final_url.replace("\\/", "/")

    return final_url


if __name__ == "__main__":
    logging.info("--- STARTING WILLOW CRICKET STREAM EXTRACTOR ---")
    stream_url = extract_willow_stream()

    if stream_url:
        logging.info("--- EXTRACTION SUCCESSFUL ---")
        print(f"\nFinal Stream URL:\n{stream_url}\n")
    else:
        logging.error("--- EXTRACTION FAILED ---")
        sys.exit(1)
