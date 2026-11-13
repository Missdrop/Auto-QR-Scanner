class Outcome:
    """Keep generic processing state and adapter-authored result text."""

    def __init__(
        self, url: str, status: str, result: str = "", details: str = ""
    ) -> None:
        self.url = url
        self.status = status
        self.result = result
        self.details = details

    def label(self) -> str:
        states = {
            "filtered": "已被地址过滤",
            "opened": "已在内置浏览器打开",
            "queued": "等待扫码",
            "processing": "正在扫码",
            "error": "处理失败，需重试",
            "cancelled": "已取消，需重试",
        }
        if self.status == "result":
            return self.result or "已处理"
        return states.get(self.status, "未打开")

    def detail(self) -> str:
        return f"扫码结果：{self.label()}\n详情：{self.details}"
