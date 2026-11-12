# 开发与贡献

使用 **Python 3.12 和 uv**，在 `dev` 分支开发。

## 准备环境

在仓库根目录执行：

```powershell
uv sync --locked --extra wechat
uv run --extra wechat python -m src.runtime --ensure
uv run --extra wechat python -m src
```

启动脚本位于 `scripts`。Chromium 使用项目固定版本，不使用日常浏览器的资料，也不使用 Chrome for Testing 替代。

仅识别本地图片，不打开链接：

```powershell
uv run python -m src --scan "C:\photos\example.jpg"
```

可用 `--data "D:\AutoQRData"` 指定数据目录。

## 代码风格

- 使用普通类、显式构造方法和组合，避免不必要的抽象。
- 命名清楚，方法简短，控制流程尽量平直；用空行分隔不同步骤。
- 标识符、注释、文档字符串和后端输出使用英文，GUI 文案使用中文。
- 添加必要的类型标注和解释原因的注释。
- 为有实际行为变化的功能补充测试，不用空壳或只重复实现的测试代替验证。

## 检查

提交前运行：

```powershell
uv run --extra wechat ruff check .
uv run --extra wechat ruff format --check .
uv run --extra wechat pyrefly check
uv run --extra wechat python -W error::ResourceWarning -m unittest discover -s tests -v
```

安装 Chromium 后，设置 `$env:QR_BROWSER_TESTS='1'` 再运行测试，可启用浏览器集成测试。这些测试拦截网络请求并使用模拟会话，不向真实网站提交二维码。

本地图片测试不需要微信登录。真实微信监听和网站处理需要单独验证，并在 PR 中写清哪些已实测、哪些仅由模拟测试覆盖。过期二维码返回正确提示，不代表有效二维码已验证成功；不要把样图识别耗时当作整个流程的耗时。

## 提交与 PR

1. 在 `dev` 完成一个独立改动，检查通过后做小提交。
2. 提交信息使用简短英文动词短语，以小写动词开头，例如 `fix image preview sizing`，无需强制添加类型前缀。
3. PR 提交到 `main`，说明解决的问题、行为变化、验证结果和已知限制，只包含本次相关改动。
4. 自动化协作者推送、创建 PR 或合并前，需要用户明确授权。

不要提交私人图片、聊天数据库、密钥、浏览器资料、运行时和诊断输出。`data/wechat` 可能包含明文消息数据库；旧版会话兼容文件和 Chromium 登录资料也属于私人数据。

## 实现约定

- 图片识别在本地完成，网页处理使用独立 Chromium。登录资料由浏览器保存，不将凭证写入 URL。
- 图片来源可多选，每个已选版本都要识别。二维码内容去重与图片版本识别分开处理，避免自动重复提交。
- 扫码结果以网站实际返回为准；普通链接打开后只能标记为已打开，不能标记为处理成功。
- 图片来源仅保留缩略图和压缩图，通过后台缓存读取，不自动操作微信窗口。

第三方来源与许可证见 [THIRD_PARTY.md](THIRD_PARTY.md)。Logo 文件位于 `assets`。
