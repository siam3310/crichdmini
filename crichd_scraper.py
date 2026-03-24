
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
        result = subprocess.run(command, capture_output=True, shell=True, check=True)
        return result.stdout.decode('utf-8', errors='ignore')
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {e}\nStderr: {e.stderr.decode('utf-8', errors='ignore') if e.stderr else ''}")
        return None

def clean_channel_name(name):
    name = re.sub(r'(\s*Live Stream(ing)?|\s*-\s*CricHD|\s*US\s*-|\s*-\s*Free|\s*Watch|\s*HD|\s*-\s*PSL T20 On|\s*Play\s*-\s*01)', '', name, flags=re.IGNORECASE)
    return " ".join(name.split())

# --- gocrichd.tv scraper functions ---

def get_channel_links_go():
    logging.info(f"Fetching channel links from {CRICHD_GO_BASE_URL}/")
    main_page_content = run_command(f"curl -L {CRICHD_GO_BASE_URL}/")
    if not main_page_content:
        return []
    pattern = r'<div class="channels">\s*<a href="([^"]+)"'
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
    iframe_html = embeds_match.group(1)

    src_match = re.search(r'src="(.*?)"', iframe_html)
    if not src_match:
        src_match = re.search(r'src=\\"(.*?)\\"' , iframe_html) # Fallback
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

    iframe_src_2 = f"https://profamouslife.com/premium.php?player=desktop&live={fid}"

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

    return channel_name, stream_url, "https://profamouslife.com/", "crichd2"

# --- crichd.com.co scraper functions ---

def get_channel_links_crichd():
    logging.info(f"Fetching channel links from {CRICHD_BASE_URL}")
    main_page_content = run_command(f"curl -L {CRICHD_BASE_URL}")
    if not main_page_content: return []
    pattern = r'<li class="has-sub"><a href="(' + re.escape(CRICHD_BASE_URL) + r'/channels/[^\"]+)"'
    channel_links = re.findall(pattern, main_page_content)
    logging.info(f"Found {len(channel_links)} channel links from {CRICHD_BASE_URL}")
    return channel_links

def get_stream_link_crichd(channel_url):
    logging.info(f"Fetching stream link for crichd.com.co: {channel_url}")
    channel_page_content = run_command(f"curl -L '{channel_url}'")
    if not channel_page_content: return None, None, None, None

    player_link_match = re.search(r"<a[^>]+href=['\"](https://(?:player\.)?dadocric\.st/player\.php\?id=[^\'\"]+)['\"]", channel_page_content)
    if not player_link_match: return None, None, None, None
    player_id = player_link_match.group(1).split("id=")[1]
    playerado_url = f"https://playerado.top/embed2.php?id={player_id}"
    
    embed_page_content = run_command(f"curl -L '{playerado_url}'")
    if not embed_page_content: return None, None, None, None

    fid_match = re.search(r'fid\s*=\s*\"([^\"]+)\"', embed_page_content)
    v_con_match = re.search(r'v_con\s*=\s*\"([^\"]+)\"', embed_page_content)
    v_dt_match = re.search(r'v_dt\s*=\s*\"([^\"]+)\"', embed_page_content)
    if not (fid_match and v_con_match and v_dt_match): return None, None, None, None
    fid, v_con, v_dt = fid_match.group(1), v_con_match.group(1), v_dt_match.group(1)

    atplay_url = f"https://player0003.com/atplay.php?v={fid}&hello={v_con}&expires={v_dt}"
    atplay_page_content = run_command(f"curl -iL --user-agent \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36\" --referer \"https://playerado.top/\" '{atplay_url}'")
    if not atplay_page_content: return None, None, None, None

    func_name_match = re.search(r'player\.load\({source: (\w+)\(\),', atplay_page_content)
    if not func_name_match: return None, None, None, None
    func_name = func_name_match.group(1)

    func_def_match = re.search(r'function\s+' + func_name + r'\s*\(\)\s*{(.*?)}', atplay_page_content, re.DOTALL)
    if not func_def_match: return None, None, None, None
    func_body = func_def_match.group(1)

    base_url_var_match = re.search(r'var url = (\w+);', func_body)
    md5_var_match = re.search(r'url \+= "\?md5="\s*\+\s*(\w+);', func_body)
    expires_var_match = re.search(r'url \+= "&expires="\s*\+\s*(\w+);', func_body)
    s_var_match = re.search(r'url \+= "&s="\s*\+\s*(\w+);', func_body)
    if not (base_url_var_match and md5_var_match and expires_var_match and s_var_match): return None, None, None, None

    base_url_var, md5_var, expires_var, s_var = base_url_var_match.group(1), md5_var_match.group(1), expires_var_match.group(1), s_var_match.group(1)

    md5_val_match = re.search(r'var ' + md5_var + r'\s*=\s*\"(.*?)\"', atplay_page_content)
    expires_val_match = re.search(r'var ' + expires_var + r'\s*=\s*\"(.*?)\"', atplay_page_content)
    s_val_match = re.search(r'var ' + s_var + r'\s*=\s*\"(.*?)\"', atplay_page_content)
    if not (md5_val_match and expires_val_match and s_val_match): return None, None, None, None
    md5, expires, s_val = md5_val_match.group(1), expires_val_match.group(1), s_val_match.group(1)

    base_url_constructor_match = re.search(r'var ' + base_url_var + r'\s*=\s*(.*?);', atplay_page_content)
    if not base_url_constructor_match: return None, None, None, None
    constructor_string = base_url_constructor_match.group(1)
    real_base_url_var = constructor_string.split('+')[0].strip()
    
    real_base_url_match = re.search(r"var " + real_base_url_var + r" = (.*?);", atplay_page_content)
    if not real_base_url_match: return None, None, None, None
    base_url_str_with_plus = real_base_url_match.group(1)
    js_string_parts = re.findall(r"'(.*?)'", base_url_str_with_plus)
    base_url = "".join(js_string_parts)
    
    stream_path = f"/hls/{fid}.m3u8"
    final_stream_link = f"{base_url}{stream_path}?md5={md5}&expires={expires}&ch={fid}&s={s_val}"
    
    channel_name_match = re.search(r'<title>(.*?)</title>', channel_page_content)
    raw_name = channel_name_match.group(1).split(" Live Streaming")[0].strip() if channel_name_match else "Unknown Channel"
    channel_name = clean_channel_name(raw_name)

    return channel_name, final_stream_link, "https://player0003.com/", "crichd1"

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

    unique_channels = []
    seen_names = set()
    for name, stream, referrer, category in all_channels:
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
    
    logging.info(f"Scraping complete. Found {total_channels} unique channels.")
