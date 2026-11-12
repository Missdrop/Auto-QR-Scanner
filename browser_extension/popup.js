document.getElementById("pair").addEventListener("click", async () => {
    const code = document.getElementById("code").value.trim();
    const response = await chrome.runtime.sendMessage({ type: "pair", code });
    document.getElementById("status").textContent = response?.ok
        ? "Paired. Sign in normally on AMS and keep the tab open."
        : response?.error || "Connection failed.";
});
