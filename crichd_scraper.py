
import re
import subprocess
import logging
import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

# --- Configuration ---
CRICHD_BASE_URL = "https://crichd.com.co"
CRICHD_GO_BASE_URL = "https://go.crichd.tv"
OUTPUT_M3U_FILE = "siamscrichd.m3u"
EPG_URL = "https://github.com/epgshare01/share/raw/master/epg_ripper_ALL_SOURCES1.xml.gz"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_command(command):
    logging.info(f"Running command: {command}")
    try:
        result = subprocess.run(command, capture_output=True, shell=True, check=True, timeout=20)
        return result.stdout.decode('utf-8', errors='ignore')
    except subprocess.TimeoutExpired:
        logging.error(f"Command timed out: {command}")
        return None
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e}\nStderr: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else ''}")
        return None

def clean_channel_name(name):
    name = re.sub(r'(\s*Live Stream(ing)?|\s*-\s*CricHD|\s*US\s*-|\s*-\s*Free|\s*Watch|\s*HD|\s*-\s*PSL T20 On|\s*Play\s*-\s*01)', '', name, flags=re.IGNORECASE)
    return " ".join(name.split())

def is_stream_working(stream_url, referrer):
    if not stream_url:
        return False
    logging.info(f"Checking stream: {stream_url}")
    command = f"curl -L -H 'Referer: {referrer}' --max-time 5 -s '{stream_url}' | head -n 1"
    output = run_command(command)
    if output and "#EXTM3U" in output:
        logging.info(f"Stream is working: {stream_url}")
        return True
    logging.warning(f"Stream is not working or not an M3U8 playlist: {stream_url}")
    return False

# --- gocrichd.tv scraper functions ---

def get_channel_links_go():
    logging.info(f"Fetching channel links from {CRICHD_GO_BASE_URL}/")
    main_page_content = run_command(f"curl -L {CRICHD_GO_BASE_URL}/")
    if not main_page_content:
        return []
    pattern = r'<div class="channels">\s*<a href="([^\"]+)"'
    channel_links = re.findall(pattern, main_page_content)
    logging.info(f"Found {len(channel_links)} channel links from {CRICHD_GO_BASE_URL}")
    return list(dict.fromkeys(channel_links))

def get_stream_link_go(channel_url):
    logging.info(f"Fetching stream link for go.crichd.tv: {channel_url}")
    channel_page_content = run_command(f"curl -L -H 'Referer: {CRICHD_GO_BASE_URL}' '{channel_url}'")
    if not channel_page_content: return None, None, None, None

    embeds_match = re.search(r"embeds\[0\]\s*=\s*'(.*?)';", channel_page_content)
    if not embeds_match:
        logging.warning(f"Could not find embeds[0] content for {channel_url}")
        return None, None, None, None
    
    iframe_html_with_escapes = embeds_match.group(1)
    iframe_html = iframe_html_with_escapes.replace('\\"', '"')

    src_match = re.search(r'src="(.*?)"', iframe_html)
    if not src_match:
        logging.warning(f"Could not find src in iframe html for {channel_url}")
        return None, None, None, None
    
    iframe_src_1 = src_match.group(1)

    if iframe_src_1.startswith("//"):
        iframe_src_1 = "https:" + iframe_src_1

    logging.info(f"Fetching first iframe: {iframe_src_1}")
    iframe_content_1 = run_command(f"curl -L -H 'Referer: {channel_url}' '{iframe_src_1}'")
    if not iframe_content_1: return None, None, None, None

    fid_match = re.search(r'fid="(.*?)"', iframe_content_1)
    if not fid_match:
        logging.warning(f"Could not find fid for {channel_url}")
        return None, None, None, None
    fid = fid_match.group(1)
    logging.info(f"Found fid: {fid}")

    iframe_src_2 = f"https://executeandship.com/premium.php?player=desktop&live={fid}"

    logging.info(f"Fetching second iframe: {iframe_src_2}")
    iframe_content_2 = run_command(f"curl -L -H 'Referer: {iframe_src_1}' '{iframe_src_2}'")
    if not iframe_content_2: return None, None, None, None

    stream_url_parts_match = re.search(r'return \(\[(.*?)\]\.join', iframe_content_2)
    if not stream_url_parts_match:
        logging.warning(f"Could not find stream URL parts for {channel_url}")
        return None, None, None, None

    char_array_str = stream_url_parts_match.group(1)
    char_list = [c.strip().strip('\"') for c in char_array_str.split(',')]
    stream_url = "".join(char_list).replace('\\/', '/')

    channel_name_match = re.search(r'<title>(.*?)</title>', channel_page_content)
    raw_name = channel_name_match.group(1).split("|")[0].strip() if channel_name_match else "Unknown Channel"
    channel_name = clean_channel_name(raw_name)

    return channel_name, stream_url, "https://executeandship.com/", "crichd2"

# --- crichd.com.co scraper functions ---

