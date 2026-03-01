<?php

// This script acts as a proxy to fetch and decrypt a protected HLS stream.
// It handles adding necessary headers and decrypting AES-128 encrypted segments on the fly.

// --- Configuration ---
$m3u8_url = "https://chevy.adsfadfds.cfd/proxy/zeko/premium308/mono.m3u8";
$referer = "https://www.ksohls.ru/premiumtv/daddyhd.php?id=370";
$user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36";

// --- Helper function to fetch a URL with custom headers ---
function fetch_url($url, $referer, $user_agent) {
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_HTTPHEADER, [
        'Referer: ' . $referer,
        'User-Agent: ' . $user_agent
    ]);
    // Follow redirects, if any
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
    $output = curl_exec($ch);
    if (curl_errno($ch)) {
        // If there's a cURL error, return an empty string or handle it
        error_log("cURL Error: " . curl_error($ch));
        return '';
    }
    curl_close($ch);
    return $output;
}

// --- Main Logic ---
$type = isset($_GET['type']) ? $_GET['type'] : 'playlist';

if ($type == 'playlist') {
    // The player is requesting the main playlist.
    $playlist_content = fetch_url($m3u8_url, $referer, $user_agent);

    // Regex to find the KEY URI
    preg_match('/URI="([^"]+)"/', $playlist_content, $key_matches);
    if (isset($key_matches[1])) {
        $original_key_uri = $key_matches[1];
        // Replace the key URI to point back to this script
        $new_key_uri = 'daddy.php?type=key&uri=' . urlencode($original_key_uri);
        $playlist_content = str_replace($original_key_uri, $new_key_uri, $playlist_content);
    }

    // Rewrite segment URLs to point back to this script
    $lines = explode("\n", $playlist_content);
    $new_lines = [];
    foreach ($lines as $line) {
        if (substr(trim($line), 0, 1) != '#' && trim($line) != '') {
            // This is a segment URL
            $new_lines[] = 'daddy.php?type=segment&uri=' . urlencode(trim($line));
        } else {
            $new_lines[] = $line;
        }
    }
    $modified_playlist = implode("\n", $new_lines);

    // Serve the modified playlist to the player
    header('Content-Type: application/vnd.apple.mpegurl');
    echo $modified_playlist;

} elseif ($type == 'key') {
    // The player is requesting the decryption key.
    $key_uri = $_GET['uri'];
    $key_content = fetch_url($key_uri, $referer, $user_agent);
    header('Content-Type: application/octet-stream');
    echo $key_content;

} elseif ($type == 'segment') {
    // The player is requesting a video segment. We need to fetch it and decrypt it.

    // 1. First, we need the key and IV. Fetch the main playlist again to ensure they are current.
    $playlist_content = fetch_url($m3u8_url, $referer, $user_agent);
    preg_match('/URI="([^"]+)"/', $playlist_content, $key_matches);
    preg_match('/IV=0x([0-9a-fA-F]+)/', $playlist_content, $iv_matches);

    if (isset($key_matches[1]) && isset($iv_matches[1])) {
        $key_uri = $key_matches[1];
        $iv_hex = $iv_matches[1];
        $iv = hex2bin($iv_hex);

        // 2. Fetch the decryption key
        $key = fetch_url($key_uri, $referer, $user_agent);

        // 3. Fetch the encrypted segment data
        $segment_uri = $_GET['uri'];
        $encrypted_segment = fetch_url($segment_uri, $referer, $user_agent);

        // 4. Decrypt the segment using OpenSSL
        $decrypted_segment = openssl_decrypt($encrypted_segment, 'aes-128-cbc', $key, OPENSSL_RAW_DATA, $iv);

        // 5. Serve the decrypted segment to the player
        header('Content-Type: video/mp2t');
        echo $decrypted_segment;
    } else {
        http_response_code(500);
        echo "Could not find key or IV in the main playlist.";
    }
}
?>
