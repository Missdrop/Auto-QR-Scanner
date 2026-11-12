# Auto QR Scanner

自动扫描微信群中新收到的二维码图片的实验项目。

## 目标

- 监听指定微信群的新图片消息。
- 识别人工拍摄屏幕的二维码，考虑倾斜、反光、摩尔纹和模糊。
- 对识别结果去重，提取二维码内容。

## 当前状态

项目已建立架构骨架，尚未实现消息监听、二维码扫描或桌面界面。当前没有可运行的扫描入口。

## 开发环境

使用 Python 3.12 和 uv：

```powershell
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pyrefly check
```

## 项目结构

```text
auto_qr_scanner/
├── app.py              # App：组织监听、扫描、记录和界面流程
├── wechat.py           # WeChat：微信交互和群图片获取
├── message.py          # ImageMessage：图片来源和接收时间
├── scanner.py          # Scanner：协调图片处理与二维码解码
├── image_processor.py  # ImageProcessor：拍屏图片增强与矫正
├── result.py           # Code、ScanResult：解码内容与来源
├── history.py          # History：扫描记录与去重
└── window.py           # Window：群选择、状态和结果展示
```

`App` 通过组合协调各对象，具体操作由对应对象负责。微信交互集中在 `WeChat` 中；拍屏处理与解码分开，便于独立验证识别效果。当前只包含初始化和职责说明，不包含业务方法或占位成功结果。

开发约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。

候选组件：

- [wxauto](https://github.com/cluic/wxauto)：Windows 微信界面自动化与图片获取。
- [ZXing-C++](https://github.com/zxing-cpp/zxing-cpp)：二维码检测与解码。

实际兼容性、拍屏识别率和处理延迟需要通过本机微信版本与真实样图验证。

请勿向仓库提交聊天图片、个人信息、登录凭证或敏感链接。