def get_channel_links_crichd():
    logging.info(f"Fetching channel links from {CRICHD_BASE_URL}")
    main_page_content = run_command(f"curl -L {CRICHD_BASE_URL}")
    if not main_page_content: return []
    pattern = r'<li class="has-sub"><a href="(https://crichd.com.co/channels/[^\"]+)"'
    channel_links = re.findall(pattern, main_page_content)
    logging.info(f"Found {len(channel_links)} channel links from {CRICHD_BASE_URL}")
    return channel_links

def get_stream_link_crichd(channel_url):
    logging.info(f"Fetching stream link for crichd.com.co: {channel_url}")
    channel_page_content = run_command(f"curl -L '{channel_url}'")
    if not channel_page_content: return None, None, None, None

    player_link_match = re.search(r'<a href=\"(https://dadocric.st/player(?:2)?\.php\?id=[^\"]+)\"', channel_page_content)
    if not player_link_match:
        player_link_match = re.search(r'<a href="(https://dadocric.st/player(?:2)?\.php\?id=[^\"]+)"', channel_page_content)
        if not player_link_match:
            logging.warning(f"Could not find dadocric player link in {channel_url}")
            return None, None, None, None
    
    player_link = player_link_match.group(1).replace('player.php', 'player2.php')

    player_page_content = run_command(f"curl -L '{player_link}'")
    if not player_page_content: return None, None, None, None

    embed_iframe_match = re.search(r'<iframe[^>]+src="(https://cdn.dadocric.st/embed.php\?id=[^\"]+)"', player_page_content)
    if not embed_iframe_match:
        logging.warning(f"Could not find cdn.dadocric.st iframe in {player_link}")
        return None, None, None, None
    
    embed_link = embed_iframe_match.group(1)

    embed_page_content = run_command(f"curl -L '{embed_link}'")
    if not embed_page_content: return None, None, None, None

    fid_match = re.search(r'fid="([^"]+)"', embed_page_content)
    v_con_match = re.search(r'v_con="([^"]+)"', embed_page_content)
    v_dt_match = re.search(r'v_dt="([^"]+)"', embed_page_content)
    
    if not (fid_match and v_con_match and v_dt_match):
        logging.warning(f"Could not find required variables in {embed_link}")
        return None, None, None, None
        
    fid = fid_match.group(1)
    v_con = v_con_match.group(1)
    v_dt = v_dt_match.group(1)

    atplay_url = f"https://player0003.com/atplay.php?v={fid}&hello={v_con}&expires={v_dt}"
    
    atplay_page_content = run_command(f"curl -L -H 'Referer: https://cdn.dadocric.st/' '{atplay_url}'")
    if not atplay_page_content: return None, None, None, None

    stream_url_match = re.search(r'return\(\[(.*?)\]\.join', atplay_page_content, re.DOTALL)
    if not stream_url_match:
        logging.warning(f"Could not find stream URL array in {atplay_url}")
        return None, None, None, None

    char_array_str = stream_url_match.group(1)
    char_list = re.findall(r'"(.*?)"', char_array_str)
    stream_url = "".join(char_list).replace('\\/', '/')

    if not stream_url:
        return None, None, None, None

    channel_name_match = re.search(r'<title>(.*?)</title>', channel_page_content)
    raw_name = channel_name_match.group(1).split(" Live Streaming")[0].strip() if channel_name_match else "Unknown Channel"
    channel_name = clean_channel_name(raw_name)

    return channel_name, stream_url, "https://player0003.com/", "crichd1"


# --- Main Execution ---

if __name__ == "__main__":
    all_channels = []
    
    links_go = get_channel_links_go()
    for link in links_go:
        result = get_stream_link_go(link)
        if result and all(result):
            all_channels.append(result)

    links_crichd = get_channel_links_crichd()
    for link in links_crichd:
        result = get_stream_link_crichd(link)
        if result and all(result):
            all_channels.append(result)

    working_channels = []
    for name, stream, referrer, category in all_channels:
        if is_stream_working(stream, referrer):
            working_channels.append((name, stream, referrer, category))

    unique_channels = []
    seen_names = set()
    for name, stream, referrer, category in working_channels:
        if name not in seen_names:
            unique_channels.append((name, stream, referrer, category))
            seen_names.add(name)

    total_channels = len(unique_channels)
    update_time = ""
    if ZoneInfo:
        try:
            dhaka_tz = ZoneInfo('Asia/Dhaka')
            update_time = datetime.datetime.now(dhaka_tz).strftime('%Y-%m-%d %I:%M:%S %p')
        except Exception:
            update_time = datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p') + " UTC"
    else: # Fallback for older python
        update_time = datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p') + " UTC"

    with open(OUTPUT_M3U_FILE, "w", encoding='utf-8') as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')
        f.write(f'# Made by Siam3310\n')
        f.write(f'# Last updated: {update_time} (Bangladesh/Dhaka)\n')
        f.write(f'# Total channels: {total_channels}\n\n')
        for name, stream, referrer, category in sorted(unique_channels):
            f.write(f'#EXTINF:-1 tvg-name="{name}" group-title="{category}",{name}\n')
            f.write(f"#EXTVLCOPT:http-referrer={referrer}\n")
            f.write(f"{stream}\n")
    
    logging.info(f"Scraping complete. Found {total_channels} unique, working channels.")
