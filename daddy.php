<?php

// Channel constants
define('CHANNEL_KEY', 'premium603');
define('CHANNEL_SALT', 'a6fa2445e156106c');
define('FINGERPRINT', '1920x1080en-US'); // Hardcoded fingerprint
define('BASE_URL', 'https://chevy.vovlacosa.sbs/proxy/top1/cdn/' . CHANNEL_KEY . '/');

// --- Authentication Logic (ported from previous analysis) ---

/**
 * Computes the Proof-of-Work nonce required by the server.
 * The logic is based on the deobfuscated JavaScript.
 */
function compute_pow_nonce($path, $timestamp) {
    $hmac_hash = hash_hmac('sha256', CHANNEL_KEY, CHANNEL_SALT);
    for ($nonce = 0; $nonce < 100000; $nonce++) {
        $message = "{$hmac_hash}" . CHANNEL_KEY . "{$path}{$timestamp}{$nonce}";
        $md5_hash = md5($message);
        // The server expects the first 4 hex digits of the hash to be less than 4096 (0x1000)
        if (hexdec(substr($md5_hash, 0, 4)) < 4096) {
            return $nonce;
        }
    }
    return 99999; // Fallback nonce
}

/**
 * Generates the X-Auth-Token required by the server.
 * The logic is based on the deobfuscated JavaScript.
 */
function generate_auth_token($path, $timestamp) {
    $message = CHANNEL_KEY . "|{$path}|{$timestamp}|" . FINGERPRINT;
    $hash = hash_hmac('sha256', $message, CHANNEL_SALT);
    return substr($hash, 0, 16); // The token is the first 16 chars of the hash
}


// --- Proxy Logic ---

if (isset($_GET['resource'])) {
    $resource = $_GET['resource'];
    $auth_path = $resource; // The path used for authentication is the resource file name

    $timestamp = time();
    $nonce = compute_pow_nonce($auth_path, $timestamp);
    $auth_token = generate_auth_token($auth_path, $timestamp);

    // Prepare the authentication headers
    $headers = [
        'X-Timestamp: ' . $timestamp,
        'X-Nonce: ' . $nonce,
        'X-Auth-Token: ' . $auth_token,
        'X-Fingerprint: ' . FINGERPRINT,
        'X-Country-Code: US' // A country code is also required
    ];

    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, BASE_URL . $resource);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
    
    // Forward the user's User-Agent for good measure
    if(isset($_SERVER['HTTP_USER_AGENT'])) {
        curl_setopt($ch, CURLOPT_USERAGENT, $_SERVER['HTTP_USER_AGENT']);
    }

    $content = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $content_type = curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
    curl_close($ch);

    // If the upstream server returns an error, pass it along
    if ($http_code != 200) {
        http_response_code($http_code > 0 ? $http_code : 500);
        echo "Upstream error: {$http_code}\n";
        echo $content;
        exit;
    }

    // For HLS playlists, all segment/sub-playlist URLs must be rewritten 
    // to point back to this proxy script.
    if (pathinfo($resource, PATHINFO_EXTENSION) === 'm3u8') {
        $content = preg_replace('/^(.*\\.ts)$/m', 'index.php?resource=$1', $content);
        $content = preg_replace('/^(.*\\.m3u8)$/m', 'index.php?resource=$1', $content);
    }

    // Pass back the correct Content-Type and the actual content
    header('Content-Type: ' . $content_type);
    echo $content;
    exit;
}

// --- HTML Player Page (served by default) ---
?>
<!DOCTYPE html>
<html>
<head>
    <title>PHP Video Stream Proxy</title>
    <link href="https://vjs.zencdn.net/7.15.4/video-js.css" rel="stylesheet" />
    <style>
        body { font-family: sans-serif; }
        #stream-info {
            margin-top: 20px;
            padding: 15px;
            border: 1px solid #ccc;
            background-color: #f5f5f5;
            word-wrap: break-word;
        }
    </style>
</head>
<body>

<h1>Video Stream via PHP Proxy</h1>
<video-js id="my-video" class="video-js" controls preload="auto" width="960" height="540" data-setup="{}">
    <!-- The source points to this script to fetch the main playlist -->
    <source src="index.php?resource=mono.m3u8" type="application/x-mpegURL">
</video-js>

<div id="stream-info">
    <strong>Live Fetched URL:</strong>
    <span id="live-url">Waiting for stream to start...</span>
</div>

<script src="https://vjs.zencdn.net/7.15.4/video.js"></script>

<script>
    // Expose the PHP base URL to JavaScript
    const BASE_URL = '<?php echo BASE_URL; ?>';

    (function() {
        // Get the video.js player instance
        const player = videojs('my-video');
        const liveUrlElement = document.getElementById('live-url');

        // This function runs just before any segment is requested
        player.vhs.xhr.beforeRequest = function(options) {
            
            // The URI will be like "index.php?resource=..."
            const requestUri = options.uri;
            
            // Extract the resource name from the URI
            const urlParams = new URLSearchParams(requestUri.split('?')[1]);
            const resource = urlParams.get('resource');

            if (resource) {
                // Construct the full upstream URL and display it
                const fullUrl = BASE_URL + resource;
                liveUrlElement.textContent = fullUrl;
            }

            // Return the original options to allow the request to proceed
            return options;
        };
    })();
</script>

</body>
</html>
