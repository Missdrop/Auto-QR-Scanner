# Browser companion

1. Start the desktop app.
2. Open Chrome Extensions, enable Developer mode and load this directory as an unpacked extension.
3. Click **Copy browser pairing code** in the desktop app.
4. Open the extension popup, paste the code and click **Pair with desktop app**.
5. Use **Student login** in the app and sign in normally. Keep the AMS tab open.

The extension reads AMS session storage on the two student paths only. It never runs on the university SSO password page. It sends session and page-status events to the authenticated loopback service and does not contact another server. No student token is stored in the extension's settings; only the local pairing code is stored.

If the app reports that the session expired, sign in again. A saved session is not proof of server acceptance. Remove this extension and clear the app's local student directory to disconnect it.
