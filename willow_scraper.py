
import re
import requests
import logging
import datetime
import sys
import os
import cloudscraper

# --- Configuration ---
CRICHD_BASE_URL = "https://vf.crichd.tv"
WEB_URL = "https://vf.crichd.tv/web"
OUTPUT_M3U_FILE = "output.m3u"
EPG_URL = "https://github.com/epgshare01/share/raw/master/epg_ripper_ALL_SOURCES1.xml.gz"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
REQUESTS_TIMEOUT = 25

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
    stream=sys.stdout
)

# --- Session Initialization ---
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)
scraper.headers.update({'User-Agent': USER_AGENT})

# --- Main Functions ---
def get_page_content(url, referrer=None):
    """Fetches content for a given URL using the cloudscraper session."""
    logging.debug(f"Fetching URL: {url} with referrer: {referrer}")
    headers = {'User-Agent': USER_AGENT}
    if referrer:
        headers['Referer'] = referrer
    try:
        response = scraper.get(url, headers=headers, timeout=REQUESTS_TIMEOUT)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

def get_all_fids():
    """
    Step 1: Scrape all channel pages to collect FIDs.
    """
    logging.info("--- Step 1: Scraping all channel pages to collect FIDs ---")
    main_page_content = get_page_content(WEB_URL)
    if not main_page_content:
        logging.critical("Failed to fetch main page content. Exiting.")
        return []

    # CORRECTED REGEX for channel links
    channel_links = re.findall(r'href=["\'](https?://vf\.crichd\.tv/[^\"\']+-live-streaming)["\']', main_page_content)
    unique_links = sorted(list(set(channel_links)))
    logging.info(f"Found {len(unique_links)} unique channel links.")

    collected_fids = []
    for link in unique_links:
        logging.info(f"Processing channel page: {link}")
        channel_page_content = get_page_content(link, referrer=WEB_URL)
        if not channel_page_content:
            continue

        title_match = re.search(r'<title>(.*?)</title>', channel_page_content)
        raw_name = title_match.group(1).split('|')[0].strip() if title_match else "Unknown Channel"

        intermediary_matches = re.findall(r'src=\\"([^\"]+\.php)\\"', channel_page_content)
        if not intermediary_matches:
            logging.warning(f"No streamcrichd iframe found on {link}")
            continue

        for intermediary_path in intermediary_matches:
            # Ensure the path starts with //, which is the expected format
            if not intermediary_path.startswith('//'):
                 intermediary_path = f'//{intermediary_path}'
                 
            intermediary_url = f"https:{intermediary_path}"
            logging.info(f"Found intermediary URL: {intermediary_url}")

            intermediary_content = get_page_content(intermediary_url, referrer=link)
            if not intermediary_content:
                continue

            # CORRECTED REGEX for fid
            fid_match = re.search(r'fid\s*=\s*["\']([^\"\']+)["\']', intermediary_content)
            if fid_match:
                fid = fid_match.group(1)
                logging.info(f"SUCCESS: Found fid: '{fid}' for channel '{raw_name}'")
                collected_fids.append({'name': raw_name, 'fid': fid, 'referrer': intermediary_url})
            else:
                logging.warning(f"Could not find fid in {intermediary_url}")

    logging.info(f"--- Finished Step 1: Collected {len(collected_fids)} FIDs in total. ---")
    return collected_fids

def get_stream_from_fid(fid_info):
    """
    Step 2: Use the collected fid and referrer to get the final m3u8 stream URL.
    """
    fid = fid_info['fid']
    name = fid_info['name']
    final_referrer = fid_info['referrer']

    logging.info(f"--- Step 2: Extracting stream for fid: '{fid}' ({name}) ---")
    player_url = f"https://executeandship.com/premiumcr.php?player=desktop&live={fid}"
    player_page_content = get_page_content(player_url, referrer=final_referrer)

    if not player_page_content:
        logging.error(f"Failed to fetch final player page for fid: {fid}")
        return None

    # CORRECTED REGEX for stream array extraction
    stream_array_match = re.search(r"return \(\[(.*?)\]\.join", player_page_content, re.DOTALL)
    if not stream_array_match:
        logging.error(f"Could not find the stream URL array for fid: {fid}.")
        with open(f"debug_{fid}.html", "w") as f:
            f.write(player_page_content)
        logging.info(f"Saved problematic page content to debug_{fid}.html")
        return None

    char_list_str = stream_array_match.group(1)
    char_list = re.findall(r'"([^"]*)"', char_list_str)
    final_url = "".join(char_list).replace("\\/", "/")

    if "m3u8" in final_url:
        logging.info(f"SUCCESS: Extracted stream for '{name}'")
        return final_url
    else:
        logging.warning(f"Extracted URL for '{name}' may not be a valid m3u8 stream.")
        return None

# --- Main Execution ---
if __name__ == "__main__":
    logging.info("--- STARTING CRICHD SCRAPER (FINAL CORRECTED VERSION) ---")
    fids = get_all_fids()
    all_channels = []
    if fids:
        for fid_info in fids:
            stream_url = get_stream_from_fid(fid_info)
            if stream_url:
                all_channels.append((fid_info['name'], stream_url, fid_info['referrer'], "crichd.tv"))

    logging.info("--- SCRAPE COMPLETE ---")
    total_channels = len(all_channels)
    logging.info(f"Total channels successfully scraped: {total_channels}")

    if total_channels == 0:
        logging.warning("No channels were found. M3U will be generated but empty.")

    logging.info(f"Writing {total_channels} channels to {OUTPUT_M3U_FILE}")
    try:
        with open(OUTPUT_M3U_FILE, "w", encoding='utf-8') as f:
            f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
            f.write(f"# Generated by Gemini-Code-Assistant\n")
            update_time = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')
            f.write(f'# Last updated: {update_time}\n')
            f.write(f'# Total channels: {total_channels}\n\n')
            for name, stream, referrer, category in sorted(all_channels, key=lambda x: x[0].lower()):
                f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{category}",{name}\n')
                f.write(f'#EXTVLCOPT:http-referrer={referrer}\n')
                f.write(f"{stream}\n")
        logging.info("M3U file written successfully.")
    except Exception as e:
        logging.critical("Failed to write the M3U file.", exc_info=True)
        sys.exit(1)

    logging.info("--- SCRIPT EXECUTION FINISHED ---")
