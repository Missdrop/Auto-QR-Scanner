# Auto QR Scanner

自动识别微信群和私聊中的二维码图片，支持拍屏照片、扫描记录，以及使用已登录的内置浏览器处理链接。

## 启动

需要 **Windows 10/11 64 位**，并保持微信登录。

下载并解压仓库，双击 **[scripts/start.cmd](scripts/start.cmd)**。首次启动会自动下载运行环境和 Chromium，需要联网；之后可以直接启动。

启动失败时，查看 `data/startup.log`。

## 使用

1. 输入群名或联系人名称的开头，候选框会自动弹出，选择会话即可，每行一个。候选通过后台查询，不切换微信窗口。
2. 如需登录网站，点击 **打开内置浏览器**，自行登录后关闭浏览器窗口。登录资料会保留，网站会话过期时需重新登录。
3. 选择图片来源，点击 **开始监听**。默认使用缩略图和压缩图；开始监听后只处理新图片。也可用 **扫描最近图片** 处理旧消息。
4. 勾选 **识别后自动扫码**，识别出的网页链接会继续处理。选中记录可查看图片、二维码内容和扫码结果，也可打开链接或重新扫码。

**地址过滤**每行填写一个域名（如 `example.com`）或完整网址前缀（如 `https://example.com/qr/`），匹配任意一行即可自动扫码；留白允许所有网址。域名只匹配自身，不包含子域名。未匹配的二维码仍保存到记录，手动打开链接或重新扫码不受此限制。

图片来源可以同时勾选，程序会识别所有选中的版本：

| 图片来源 | 特点 |
| --- | --- |
| 缩略图 | 体积小、速度快，但清晰度低 |
| 压缩图 | 微信缓存的普通清晰版本 |

两种图片均从后台缓存读取，不打开图片窗口，不需要保持微信在前台。

## 注意事项

- 支持普通二维码；模糊、反光或遮挡严重的图片可能无法识别，不支持微信小程序专用码。
- 普通网页链接会在内置浏览器打开；已适配的链接可显示网站返回的处理结果。打开网页不代表处理成功。
- 后台处理前请关闭内置浏览器窗口，登录资料仍会保留。
- 微信未缓存的图片暂时无法读取，可手动打开图片后重试。
- 图片、记录、微信数据库缓存和浏览器登录资料保存在本机 `data` 目录，请勿上传或分享该目录。

## 贡献与许可

### 网站适配接口

在 `website_adapters/<名称>/adapter.py` 中定义 `Adapter` 类，修改后重启程序。该目录已被 Git 忽略，请只放入自己信任的代码。

```python
from urllib.parse import urlsplit


class Adapter:
    def matches(self, url: str) -> bool:
        return urlsplit(url).hostname == "example.com"

    def process(self, page, url: str) -> tuple[int, str]:
        # page is a Playwright page with the saved browser login.
        raise NotImplementedError("Implement website processing here")
```

`matches` 判断是否接管网址；`process` 使用已登录的 Chromium 页面执行操作，返回 `(结果码, 提示)`：`0` 为成功，`401/403` 为需登录，其余为未通过。未匹配适配器的网址按普通链接打开。请勿把“页面打开”当作处理成功。

开发和贡献说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。

本项目采用 [GNU GPL v3.0](LICENSE)。第三方组件保留各自的许可证，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。

Copyright (C) 2026 Missdrop，详见 [COPYRIGHT](COPYRIGHT)。
