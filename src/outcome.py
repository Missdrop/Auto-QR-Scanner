class Outcome:
    """
    Keep an actual platform outcome separate from successful QR decoding.
    """

    def __init__(
        self, url: str, status: str, code: int | None = None, message: str = ""
    ) -> None:
        self.url = url
        self.status = status
        self.code = code
        self.message = message

    def label(self) -> str:
        states = {
            "opened": "已在内置浏览器打开",
            "queued": "等待扫码",
            "processing": "正在扫码",
            "login": "需要登录",
            "error": "处理失败，需重试",
            "cancelled": "已取消，需重试",
        }
        if self.status in states:
            return states[self.status]
        if self.status != "result":
            return "未提交"
        if self.code == 0:
            return "签到成功"
        if self.code in {401, 403}:
            return "需要重新登录"
        message = self.message.lower()
        if "expired" in message or "过期" in message:
            return "二维码已过期"
        if any(
            value in message
            for value in (
                "not your",
                "not enrolled",
                "not registered",
                "not in this",
                "不属于",
                "非本人",
                "不是你的",
                "不是您的",
                "未选修",
            )
        ):
            return "不是我的课"
        if "already" in message and any(
            value in message for value in ("sign", "check", "attend")
        ):
            return "已签到"
        if "已签到" in message:
            return "已签到"
        return "扫码未通过"

    def detail(self) -> str:
        code = str(self.code) if self.code is not None else "无"
        return f"扫码结果：{self.label()}\n返回码：{code}\n原始提示：{self.message}"
