# Google Home Bluetooth Proxy: Authentication Guide

This guide walks you through authenticating Google Home Bluetooth Proxy with your Google account.

---

## Which Method Should You Use?

| Method | When to Use | Setup Time |
| :--- | :--- | :--- |
| **1. Existing `ha-google-home` Import** | You already run the [ha-google-home](https://github.com/leikoilja/ha-google-home) integration in HA | **Instant (1 Click)** |
| **2. Google App Password** | Standard setup for personal Google accounts with 2-Step Verification | **~1 Minute** |
| **3. Browser Token Copy** | If App Password fails with `BadAuthentication` or `NeedsBrowser` | **~30 Seconds** |

---

## Method 1: Auto-Import from Existing Google Home Integration

If you already use the popular `ha-google-home` custom component for alarms, timers, or rebooting:

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Google Home Bluetooth Proxy**.
3. The integration detects your existing tokens automatically.
4. Click **Submit** to import credentials. No typing or token extraction required.

---

## Method 2: Google App Password (Recommended)

1. Open [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
   *(Note: You must have **2-Step Verification** turned on in your Google Account security settings to generate an App Password.)*
2. Under **App name**, enter `Home Assistant BT Proxy` and click **Create**.
3. Google displays a 16-character password (e.g. `abcd efgh ijkl mnop`).
4. In Home Assistant:
   - **Google Account Email**: Your full Google email address.
   - **App Password**: The 16-character password (spaces can be omitted or included).
   - **Master Token**: Leave blank.
5. Click **Submit**.

---

## Method 3: Browser DevTools Token Extraction

If Google rejects password login (returning `BadAuthentication` or requiring browser verification), you can grab a one-time token from Google in about 30 seconds using your regular web browser. **No extensions or developer mode required.**

### Step 1: Open Google Embedded Setup
Open a desktop browser (Chrome, Edge, Brave, or Firefox) and navigate to:
[https://accounts.google.com/EmbeddedSetup](https://accounts.google.com/EmbeddedSetup)

Log into your Google account normally. Complete any 2FA prompts, SMS codes, or passkey prompts that Google displays.

### Step 2: Open Developer Tools to Find the Cookie
1. Once logged in, press **`F12`** (or **`Ctrl+Shift+I`** on Windows/Linux, **`Cmd+Option+I`** on macOS).
2. Go to the **Application** tab in Chrome/Edge/Brave (or **Storage** tab in Firefox).
3. In the left sidebar, expand **Cookies** and click **`https://accounts.google.com`**.
4. In the table of cookies, locate the row named **`oauth_token`**.
5. Double-click the **Value** column for `oauth_token` and copy it. It starts with `oauth2_4/`.

![DevTools Cookie Extraction Guide](images/devtools_cookie_guide.jpg)

### Step 3: Paste into Home Assistant
1. In Home Assistant, open the **Google Home Bluetooth Proxy** setup dialog.
2. Enter your **Google Account Email**.
3. Leave **App Password** blank.
4. Paste the copied token directly into the **Master Token (Optional)** field.

![Home Assistant Setup Dialog](images/ha_setup_token_input.jpg)

5. Click **Submit**.

The integration automatically detects the `oauth2_4/` format, exchanges it with Google's authentication service for a permanent master token (`aas_et/...`), and registers your speakers as Bluetooth proxies.

---

## Frequently Asked Questions

### Does this token expire?
No. Once Home Assistant exchanges your credentials for a master token (`aas_et/...`), the master token remains valid indefinitely unless you change your Google account password or revoke access in your Google Account security settings.

### Is my Google password stored in Home Assistant?
No. Once authenticated, only the master token and generated Android identifier are stored in Home Assistant's encrypted configuration entry store (`.storage/core.config_entries`). Your raw password is never kept.

### Why doesn't Home Assistant use a standard "Sign in with Google" button?
Standard third-party Google OAuth (used by integrations like Google Calendar or Google Nest Device Access) only provides access to public Google cloud APIs. Local Google Home speakers communicate over HTTPS port 8443 using local Cast authentication tokens (`cast-local-authorization-token`) that are only issued via Google's internal Play Services Android client (`com.google.android.gms`). Every tool in the open-source smart home ecosystem (`ha-google-home`, `glocaltokens`, `pychromecast`) uses this same authentication mechanism.
