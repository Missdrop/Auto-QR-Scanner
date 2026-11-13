def chinese(message: str) -> str:
    """
    Translate backend notices at the presentation boundary, leaving CLI English.
    """
    values = {
        "": (""),
        "Low resolution; waiting for a clearer cached image": (
            "当前为低分辨率图片，正在等待更清晰的缓存版本"
        ),
        "Invalid address filter": (
            "地址过滤格式无效，请每行填写一个域名或完整 HTTP/HTTPS 网址前缀"
        ),
        "Select at least one valid image source": ("请至少勾选一种图片来源"),
        "Conversation suggestions unavailable; enter a name manually": (
            "后台候选读取失败，仍可手动填写精确会话名称"
        ),
        "Close the built-in browser before background processing": (
            "请先关闭内置浏览器窗口，再重试后台扫码；登录状态会保留"
        ),
        "Decoded": ("已识别"),
        "Duplicate": ("重复二维码"),
        "No QR code": ("未识别到二维码"),
        "Failed": ("识别失败"),
        "Monitoring stopped": ("监听已停止"),
        "Monitoring selected chats in the background": ("正在后台监听所选会话"),
        "Preparing background database access; WeChat can stay minimized": (
            "正在准备后台读取，微信可保持最小化"
        ),
        "Browser session available; waiting for the platform result": (
            "正在通过 Chromium 扫码，等待扫码结果"
        ),
        "QR code queued for Chromium processing": ("二维码已进入扫码队列"),
        "Wait for the Chromium request before opening browser window": (
            "请等待当前扫码完成，再打开内置浏览器"
        ),
        "Image is not cached; open it once in WeChat and retry": (
            "微信尚未缓存图片，请手动打开图片后重试"
        ),
        "Image cache queue is full; retry missed images": (
            "图片等待队列已满，请手动重试遗漏图片"
        ),
        "Login required": ("请打开内置浏览器登录后重试"),
        "Cannot load website adapter; check adapter.py": (
            "网站适配器加载失败，请检查 adapter.py"
        ),
        "Website adapter matching failed": ("网站适配器匹配失败，请检查适配代码"),
    }
    if message in values:
        return values[message]
    prefixes = {
        "Platform confirmed successful processing: ": "处理成功：",
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
