async (state) => {
    if (location.origin !== "https://ams.xjtlu.edu.cn") {
        throw new Error("Unexpected student page origin");
    }

    let token = localStorage.getItem("Token");
    if (!token) {
        return {code: 401, message: "Student login required"};
    }
    try {
        const decoded = JSON.parse(token);
        if (typeof decoded === "string") token = decoded;
    } catch {
        // AMS also stores unquoted tokens in some frontend versions.
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
        const query = new URLSearchParams({code: state, type: "1"});
        const response = await fetch("/xjtlu/sign/qRCodeSign?" + query, {
            method: "GET",
            headers: {"X-Token": token},
            credentials: "same-origin",
            redirect: "error",
            cache: "no-store",
            signal: controller.signal,
        });
        if (response.status === 401 || response.status === 403) {
            await response.body?.cancel();
            return {code: 401, message: "Student login required"};
        }
        if (!response.ok || !response.body) {
            await response.body?.cancel();
            throw new Error("The platform response was unavailable");
        }

        const reader = response.body.getReader();
        const chunks = [];
        let size = 0;
        while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            size += value.length;
            if (size > 65536) {
                await reader.cancel();
                throw new Error("The platform response exceeded its size limit");
            }
            chunks.push(value);
        }
        const content = new Uint8Array(size);
        let offset = 0;
        for (const chunk of chunks) {
            content.set(chunk, offset);
            offset += chunk.length;
        }
        const result = JSON.parse(new TextDecoder().decode(content));
        if (!result || !Number.isSafeInteger(result.code)) {
            throw new Error("The platform response has no result code");
        }
        // Only the public outcome crosses back to the desktop process.
        return {
            code: result.code,
            message: typeof result.message === "string"
                ? result.message.slice(0, 1000) : "No platform message",
        };
    } finally {
        clearTimeout(timer);
    }
}
