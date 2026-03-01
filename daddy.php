<?php

// --- Constants and Configuration ---
define('CHANNEL_KEY', 'premium603');
define('CHANNEL_SALT', 'a6fa2445e156106c');
define('FINGERPRINT', '1920x1080en-US'); // A hardcoded fingerprint is sufficient

// --- Authentication Logic (Ported from deobfuscated.js) ---

function compute_pow_nonce($path, $timestamp) {
    $hmac_hash = hash_hmac('sha256', CHANNEL_KEY, CHANNEL_SALT);
    for ($nonce = 0; $nonce < 100000; $nonce++) {
        $message = $hmac_hash . CHANNEL_KEY . $path . $timestamp . $nonce;
        $md5_hash = md5($message);
        if (hexdec(substr($md5_hash, 0, 4)) < 4096) {
            return $nonce;
        }
    }
    return 99999; // Fallback
}

function generate_auth_token($path, $timestamp) {
    $message = CHANNEL_KEY . '|' . $path . '|' . $timestamp . '|' . FINGERPRINT;
    $hash = hash_hmac('sha256', $message, CHANNEL_SALT);
    return substr($hash, 0, 16);
}

// --- Main Logic ---

// Get the target resource from the URL, default to mono.css
$resource = isset($_GET['resource']) ? $_GET['resource'] : 'mono.css';
$auth_path = $resource;

// Fetch the dynamic server key
$lookup_url = 'https://chevy.vovlacosa.sbs/server_lookup?channel_id=' . CHANNEL_KEY;
$server_details_json = file_get_contents($lookup_url);
$server_details = json_decode($server_details_json, true);
$server_key = isset($server_details['server_key']) ? $server_details['server_key'] : '[SERVER_KEY_NOT_FOUND]';

// Construct the full URL to be fetched
$full_url = "https://chevy.adsfadfds.cfd/proxy/{$server_key}/" . CHANNEL_KEY . "/{$resource}";

// Generate the required authentication values
$timestamp = time();
$nonce = compute_pow_nonce($auth_path, $timestamp);
$auth_token = generate_auth_token($auth_path, $timestamp);

// Prepare the headers for the cURL command
$headers = [
    'X-Timestamp' => $timestamp,
    'X-Nonce' => $nonce,
    'X-Auth-Token' => $auth_token,
    'X-Fingerprint' => FINGERPRINT,
    'X-Country-Code' => 'US'
];

// Build the cURL command string
$curl_command = "curl -v -L ";
foreach ($headers as $key => $value) {
    $curl_command .= "-H '" . htmlspecialchars($key, ENT_QUOTES) . ": " . htmlspecialchars($value, ENT_QUOTES) . "' ";
}
$curl_command .= "'" . htmlspecialchars($full_url, ENT_QUOTES) . "'";

// --- HTML Page to display the command ---
?>
<!DOCTYPE html>
<html>
<head>
    <title>cURL Command Generator</title>
    <style>
        body { font-family: sans-serif; background-color: #f4f4f4; padding: 20px; }
        .container { background-color: #fff; padding: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        .code-block {
            background-color: #272822;
            color: #f8f8f2;
            padding: 15px;
            border-radius: 5px;
            white-space: pre-wrap;
            word-wrap: break-word;
            margin-top: 10px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>cURL Command for Verification</h1>
        <p>This script has generated the precise headers required to authenticate with the stream server. Copy the command below and run it in your terminal to test the connection.</p>
        <p><strong>Target Resource:</strong> <?php echo htmlspecialchars($resource); ?></p>
        <div class="code-block"><?php echo $curl_command; ?></div>
    </div>
</body>
</html>
