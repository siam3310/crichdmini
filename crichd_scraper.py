
import re
import subprocess
import logging
import datetime
import sys

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

# --- Configuration ---
CRICHD_GO_BASE_URL = "https://go.crichd.tv"
OUTPUT_M3U_FILE = "siamscrichd.m3u"
EPG_URL = "https://github.com/epgshare01/share/raw/master/epg_ripper_ALL_SOURCES1.xml.gz"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

# --- Enhanced Logging Setup ---
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
    stream=sys.stdout
)

def run_command(command):
    logging.debug(f"Executing command: {command}")
    try:
        result = subprocess.run(
            command, 
            capture_output=True, 
            shell=True, 
            check=True, 
            timeout=60, 
            text=True, 
            encoding='utf-8', 
            errors='ignore'
        )
        if result.stderr:
            logging.info(f"Command STDERR: {result.stderr}")
        return result.stdout
    except subprocess.TimeoutExpired:
        logging.error(f"Command timed out: {command}")
        return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed with exit code {e.returncode}: {command}")
        if e.stdout:
            logging.error(f"Failed Command STDOUT: {e.stdout}")
        if e.stderr:
            logging.error(f"Failed Command STDERR: {e.stderr}")
        return None

# --- go.crichd.tv scraper functions ---

def get_channel_links_go():
    logging.info(f"Attempting to fetch main page: {CRICHD_GO_BASE_URL}/")
    main_page_content = run_command(f"curl -L -A '{USER_AGENT}' '{CRICHD_GO_BASE_URL}/'")
    if not main_page_content:
        logging.critical("Failed to fetch main page content.")
        return []
    
    pattern = r'href="(https://go\.crichd\.tv/[^"]*?live-streaming[^"]*?)"'
    channel_links = re.findall(pattern, main_page_content)
    
    unique_links = sorted(list(set([link.strip() for link in channel_links])))
    logging.info(f"Found {len(unique_links)} unique channel links.")
    logging.debug(f"Discovered links: {unique_links}")
    return unique_links

def get_stream_link_go(channel_url):
    logging.info(f"Processing channel URL: {channel_url}")

    channel_page_content = run_command(f"curl -L -A '{USER_AGENT}' -H 'Referer: {CRICHD_GO_BASE_URL}/' '{channel_url}'")
    if not channel_page_content:
        return None, None, None, None

    embeds_match = re.search(r"embeds\[0\]\s*=\s*'(.*?)';", channel_page_content)
    if not embeds_match:
        logging.warning("embeds[0] not found, falling back to embeds[1].")
        embeds_match = re.search(r"embeds\[1\]\s*=\s*'(.*?)';", channel_page_content)
        if not embeds_match:
            logging.error(f"Could not find any embeds content on page: {channel_url}")
            return None, None, None, None
            
    iframe_html = embeds_match.group(1).replace('\\"', '"')
    src_match = re.search(r'src=["\'](.*?)["\']', iframe_html)
    if not src_match:
        logging.error(f"Could not extract iframe 'src' from embeds content: {iframe_html}")
        return None, None, None, None
    
    iframe_src_1 = src_match.group(1).strip()
    if iframe_src_1.startswith("//"):
        iframe_src_1 = "https:" + iframe_src_1
    
    logging.info(f"Fetching first iframe from: {iframe_src_1}")
    iframe_content_1 = run_command(f"curl -L -A '{USER_AGENT}' -H 'Referer: {channel_url}' '{iframe_src_1}'")
    if not iframe_content_1: return None, None, None, None

    fid_match = re.search(r'fid="([^"]+)"', iframe_content_1)
    if not fid_match:
        logging.error(f"Could not find 'fid' in first iframe: {iframe_src_1}")
        return None, None, None, None
        
    fid = fid_match.group(1)
    logging.info(f"Successfully extracted fid: {fid}")

    iframe_src_2 = f"https://executeandship.com/premium.php?player=desktop&live={fid}"
    logging.info(f"Fetching second iframe from: {iframe_src_2}")
    
    iframe_content_2 = run_command(f"curl -L -A '{USER_AGENT}' -H 'Referer: {iframe_src_1}' '{iframe_src_2}'")
    if not iframe_content_2: return None, None, None, None

    stream_url = ''
    join_match = re.search(r"return\s*\(\s*\[(.*?)\]\.join", iframe_content_2, re.DOTALL)
    if join_match:
        logging.info("Found stream using pattern #1 ([...].join)")
        char_array_str = join_match.group(1)
        logging.debug(f"Found character array string: {char_array_str}")
        char_list = re.findall(r"['\"](.*?)['\"]", char_array_str)
        stream_url = "".join(char_list).replace('\\/', '/')
        logging.info(f"Reconstructed stream URL: {stream_url}")

    if not stream_url:
        eval_match = re.search(r"eval\(function\(p,a,c,k,e,d\).*?(https?://[^\s\'\"]+\.m3u8[^\s\'\"]*)", iframe_content_2, re.DOTALL)
        if eval_match:
            logging.info("Found stream using pattern #2 (eval)")
            stream_url = eval_match.group(1)

    if not stream_url:
        source_match = re.search(r'source:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', iframe_content_2)
        if source_match:
            logging.info("Found stream using pattern #3 (source: ...)")
            stream_url = source_match.group(1)

    if not stream_url or '.m3u8' not in stream_url:
        logging.error(f"All patterns failed for: {channel_url}")
        logging.debug(f"Final iframe content for failed URL:\n{iframe_content_2}")
        return None, None, None, None

    channel_name_match = re.search(r'<title>(.*?)</title>', channel_page_content)
    raw_name = channel_name_match.group(1).split("|")[0].strip() if channel_name_match else "Unknown Channel"
    logging.info(f"Successfully found stream for channel: '{raw_name}'")
    
    return raw_name, stream_url, "https://executeandship.com/", "go.crichd.tv"


