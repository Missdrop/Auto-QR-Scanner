// Read only the AMS session; never inspect password fields or the SSO page.
let lastSession = "";
let hadSession = false;
let lastRoute = "";

function readSession() {
    try {
        const mobile = JSON.parse(sessionStorage.getItem("amsuserInfo") || "null");
        if (mobile?.token && mobile?.userId) return mobile;
        const desktop = JSON.parse(localStorage.getItem("userInfo") || "null");
        const rawToken = localStorage.getItem("Token");
        // AMS desktop identifies the student with sourceId; mobile uses userId.
        const userId = desktop?.userId ?? desktop?.sourceId;
        if (!userId || !rawToken) return null;
        let token = rawToken;
        try { token = JSON.parse(rawToken); } catch { /* Plain strings are also used. */ }
        return { userId, token };
    } catch {
        return null;
    }
}

async function send(payload) {
    const response = await chrome.runtime.sendMessage({ type: "event", payload });
    return response?.ok === true;
}

async function synchronize() {
    try {
        const session = readSession();
        if (session) {
            const signature = JSON.stringify([session.userId, session.token]);
            if (signature !== lastSession && await send({
                event: "session", userId: String(session.userId), token: String(session.token),
            })) {
                lastSession = signature;
                hadSession = true;
            }
        } else if (hadSession && await send({ event: "logout" })) {
            lastSession = "";
            hadSession = false;
        }
        const route = location.hash.split("?")[0];
        if (route !== lastRoute) {
            const event = route === "#/signCodeSuccess" ? "success"
                : route === "#/signCodeFail" ? "failure" : null;
            if (!event || await send({ event })) lastRoute = route;
        }
    } catch {
        // Retry after pairing or when the desktop app is restarted.
    }
}

setInterval(synchronize, 2000);
synchronize();

chrome.runtime.onMessage.addListener((message, sender, respond) => {
    if (message.type !== "inspect-session") return false;
    let desktop = null;
    try { desktop = JSON.parse(localStorage.getItem("userInfo") || "null"); } catch {}
    const session = readSession();
    respond({
        ok: true,
        sessionDetected: !!session,
        hasDesktopToken: !!localStorage.getItem("Token"),
        desktopFields: desktop && typeof desktop === "object" ? Object.keys(desktop) : [],
    });
    synchronize();
    return false;
});
