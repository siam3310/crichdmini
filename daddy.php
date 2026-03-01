<?php
error_reporting(0);

function b64_to_hex($b64) {
    return bin2hex($b64);
}

function hex_to_b64($hex) {
    if (!preg_match('/^[0-9a-fA-F]+$/', $hex)) return false;
    if (strlen($hex) % 2 !== 0) return false;
    $bin = hex2bin($hex);
    if ($bin === false) return false;
    return $bin;
}

if (!isset($_GET["url"])) {
    http_response_code(400);
    die("Missing url");
}

$raw = trim($_GET["url"]);
$url = "";

if (preg_match('/^[0-9a-fA-F]+$/', $raw) && strlen($raw) > 20) {
    $b64 = hex_to_b64($raw);
    if ($b64 !== false) {
        $decoded = base64_decode($b64, true);
        if ($decoded !== false && filter_var($decoded, FILTER_VALIDATE_URL)) {
            $url = $decoded;
        }
    }
}

if ($url === "") {
    $url = urldecode($raw);
}

if (!filter_var($url, FILTER_VALIDATE_URL)) {
    http_response_code(400);
    die("Invalid url");
}

function get_base($url) {
    $p = parse_url($url);
    $scheme = $p["scheme"] ?? "http";
    $host = $p["host"] ?? "";
    $port = isset($p["port"]) ? ":" . $p["port"] : "";
    $path = $p["path"] ?? "/";
    $dir = rtrim(dirname($path), "/") . "/";
    return $scheme . "://" . $host . $port . $dir;
}

function to_abs($base, $rel) {
    if (preg_match("#^https?://#i", $rel)) return $rel;
    if (strpos($rel, "//") === 0) return "https:" . $rel;

    if (strpos($rel, "/") === 0) {
        $p = parse_url($base);
        $scheme = $p["scheme"] ?? "http";
        $host = $p["host"] ?? "";
        $port = isset($p["port"]) ? ":" . $p["port"] : "";
        return $scheme . "://" . $host . $port . $rel;
    }

    return $base . $rel;
}

function curl_fetch($url) {
    $ua = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36";

    $ch = curl_init();

    curl_setopt_array($ch, [
        CURLOPT_URL => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_HEADER => true,
        CURLOPT_CONNECTTIMEOUT => 15,
        CURLOPT_TIMEOUT => 30,
        CURLOPT_SSL_VERIFYPEER => false,
        CURLOPT_SSL_VERIFYHOST => false,
        CURLOPT_HTTPHEADER => [
            "User-Agent: $ua",
            "Accept: */*",
            "Connection: keep-alive"
        ],
    ]);

    $res = curl_exec($ch);

    if ($res === false) {
        curl_close($ch);
        return ["ok" => false];
    }

    $hs = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
    $ct = curl_getinfo($ch, CURLINFO_CONTENT_TYPE);

    $body = substr($res, $hs);

    curl_close($ch);

    return [
        "ok" => true,
        "ct" => $ct,
        "body" => $body
    ];
}

$r = curl_fetch($url);

if (!$r["ok"]) {
    http_response_code(502);
    die("Fetch failed");
}

$body = $r["body"];
$ct = $r["ct"] ?? "";

header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Headers: *");
header("Access-Control-Allow-Methods: GET, OPTIONS");
if ($_SERVER["REQUEST_METHOD"] === "OPTIONS") exit;

$is_m3u8 = false;

if (!empty($ct) && stripos($ct, "mpegurl") !== false) $is_m3u8 = true;
if (strpos($body, "#EXTM3U") !== false) $is_m3u8 = true;

if ($is_m3u8) {
    $base = get_base($url);
    $lines = preg_split("/\r\n|\n|\r/", $body);
    $out = [];

    foreach ($lines as $line) {
        $t = trim($line);

        if ($t === "") {
            $out[] = "";
            continue;
        }

        if (strpos($t, "#") === 0) {

            if (stripos($t, "#EXT-X-KEY") === 0 && preg_match('/URI="([^"]+)"/', $t, $m)) {
                $key = $m[1];
                $absKey = to_abs($base, $key);
                $proxyKey = "?url=" . b64_to_hex(base64_encode($absKey));
                $t = preg_replace('/URI="([^"]+)"/', 'URI="' . $proxyKey . '"', $t);
            }

            $out[] = $t;
            continue;
        }

        $abs = to_abs($base, $t);
        $out[] = "?url=" . b64_to_hex(base64_encode($abs));
    }

    header("Content-Type: application/vnd.apple.mpegurl");
    echo implode("\n", $out);
    exit;
}

if (!empty($ct)) {
    header("Content-Type: $ct");
} else {
    if (preg_match("/\.ts(\?|$)/i", $url)) {
        header("Content-Type: video/mp2t");
    } elseif (preg_match("/\.m4s(\?|$)/i", $url)) {
        header("Content-Type: video/iso.segment");
    } elseif (preg_match("/\.mp4(\?|$)/i", $url)) {
        header("Content-Type: video/mp4");
    } elseif (preg_match("/\.key(\?|$)/i", $url)) {
        header("Content-Type: application/octet-stream");
    } else {
        header("Content-Type: application/octet-stream");
    }
}

echo $body;
exit;
?>