# --- Main Execution ---

if __name__ == "__main__":
    all_channels = []
    
    logging.info("--- STARTING GO.CRICHD.TV SCRAPE ---")
    links_go = get_channel_links_go()
    if links_go:
        for link in links_go:
            try:
                result = get_stream_link_go(link)
                if result and all(result):
                    all_channels.append(result)
            except Exception as e:
                logging.critical(f"A critical error occurred while processing {link}", exc_info=True)

    logging.info("--- GO.CRICHD.TV SCRAPE COMPLETE ---")
    total_channels = len(all_channels)
    logging.info(f"Total channels found: {total_channels}")

    update_time = ""
    try:
        if ZoneInfo:
            dhaka_tz = ZoneInfo('Asia/Dhaka')
            update_time = datetime.datetime.now(dhaka_tz).strftime('%Y-%m-%d %I:%M:%S %p')
        else:
            utc_now = datetime.datetime.utcnow()
            dhaka_now = utc_now + datetime.timedelta(hours=6)
            update_time = dhaka_now.strftime('%Y-%m-%d %I:%M:%S %p')
    except Exception as e:
        logging.warning(f"Could not set timezone. Falling back to UTC. Error: {e}")
        update_time = datetime.datetime.utcnow().strftime('%Y-%m-%d %I:%M:%S %p') + " UTC"

    logging.info(f"Writing {total_channels} channels to {OUTPUT_M3U_FILE}")
    try:
        with open(OUTPUT_M3U_FILE, "w", encoding='utf-8') as f:
            f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
            # Corrected the syntax error in the line below
            f.write(f"# Generated by Siam's Advanced Scraper\n")
            f.write(f'# Last updated: {update_time} (Asia/Dhaka)\n')
            f.write(f'# Total channels: {total_channels}\n\n')
            for name, stream, referrer, category in sorted(all_channels, key=lambda x: (x[3].lower(), x[0].lower())):
                f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{category}",{name}\n')
                f.write(f'#EXTVLCOPT:http-referrer={referrer}\n')
                f.write(f"{stream}\n")
        logging.info("M3U file written successfully.")
    except Exception as e:
        logging.critical("Failed to write the M3U file.", exc_info=True)

    logging.info("--- VALIDATING FINAL M3U FILE ---")
    try:
        with open(OUTPUT_M3U_FILE, "r", encoding='utf-8') as f:
            final_content = f.read()
            logging.info(f"Successfully read back M3U file. Size: {len(final_content)} bytes.")
            print("\n--- FINAL M3U FILE CONTENT ---")
            print(final_content)
            print("--- END OF FILE CONTENT ---\n")
    except Exception as e:
        logging.error("Could not read back the final M3U file for validation.", exc_info=True)
    
    logging.info("--- SCRIPT EXECUTION FINISHED ---")
