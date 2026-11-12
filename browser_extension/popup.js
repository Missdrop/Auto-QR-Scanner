document.getElementById("pair").addEventListener("click", async () => {
    const code = document.getElementById("code").value.trim();
    const response = await chrome.runtime.sendMessage({ type: "pair", code });
    document.getElementById("status").textContent = response?.ok
        ? "Paired. Sign in normally on AMS and keep the tab open."
        : response?.error || "Connection failed.";
});

async function inspectSession() {
    try {
        const response = await chrome.runtime.sendMessage({ type: "inspect" });
        const status = document.getElementById("session");
        if (!response?.ok) {
            status.textContent = "Open or refresh the AMS student tab to check its session.";
            return;
        }
        status.textContent = response.sessionDetected
            ? "AMS session detected. Synchronizing with the desktop app."
            : `Session not detected. Token present: ${response.hasDesktopToken}. Account fields: ${response.desktopFields.join(", ") || "none"}.`;
    } catch {
        document.getElementById("session").textContent = "Refresh the AMS page after reloading the extension.";
    }
}
inspectSession();
