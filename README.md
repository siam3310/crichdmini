
# CRICHD mini

A lightweight, self-hosted web application for streaming live TV channels, featuring a clean, modern interface and a PHP backend to proxy HLS streams.

## Features

- **Dynamic Channel List:** The list of channels is loaded dynamically from the `channels.php` backend, making it easy to manage.
- **HLS Stream Player:** Uses the robust `hls.js` library to play HLS (HTTP Live Streaming) feeds with low latency.
- **Modern UI:** Built with the Bootswatch "Zephyr" theme for a clean and modern user experience.
- **M3U Playlist Generation:** Includes a script (`playlist.php`) to generate a downloadable M3U playlist file, compatible with external players like VLC, IINA, or IPTV applications.
- **Proxy Backend:** The PHP backend fetches the stream links from the source, hiding the origin and providing a single point of access for the player.

## How to Set Up

To run this project, you need a local or remote web server with PHP support.

1.  **Download Files:** Place all the project files (`index.html`, `player.php`, `channels.php`, `playlist.php`) in the same directory on your web server.
2.  **Start a Local Server (Optional):** If you are working on your local machine, you can quickly start a PHP development server by running the following command in your terminal from the project directory:

    ```bash
    php -S localhost:8000
    ```

3.  **Access the Application:** Open your web browser and navigate to the server address. If you are using the local server command above, the URL will be:

    `http://localhost:8000`

## Credits

This project was developed by **Siam3310**.

