// Keep browser sessions inside the AMS-to-loopback connection.
async function deliver(event) {
    const { pairing } = await chrome.storage.local.get("pairing");
    if (!pairing) return { ok: false, error: "Paste the app pairing code first." };
    const [port, key] = pairing.split(":");
    const response = await fetch(`http://127.0.0.1:${port}/event`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${key}` },
        body: JSON.stringify(event),
    });
    if (!response.ok) throw new Error("App rejected the connection. Copy a fresh pairing code.");
    return { ok: true };
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
    const handle = async () => {
        if (message.type === "pair" && !sender.tab) {
            if (!/^\d{1,5}:[A-Za-z0-9_-]{32,64}$/.test(message.code)) {
                throw new Error("Invalid pairing code.");
            }
            await chrome.storage.local.set({ pairing: message.code });
            return deliver({ event: "ping" });
        }
        const source = new URL(sender.tab?.url || "https://invalid.local/");
        if (message.type !== "event" || source.origin !== "https://ams.xjtlu.edu.cn") {
            throw new Error("Only AMS tabs can send session events.");
        }
        return deliver(message.payload);
    };
    handle().then(respond).catch(() => respond({
        ok: false, error: "Cannot connect. Keep the desktop app running and pair again.",
    }));
    return true;
});
