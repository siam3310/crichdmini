<?php

// Allow only specific domains (VERY IMPORTANT)
$allowed_domains = [
    "dlhd.link"
];

if (!isset($_GET['url'])) {
    die("No URL provided.");
}

$url = $_GET['url'];

// Validate URL
$parsed = parse_url($url);
if (!$parsed || !in_array($parsed['host'], $allowed_domains)) {
    die("Domain not allowed.");
}

// cURL fetch
$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, false); // 🚫 Stop redirects
curl_setopt($ch, CURLOPT_USERAGENT, $_SERVER['HTTP_USER_AGENT']);
curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);

$response = curl_exec($ch);
curl_close($ch);

// Remove dangerous scripts
$response = preg_replace('#<script.*?>.*?</script>#is', '', $response);
$response = preg_replace('#on[a-z]+=".*?"#is', '', $response);
$response = preg_replace('#javascript:#is', '', $response);

// Remove iframe inside iframe
$response = preg_replace('#<iframe.*?>.*?</iframe>#is', '', $response);

// Block meta refresh redirect
$response = preg_replace('#<meta.*?http-equiv=["\']refresh["\'].*?>#is', '', $response);

// Inject CSP inside proxy output
header("Content-Security-Policy: default-src 'self' https: data:; script-src 'none'; object-src 'none'; frame-ancestors 'self';");

// Prevent caching
header("Cache-Control: no-store, no-cache, must-revalidate, max-age=0");
header("Pragma: no-cache");

echo $response;
