/**
 * Google Home Bluetooth Proxy Auth Helper - Popup Controller
 */

const DEFAULT_HA_URL = "http://homeassistant.local:8123";

const haUrlInput = document.getElementById("ha-url");
const emailInput = document.getElementById("email");
const flowIdInput = document.getElementById("flow-id");
const configForm = document.getElementById("config-form");
const loginBtn = document.getElementById("login-btn");
const checkCookieBtn = document.getElementById("check-cookie-btn");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");

/**
 * Update the status indicator and message
 * @param {string} message
 * @param {'ready'|'waiting'|'sending'|'success'|'error'} state
 */
function updateStatus(message, state = "ready") {
  statusText.textContent = message;
  statusDot.className = "status-dot";
  if (state !== "ready") {
    statusDot.classList.add(state);
  }
}

/**
 * Save current settings to chrome.storage.local
 * @returns {Promise<{ha_url: string, email: string, flow_id: string}>}
 */
async function saveSettings() {
  const ha_url = (haUrlInput.value || DEFAULT_HA_URL).trim();
  const email = emailInput.value.trim();
  const flow_id = flowIdInput.value.trim();

  await chrome.storage.local.set({ ha_url, email, flow_id });
  return { ha_url, email, flow_id };
}

// 1. Initialize UI on load
document.addEventListener("DOMContentLoaded", async () => {
  const stored = await chrome.storage.local.get([
    "ha_url",
    "email",
    "flow_id",
    "last_status"
  ]);

  haUrlInput.value = stored.ha_url || DEFAULT_HA_URL;
  emailInput.value = stored.email || "";
  flowIdInput.value = stored.flow_id || "";

  if (stored.last_status && Date.now() - (stored.last_status.timestamp || 0) < 1800000) {
    updateStatus(
      stored.last_status.message,
      stored.last_status.success ? "success" : "error"
    );
  } else {
    updateStatus("Ready", "ready");
  }
});

// 2. Save settings button / form submit
configForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  await saveSettings();
  updateStatus("Settings saved!", "success");
});

// 3. Start Google Login button
loginBtn.addEventListener("click", async () => {
  await saveSettings();
  updateStatus("Waiting for login...", "waiting");
  await chrome.tabs.create({
    url: "https://accounts.google.com/EmbeddedSetup"
  });
});

// 4. Manual Check / Send Cookie button
checkCookieBtn.addEventListener("click", async () => {
  const { email } = await saveSettings();
  if (!email) {
    updateStatus("Please enter your Google email address first.", "error");
    emailInput.focus();
    return;
  }

  updateStatus("Sending token...", "sending");
  checkCookieBtn.disabled = true;

  try {
    const response = await chrome.runtime.sendMessage({
      action: "check_and_send_cookie"
    });

    if (response && response.success) {
      updateStatus(response.message || "Success! Sent to Home Assistant.", "success");
    } else {
      const err = response ? response.message : "Unknown error sending cookie.";
      updateStatus(err, "error");
    }
  } catch (err) {
    updateStatus(`Error: ${err.message}`, "error");
  } finally {
    checkCookieBtn.disabled = false;
  }
});

// 5. React to storage changes in real-time
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && changes.last_status && changes.last_status.newValue) {
    const newStatus = changes.last_status.newValue;
    updateStatus(
      newStatus.message,
      newStatus.success ? "success" : "error"
    );
  }
});
