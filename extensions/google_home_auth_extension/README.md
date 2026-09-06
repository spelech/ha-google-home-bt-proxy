# Google Home Bluetooth Proxy Auth Helper

A lightweight, standalone Chromium browser extension (Manifest V3) that automates capturing the Google Home authentication cookie (`oauth_token`) and sending it directly to your Home Assistant instance.

## Why This Extension?

Google Home tokens require authenticating via `https://accounts.google.com/EmbeddedSetup`. During this login flow, Google issues a master `oauth_token` with the `HttpOnly` flag. Because `HttpOnly` cookies cannot be accessed by normal in-page JavaScript or web pages, users previously had to manually open Developer Tools (`F12`), locate the cookie, and copy-paste the token into Home Assistant.

This extension runs locally in your browser, listens for the `oauth_token` cookie when you complete the `EmbeddedSetup` login, and automatically transmits it to Home Assistant's `/api/google_home_bt_proxy/auth_callback` endpoint.

---

## Features

- **Automated Cookie Interception:** Instantly captures the `oauth_token` when logging in to `accounts.google.com/EmbeddedSetup`.
- **Config Flow Integration:** Auto-advances your active Home Assistant configuration flow when Flow ID is provided.
- **Manual Trigger:** One-click "Check / Send Current Cookie" if you are already authenticated in your browser.
- **Visual Feedback:** Status indicators and badges (`OK`, `SEND`, `CFG`, `ERR`) directly in the toolbar.
- **Zero External Telemetry:** All communication occurs exclusively between your browser and your private Home Assistant instance.

---

## Installation Guide (Chrome / Edge / Brave / Opera)

This extension is distributed in source form and installed via the Chromium "Load unpacked" developer feature.

### Step 1: Access Extensions Page
- **Google Chrome:** Navigate to `chrome://extensions`
- **Brave Browser:** Navigate to `brave://extensions`
- **Microsoft Edge:** Navigate to `edge://extensions`
- **Opera / Vivaldi:** Navigate to your browser's extension management page

### Step 2: Enable Developer Mode
- In the top-right corner of the Extensions page, toggle the **Developer mode** switch to **ON**.

### Step 3: Load Unpacked Extension
1. Click the **Load unpacked** button in the top toolbar.
2. Select the `extensions/google_home_auth_extension` directory located inside this repository:
   ```
   /path/to/ha-google-home-bt-proxy/extensions/google_home_auth_extension
   ```
3. The extension **"Google Home Bluetooth Proxy Auth Helper"** will now appear in your browser's extension list.
4. (Optional) Click the puzzle piece icon in your browser toolbar and pin the extension for easy access.

---

## How to Connect to Home Assistant

### Option A: Fully Automated Flow (Recommended)

1. Open Home Assistant in your browser and start adding the **Google Home Bluetooth Proxy** integration:
   - Go to **Settings** > **Devices & Services** > **Add Integration** > search for **Google Home Bluetooth Proxy**.
   - If prompted, note your active **Flow ID** (or leave it blank to authenticate the integration).
2. Click the **Google Home Auth Helper** icon in your browser toolbar.
3. Configure the settings:
   - **Home Assistant URL:** Enter your instance URL (e.g. `http://homeassistant.local:8123` or your Nabu Casa / custom domain).
   - **Google Email Address:** Enter the email address associated with your Google Home devices.
   - **Config Flow ID (Optional):** Paste your flow ID if you want Home Assistant to auto-advance the setup wizard.
4. Click **Save Settings**.
5. Click **Start Google Login**:
   - A new browser tab opens to `https://accounts.google.com/EmbeddedSetup`.
   - Complete Google login (including 2FA if prompted) until you see the confirmation page.
6. The extension intercepts the `oauth_token` cookie and sends it to Home Assistant automatically.
7. Return to Home Assistant—your devices are ready!

### Option B: Manual Check / Send

If you have already signed in to `https://accounts.google.com/EmbeddedSetup` in the same browser:
1. Open the **Google Home Auth Helper** popup.
2. Verify your **Home Assistant URL** and **Google Email Address**.
3. Click **Check / Send Current Cookie**.
4. The extension locates the existing cookie and submits it to Home Assistant immediately.

---

## Security & Privacy Considerations

- **Runs 100% Locally:** There is no intermediate server, cloud service, or third-party tracking.
- **Restricted Scope:** The extension only inspects cookies with the exact name `oauth_token` originating from `accounts.google.com` or `google.com`.
- **Direct Communication:** Captured tokens are sent solely to the Home Assistant URL you configure in the extension's settings.
- **Temporary Use:** Once your Home Assistant integration is configured and has received the token, you may disable or remove the extension if desired.
