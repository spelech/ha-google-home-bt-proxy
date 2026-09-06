/**
 * Google Home Bluetooth Proxy Auth Helper - Background Service Worker
 * Manifest V3
 */

const DEFAULT_HA_URL = "http://homeassistant.local:8123";

let lastSentToken = null;
let lastSentTime = 0;

/**
 * Send OAuth token payload to Home Assistant callback API.
 * @param {string} token
 * @param {string} haUrl
 * @param {string} email
 * @param {string|null} flowId
 * @returns {Promise<{success: boolean, message: string}>}
 */
async function sendTokenToHomeAssistant(token, haUrl, email, flowId) {
  if (!token) {
    return { success: false, message: "Token is empty." };
  }
  if (!haUrl) {
    haUrl = DEFAULT_HA_URL;
  }
  if (!email) {
    await chrome.action.setBadgeText({ text: "CFG" });
    await chrome.action.setBadgeBackgroundColor({ color: "#FF9800" });
    const msg = "oauth_token detected, but Google Email is not configured. Please open extension popup to enter your email.";
    await chrome.storage.local.set({
      last_status: { success: false, message: msg, timestamp: Date.now() }
    });
    return { success: false, message: msg };
  }

  // Normalize HA URL (remove trailing slashes)
  const normalizedHaUrl = haUrl.replace(/\/+$/, "");
  const targetEndpoint = `${normalizedHaUrl}/api/google_home_bt_proxy/auth_callback`;

  // Update badge to indicate sending
  await chrome.action.setBadgeText({ text: "SEND" });
  await chrome.action.setBadgeBackgroundColor({ color: "#2196F3" });

  const payload = {
    oauth_token: token,
    email: email.trim()
  };
  if (flowId && flowId.trim()) {
    payload.flow_id = flowId.trim();
  }

  try {
    const response = await fetch(targetEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json().catch(() => ({}));

    if (response.ok && (data.status === "success" || data.master_token_acquired)) {
      lastSentToken = token;
      lastSentTime = Date.now();

      await chrome.action.setBadgeText({ text: "OK" });
      await chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });

      const msg = "Success! Token sent to Home Assistant and exchanged.";
      await chrome.storage.local.set({
        last_status: { success: true, message: msg, timestamp: Date.now() }
      });
      return { success: true, message: msg };
    } else {
      const errDetail = data.details || data.error || `HTTP error ${response.status}`;
      const msg = `Failed to exchange token in Home Assistant: ${JSON.stringify(errDetail)}`;

      await chrome.action.setBadgeText({ text: "ERR" });
      await chrome.action.setBadgeBackgroundColor({ color: "#F44336" });

      await chrome.storage.local.set({
        last_status: { success: false, message: msg, timestamp: Date.now() }
      });
      return { success: false, message: msg };
    }
  } catch (err) {
    const msg = `Network error connecting to Home Assistant (${targetEndpoint}): ${err.message}`;
    await chrome.action.setBadgeText({ text: "ERR" });
    await chrome.action.setBadgeBackgroundColor({ color: "#F44336" });

    await chrome.storage.local.set({
      last_status: { success: false, message: msg, timestamp: Date.now() }
    });
    return { success: false, message: msg };
  }
}

/**
 * Helper to look up oauth_token cookie across accounts.google.com and google.com
 */
async function findOauthTokenCookie() {
  const urlCandidates = [
    "https://accounts.google.com/EmbeddedSetup",
    "https://accounts.google.com",
    "https://google.com"
  ];

  for (const url of urlCandidates) {
    try {
      const cookie = await chrome.cookies.get({ url, name: "oauth_token" });
      if (cookie && cookie.value) {
        return cookie;
      }
    } catch {
      // Continue searching
    }
  }

  // Fallback: search all cookies named oauth_token
  try {
    const allCookies = await chrome.cookies.getAll({ name: "oauth_token" });
    const googleCookie = allCookies.find(
      (c) => c.domain && (c.domain.includes("google.com") || c.domain.includes("accounts.google.com"))
    );
    if (googleCookie && googleCookie.value) {
      return googleCookie;
    }
  } catch {
    // Ignore error
  }

  return null;
}

// 1. Listen for cookie changes
chrome.cookies.onChanged.addListener(async (changeInfo) => {
  if (changeInfo.removed) {
    return;
  }

  const cookie = changeInfo.cookie;
  if (!cookie || cookie.name !== "oauth_token" || !cookie.value) {
    return;
  }

  const domain = cookie.domain || "";
  if (!domain.includes("google.com")) {
    return;
  }

  // Prevent duplicate spam if identical token received within 5 seconds
  if (cookie.value === lastSentToken && Date.now() - lastSentTime < 5000) {
    return;
  }

  const stored = await chrome.storage.local.get(["ha_url", "email", "flow_id"]);
  const haUrl = stored.ha_url || DEFAULT_HA_URL;
  const email = stored.email;
  const flowId = stored.flow_id || null;

  await sendTokenToHomeAssistant(cookie.value, haUrl, email, flowId);
});

// 2. Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "check_and_send_cookie") {
    (async () => {
      const stored = await chrome.storage.local.get(["ha_url", "email", "flow_id"]);
      const haUrl = stored.ha_url || DEFAULT_HA_URL;
      const email = stored.email;
      const flowId = stored.flow_id || null;

      if (!email) {
        sendResponse({
          success: false,
          message: "Please enter and save your Google Email address in settings first."
        });
        return;
      }

      const cookie = await findOauthTokenCookie();
      if (!cookie || !cookie.value) {
        sendResponse({
          success: false,
          message: "No oauth_token cookie found on accounts.google.com. Click 'Start Google Login' to log in first."
        });
        return;
      }

      const result = await sendTokenToHomeAssistant(cookie.value, haUrl, email, flowId);
      sendResponse(result);
    })();

    return true; // Keep message channel open for async response
  }
});
