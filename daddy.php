<?php

// --- Configuration ---
define('CHANNEL_KEY', 'premium603');
define('CHANNEL_SALT', 'a6fa2445e156106c');
define('FINGERPRINT', '1920x1080en-US');

// --- Proxy Logic ---
if (isset($_GET['resource'])) {

    // --- Authentication Functions ---
    function compute_pow_nonce($path, $timestamp) {
        $hmac_hash = hash_hmac('sha256', CHANNEL_KEY, CHANNEL_SALT);
        for ($nonce = 0; $nonce < 100000; $nonce++) {
            $message = $hmac_hash . CHANNEL_KEY . $path . $timestamp . $nonce;
            if (hexdec(substr(md5($message), 0, 4)) < 4096) return $nonce;
        }
        return 99999;
    }

    function generate_auth_token($path, $timestamp) {
        $message = CHANNEL_KEY . '|' . $path . '|' . $timestamp . '|' . FINGERPRINT;
        return substr(hash_hmac('sha256', $message, CHANNEL_SALT), 0, 16);
    }

    $resource_path = $_GET['resource'];
    $is_key_request = strpos($resource_path, 'key/') === 0;

    if ($is_key_request) {
        $full_url = 'https://chevy.soyspace.cyou/' . $resource_path;
        $auth_path = '/' . $resource_path;
    } else {
        $lookup_url = 'https://chevy.vovlacosa.sbs/server_lookup?channel_id=' . CHANNEL_KEY;
        $server_details_json = @file_get_contents($lookup_url, false, stream_context_create(["ssl"=>["verify_peer"=>false, "verify_peer_name"=>false]]));
        if ($server_details_json === FALSE) { http_response_code(503); exit("Error: Could not contact server lookup."); }
        $server_details = json_decode($server_details_json, true);
        $server_key = $server_details['server_key'];
        $full_url = "https://chevy.adsfadfds.cfd/proxy/{$server_key}/" . CHANNEL_KEY . "/{$resource_path}";
        $auth_path = $resource_path;
    }

    $timestamp = time();
    $nonce = compute_pow_nonce($auth_path, $timestamp);
    $auth_token = generate_auth_token($auth_path, $timestamp);

    // --- THE FIX: Use different headers for the key server vs the playlist server ---
    if ($is_key_request) {
        $headers = [
            'X-Key-Timestamp: ' . $timestamp,
            'X-Key-Nonce: ' . $nonce,
            'X-Key-Token: ' . $auth_token,
            'X-Fingerprint: ' . FINGERPRINT,
            'X-Country-Code: US'
        ];
    } else {
        $headers = [
            'X-Timestamp: ' . $timestamp,
            'X-Nonce: ' . $nonce,
            'X-Auth-Token: ' . $auth_token,
            'X-Fingerprint: ' . FINGERPRINT,
            'X-Country-Code: US'
        ];
    }

    $ch = curl_init($full_url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($ch, CURLOPT_USERAGENT, $_SERVER['HTTP_USER_AGENT'] ?? 'Mozilla/5.0');
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);

    $content = curl_exec($ch);
    if ($content === false) { http_response_code(502); exit("cURL Error: " . curl_error($ch)); }
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $content_type = curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
    curl_close($ch);

    if ($http_code != 200) { http_response_code($http_code); exit("Upstream error: {$http_code}"); }

    if (pathinfo($resource_path, PATHINFO_EXTENSION) === 'css') {
        $content = preg_replace_callback(
            '/(#EXT-X-KEY:.*?URI=")([^"]+)(")/m',
            fn($m) => $m[1] . 'daddy.php?resource=' . ltrim(parse_url($m[2], PHP_URL_PATH), '/') . $m[3],
            $content
        );
        $content_type = 'application/vnd.apple.mpegurl';
    }

    header('Content-Type: ' . $content_type);
    echo $content;
    exit;
}

// --- HTML Player Page ---
?>
<!DOCTYPE html>
<html>
<head>
    <title>Daddy Player</title>
    <meta charset="utf-8">
    <style>body,html{margin:0;padding:0;height:100%;overflow:hidden;background-color:#000}#p{width:100%;height:100%}</style>
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.8/dist/hls.min.js"></script>
</head>
<body>
    <video id="p" controls></video>
    <script>
        const v=document.getElementById('p'), u='daddy.php?resource=mono.css';
        if(Hls.isSupported()){const h=new Hls();h.loadSource(u);h.attachMedia(v);}
        else if(v.canPlayType('application/vnd.apple.mpegurl')){v.src=u;}
    </script>
</body>
</html>
