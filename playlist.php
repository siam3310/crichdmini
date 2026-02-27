<?php
// This script generates an M3U playlist.
error_reporting(0);
require_once 'channels.php'; // Include the channel list

// Determine the base URL for the stream links
$self_url = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on' ? "https" : "http") . "://$_SERVER[HTTP_HOST]";
$player_path = str_replace(basename(__FILE__), 'player.php', $_SERVER['SCRIPT_NAME']);

// Set headers to make the browser download the file with the .m3u extension
header('Content-Type: application/vnd.apple.mpegurl');
header('Content-Disposition: attachment; filename="crichdmini-playlist.m3u"');

// Start the M3U file content
echo "#EXTM3U\n";

// Loop through the channels and create an entry for each
foreach ($channels as $id => $details) {
    $name = $details['name'];
    $logo = $details['logo'];
    // The stream URL for each channel points to the player.php proxy
    $stream_url = $self_url . $player_path . '?channel=' . $id;
    
    // Add the tvg-logo attribute for IPTV players
    echo "#EXTINF:-1 tvg-id=\"{$id}\" tvg-name=\"{$name}\" tvg-logo=\"{$logo}\",{$name}\n";
    echo $stream_url . "\n";
}

?>
