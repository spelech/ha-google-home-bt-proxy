# Google Home Bluetooth Proxy Auth Helper

A Chromium browser extension (Manifest V3) that captures the Google Home authentication cookie (`oauth_token`) and sends it to your Home Assistant instance.

## Why This Extension?

Google Home tokens require authenticating through `https://accounts.google.com/EmbeddedSetup`. During login, Google issues an `oauth_token` with the `HttpOnly` flag. Because `HttpOnly` cookies cannot be accessed by scripts inside web pages, users previously had to manually open Developer Tools (`F12`), find the cookie, and copy-paste it into Home Assistant.

This extension runs locally in your browser, detects the `oauth_token` cookie when login is complete, and sends it directly to Home Assistant's `/api/google_home_bt_proxy/auth_callback` endpoint.

---

## Features

- **Automatic Cookie Detection**: Captures `oauth_token` upon completion of login at `accounts.google.com/EmbeddedSetup`.
- **Config Flow Integration**: Advances your active Home Assistant configuration flow when Flow ID is provided.
- **Manual Submission**: "Check / Send Current Cookie" button if already logged in.
- **Visual Status**: Displays status badge in the browser toolbar.
- **Local Only**: Communicates exclusively between your browser and your Home Assistant instance.

---

## Installation (Chrome, Edge, Brave, Opera)

1. Open your browser's extension page:
   - Chrome: `chrome://extensions`
   - Brave: `brave://extensions`
   - Edge: `edge://extensions`
2. Toggle **Developer mode** to **ON** in the top-right corner.
3. Click **Load unpacked** in the top toolbar.
4. Select the `extensions/google_home_auth_extension` directory from this repository:
   ```
   /path/to/ha-google-home-bt-proxy/extensions/google_home_auth_extension
   ```
5. The extension will appear in your extensions list. Pin it to your toolbar for easy access.

---

## Usage

### Option A: Automatic Flow

1. In Home Assistant, start adding **Google Home Bluetooth Proxy** under **Settings** > **Devices & Services**.
2. If prompted with a Flow ID, copy it (optional).
3. Click the **Google Home Auth Helper** icon in your browser toolbar.
4. Enter your settings:
   - **Home Assistant URL**: Your instance URL (e.g. `http://homeassistant.local:8123`).
   - **Google Email Address**: The email associated with your Google Home devices.
   - **Config Flow ID (Optional)**: Paste the flow ID if available.
5. Click **Save Settings**, then click **Start Google Login**.
6. A new tab opens to `https://accounts.google.com/EmbeddedSetup`. Log in with your Google account.
7. The extension captures the cookie and forwards it to Home Assistant automatically.

### Option B: Manual Submission

If you already signed in to `https://accounts.google.com/EmbeddedSetup` in the same browser:
1. Open the **Google Home Auth Helper** popup.
2. Confirm the **Home Assistant URL** and **Google Email Address**.
3. Click **Check / Send Current Cookie**.

---

## Security

- Runs locally in the browser; there are no external servers or analytics.
- Only reads the cookie named `oauth_token` on `accounts.google.com` or `google.com`.
- Communicates directly with the configured Home Assistant instance URL.
- Once setup is complete, the extension can be disabled or removed.
