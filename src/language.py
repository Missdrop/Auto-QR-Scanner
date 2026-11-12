def chinese(message: str) -> str:
    """
    Translate backend notices at the presentation boundary, leaving CLI English.
    """
    values = {
        "": "",
        "Low resolution; waiting for a clearer cached image": (
            "当前为低分辨率图片，正在等待更清晰的缓存版本"
        ),
        "Ready": "就绪",
        "Close the built-in browser before background processing": (
            "请先关闭内置浏览器窗口，再重试后台扫码；登录状态会保留"
        ),
        "Original download unavailable; open the image in WeChat": (
            "原图下载失败，请在电脑微信中打开该图片；缩略图识别不受影响"
        ),
        "Decoded": "已识别",
        "Duplicate": "重复二维码",
        "No QR code": "未识别到二维码",
        "Failed": "识别失败",
        "Monitoring stopped": "监听已停止",
        "Monitoring selected chats in the background": "正在后台监听所选会话",
        "Preparing background database access; WeChat can stay minimized": (
            "正在准备后台读取，微信可保持最小化"
        ),
        "Student login required": "请先登录账号",
        "Student session saved; platform validates it on use": (
            "账号登录已保存，扫码时由服务验证"
        ),
        "Student session available; platform validates it on use": (
            "账号登录已保存，扫码时由服务验证"
        ),
        "Sign in using Chromium, then close its window to synchronize the session": (
            "请在 Chromium 中登录账号，然后正常关闭窗口以同步登录"
        ),
        "Student session available; waiting for the platform result": (
            "正在通过 Chromium 扫码，等待扫码结果"
        ),
        "QR code queued for Chromium processing": "二维码已进入扫码队列",
        "Close Student login before processing a QR code": (
            "请先关闭账号登录窗口，再重试扫码"
        ),
        "Login required: open Student login and sign in": (
            "请打开内置浏览器，在对应网站登录后重试"
        ),
        "Login required: student session expired or was cleared": (
            "账号登录已过期，请重新登录"
        ),
        "Login required; retry pending records after signing in": (
            "请先登录，然后重试待处理记录"
        ),
        "Close the student login window and reopen Student login": (
            "请关闭内置浏览器窗口后重试"
        ),
        "Cannot start the local bridge; close other app instances": (
            "登录服务无法启动，请关闭其他程序实例"
        ),
        "Student queue is full; retry this record manually": (
            "扫码队列已满，请稍后手动重试这条记录"
        ),
        "Wait for the Chromium request before opening Student login": (
            "请等待当前扫码完成，再打开内置浏览器"
        ),
        "Image is not cached; open it once in WeChat and retry": (
            "微信尚未缓存图片，请手动打开图片后重试"
        ),
        "Image cache queue is full; retry missed images": (
            "图片等待队列已满，请手动重试遗漏图片"
        ),
    }
    if message in values:
        return values[message]
    prefixes = {
        "Platform confirmed successful processing: ": "签到成功：",
        "Platform rejected the QR code: ": "扫码未通过：",
        "Cannot obtain a platform result: ": (
            "无法确认扫码结果，请检查登录并手动重试。"
        ),
        "Monitoring stopped: ": "监听已停止，请检查微信登录和后台兼容性。",
        "Cannot decrypt cached image: ": "图片解密失败，请重试。",
        "Decoded: ": "已识别：",
        "Duplicate: ": "重复二维码：",
        "No QR code: ": "未识别到二维码：",
        "Failed: ": "识别失败：",
    }
    for prefix, translated in prefixes.items():
        if message.startswith(prefix):
            return translated + (
                message[len(prefix) :]
                if prefix.endswith(": ")
                and prefix in {"Decoded: ", "Duplicate: ", "No QR code: ", "Failed: "}
                else "请查看对应记录的扫码结果"
            )
    return "操作提示：请查看记录详情并重试"
