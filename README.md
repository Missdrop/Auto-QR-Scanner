# Auto QR Scanner

自动扫描微信群中新收到的二维码图片，也支持手动选择本地图片或整个文件夹。针对人工拍屏图片，尝试灰度、缩放、对比度增强、二值化及降噪，并提取同一图片中的多个二维码。

## 安装与启动

需要 Windows 10/11、Python 3.12、[uv](https://docs.astral.sh/uv/) 和 Microsoft Edge。

```powershell
uv sync --locked --extra wechat
uv run --extra wechat python -m src
```

只使用本地图片扫描时可以不安装微信适配依赖：

```powershell
uv sync --locked
uv run python -m src
```

命令行模式只解码图片并输出 JSON，不打开链接：

```powershell
uv run python -m src --scan "C:\photos\example.jpg"
```

## 使用

1. 点击 **Student login**，在学校页面自行完成学生账号登录。专用浏览器配置保存在本机，程序不保存账号密码。
2. 输入精确群名，每行一个，点击 **Start monitoring**。
3. 新收到的图片进入后台队列，识别后显示来源、时间、二维码内容、耗时和重复状态。
4. **Scan images / Scan folder** 可扫描本地图片。导入图片不会自动打开网页。
5. 选择记录后，可以复制内容、手动打开链接、通过学生会话打开 AMS 页面，或重新扫描原图片。

勾选 **Open new AMS codes in student session** 时，新收到且未重复的 AMS 二维码会交给学生浏览器处理。仅自动打开精确匹配的 HTTPS AMS 学生页面，其他二维码只显示内容。未登录或服务器报告会话失效时提示登录；会话存在不等于平台已确认处理成功。登录后需要手动重新打开之前未处理的记录，不自动重放旧码。

## 微信兼容性

微信接入基于 [wxauto](https://docs.wxauto.org/docs/install.html) 的 Windows 界面自动化，需要已登录的兼容客户端。

- `wxauto4` 免费后端：单群轮询，间隔约 0.3 秒；需保持目标聊天打开，切换聊天会停止监听。
- 已单独安装并配置 `wxautox4` 时：使用其多窗口监听接口；该后端需用户自行获取和激活，不随本项目提供。
- 免费后端当前文档标明支持到微信 `4.1.8.107`。本机微信 `4.2.0.52` 的实际连接测试失败，不能视为支持该版本。程序不会降级微信。
- 启动时跳过可见的旧消息。窗口隐藏、锁屏、客户端更新或 UI 元素变化可能导致漏取图片；没有后台协议级消息接收保证。

## 数据与限制

扫描记录和重复内容索引保存在 `data/history.sqlite3`，群图片副本保存在 `data/images`，学生浏览器配置保存在 `data/student-profile`。可通过 `--data "D:\AutoQRData"` 指定其他位置。浏览器配置包含会话资料，应仅保存在自己的设备上。

- 支持普通 QR 二维码，不支持微信专用小程序码。
- 不保存学生密码，不绕过验证码，不自动延长服务器规定的会话有效期。
- 最大图片文件 40 MB、解码后 2400 万像素。严重模糊、遮挡或反光可能无法恢复。
- 扫描队列上限 64 张；队列满时提示重试。关闭程序时尚未处理的队列不保留，已下载的图片可手动重新扫描。
- 界面显示最近最多 2000 行，启动加载最近 500 次扫描；完整记录仍在本地数据库。
- 重复状态按解码文本判断，保留每次扫描记录。手动重新扫描不会自动打开网页。
- 本机 14 张用户提供的拍屏样图全部解码成功，平均约 58 ms，最慢约 71 ms。该结果不代表其他图片识别率或微信到网页的端到端延迟。
- 学生登录和平台处理流程仍需真实账号及有效二维码验证，不能将扫描成功视为平台操作成功。

图片、数据库、浏览器配置、登录资料和临时验证输出均不提交到仓库。

## 项目结构

```text
src/
├── __main__.py         # 桌面和命令行入口
├── app.py              # App：协调界面、监听和扫描
├── wechat.py           # WeChat：客户端适配、消息过滤与图片获取
├── message.py          # ImageMessage：来源与接收时间
├── scanner.py          # Scanner：二维码解码
├── image_processor.py  # ImageProcessor：拍屏图片预处理
├── result.py           # Code、ScanResult：内容、耗时和错误
├── history.py          # History：SQLite 记录与去重
├── worker.py           # Worker：有界后台扫描队列
├── student.py          # Student：学生浏览器与登录状态
└── window.py           # Window：桌面控件和用户操作
```

`App` 通过组合组织流程。微信 UI 操作、图片扫描和学生浏览器分别在工作线程中运行，界面通过 Qt 信号接收结果。`Scanner` 不访问微信或网页，便于独立验证拍屏识别。

## 开发检查

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pyrefly check
uv run python -W error::ResourceWarning -m unittest discover -s tests -v
```

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。
