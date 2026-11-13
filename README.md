# Auto QR Scanner

自动识别微信群和私聊中的二维码。识别后可在内置浏览器打开链接，并查看扫描记录。

## 启动

需要 **Windows 10/11 64 位**，微信需保持登录。

拉取仓库后，双击 **[scripts/start.cmd](scripts/start.cmd)** 即可启动：

```shell
git clone https://github.com/Missdrop/Auto-QR-Scanner.git
```

首次启动需要联网，程序会自动下载运行环境和 Chromium。

启动失败时，查看 `data/startup.log`。

## 使用

1. **选择会话**：输入群名或联系人名称的开头，从候选中选择，每行一个。
2. **登录网站（如需）**：点击 **打开内置浏览器**，登录后关闭窗口。登录资料会保留，过期后需重新登录。
3. **开始扫描**：选择图片来源，点击 **开始监听**。监听只处理新图片，旧消息可用 **扫描最近图片**。
4. **查看结果**：勾选 **识别后自动扫码** 可自动处理链接。点击记录可查看图片和结果，也可打开链接或重新扫码。

### 地址过滤

留白允许所有网址。需要限制自动扫码的网址时，每行填写一个域名或网址前缀：

```text
example.com
https://another.example/qr/
```

匹配任意一行即可。域名不包含子域名。未匹配的二维码仍会记录，手动打开链接和重新扫码不受限制。

### 图片来源

默认两项都勾选，所有选中的版本都会识别：

| 图片来源 | 特点 | 微信位于后台 | 消息免打扰 | 未选中监听会话 |
| --- | --- | --- | --- | --- |
| 缩略图 | 速度快、清晰度低 | ✓ | ✓ | ✓ |
| 压缩图 | 更清晰 | ✓（需选中会话） | ✓（需选中会话） | 无法获取 |

**具体情况请自行测试；最保险的方式是将微信置于前台，并打开监听的会话。**

## 注意事项

- 不支持微信小程序专用码。模糊、反光或遮挡严重的二维码可能无法识别。
- 普通链接只显示是否打开；安装对应的网站适配器后，才能显示网站的处理结果。打开网页不代表处理成功。
- 自动处理链接前，请先关闭内置浏览器窗口。
- 微信未缓存的图片暂时无法读取，可手动打开图片后重试。
- `data` 保存图片、记录、聊天数据库缓存和浏览器登录资料，请勿上传或分享。

## 网站适配接口

需要读取网站处理结果时，在 `website_adapters/<名称>/adapter.py` 中编写适配器：

```python
from urllib.parse import urlsplit
from adapters.base import AdapterResult, WebsiteAdapter


class Adapter(WebsiteAdapter):
    version = "1.0.0"
    description = "Process links from example.com"

    def matches(self, url: str) -> bool:
        return urlsplit(url).hostname == "example.com"

    def process(self, page, url: str) -> AdapterResult:
        # Replace this example with the website's actual processing logic.
        page.goto(url)
        return AdapterResult(result="已打开页面", details=page.title())
```

只需实现两个方法：`matches` 判断网址是否适用，`process` 使用已保存登录资料的网页完成处理。上例仅打开页面，实际结果需根据网站响应判断。

`process` 必须返回 `AdapterResult(result="结果文字", details="详情文字")`：

- `result`：显示在“扫码结果”，必填字符串，不能全为空白，最多 200 字符。
- `details`：显示在“详情”，可省略，默认空字符串，最多 4000 字符。

字段不符合要求时会抛出 `ValueError`。

保存后重启程序，点击 **查看适配器** 确认已加载。名称取自文件夹名；`version` 和 `description` 可省略。

## 贡献与许可

开发和贡献说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。

第三方组件保留各自的许可证，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。

Copyright © 2026 Missdrop · [GNU GPL v3.0](LICENSE)
