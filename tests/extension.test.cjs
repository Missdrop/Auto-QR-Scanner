const assert = require("node:assert/strict");
const test = require("node:test");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");

function createPage() {
    const events = [];
    const stored = new Map();
    const context = vm.createContext({
        sessionStorage: { getItem: key => stored.get(key) ?? null },
        localStorage: { getItem: () => null },
        location: { hash: "#/home" },
        setInterval: () => {},
        chrome: { runtime: { sendMessage: async message => {
            events.push(message.payload);
            return { ok: true };
        } } },
    });
    vm.runInContext(fs.readFileSync(path.join(__dirname, "../browser_extension/content.js"), "utf8"), context);
    return { context, stored, events };
}

test("companion sends session once and detects logout", async () => {
    const { context, stored, events } = createPage();
    stored.set("amsuserInfo", JSON.stringify({ userId: "student", token: "secret" }));
    await vm.runInContext("synchronize()", context);
    await vm.runInContext("synchronize()", context);
    assert.equal(events.filter(event => event.event === "session").length, 1);
    stored.delete("amsuserInfo");
    await vm.runInContext("synchronize()", context);
    assert.equal(events.at(-1).event, "logout");
});

test("companion distinguishes failure and success routes", async () => {
    const { context, events } = createPage();
    context.location.hash = "#/signCodeFail?message=expired";
    await vm.runInContext("synchronize()", context);
    assert.equal(events.at(-1).event, "failure");
    context.location.hash = "#/signCodeSuccess";
    await vm.runInContext("synchronize()", context);
    assert.equal(events.at(-1).event, "success");
});

test("corrupt stored data never sends a session", async () => {
    const { context, stored, events } = createPage();
    stored.set("amsuserInfo", "not json");
    await vm.runInContext("synchronize()", context);
    assert.equal(events.length, 0);
});

test("manifest limits content scripts to AMS pages", () => {
    const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, "../browser_extension/manifest.json"), "utf8"));
    assert.deepEqual(manifest.permissions, ["storage"]);
    assert.ok(manifest.content_scripts[0].matches.every(url => url.startsWith("https://ams.xjtlu.edu.cn/")));
});
