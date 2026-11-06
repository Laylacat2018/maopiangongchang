# 猫片工场

**当前版本：V1.1（1.1.0），已通过用户验收。** · [V1.1 功能与验收说明](docs/V1.1-验收说明.md) · [版本记录](CHANGELOG.md) · [V1.0 发布自测](docs/V1.0发布自测.md) · [域名部署规划](docs/域名部署规划.md)

V1.1已部署至[正式域名](https://maopian.migucomi.com/#production)，沿用原有账号登录；见[实际部署与验收记录](docs/V1.1域名部署自测.md)。

GitHub 仓库：[Laylacat2018/maopiangongchang](https://github.com/Laylacat2018/maopiangongchang)。正式标签使用 `v1.0.0`；后续功能或修复在新分支开发，通过持续集成后合入 `main`，不移动已发布标签。

基于《猫片工场 PRD v2.1-cc》开发的单用户本地萌宠视频生产台。沿用原设计的墨绿侧栏、薄荷绿选中态和珊瑚色主按钮，并按新版 PRD 调整为半手动流程。

平台管理人群简报、调研证据、剧情分镜、资产版本、官网主体、冻结提交包、候选审片、增强登记、剪映素材包、成片质检、费用与复盘。图片和视频由用户在模型官网生成；剪辑、配音和编码在剪映完成。只有用户主动确认的 LLM 调用会访问已配置的模型接口。

## 启动

环境：Python 3.12+、Node.js 20.19+、FFmpeg/ffprobe，Windows 10/11。当前电脑已安装并验证依赖。

在本目录双击 **启动猫片工场.cmd**，或执行：

```powershell
python run.py
```

默认地址 **http://127.0.0.1:8776**。首次运行自动创建虚拟环境、安装 Python/前端依赖并构建前端；后续只在源文件更新后重建。服务只监听本机，后台运行，关闭网页不会关闭服务。

发布版优先使用 `requirements-lock.txt` 和 `web/package-lock.json`；启动器检测依赖锁文件变化后更新依赖。`requirements-tested.txt` 保留最初的直接依赖版本记录。Python 锁文件中的 Windows 专用依赖含平台条件，其他操作系统由 pip 解析相应系统依赖，并由 CI 验证。

```powershell
# 仅启动，不打开浏览器
python run.py --no-browser

# 停止本项目管理的后台进程；会核验 PID 和可执行文件
powershell -NoProfile -File .\stop.ps1
```

若端口被其他程序占用，设置 `CATSTUDIO_PORT` 后启动。应用不会停止其他程序。手动开发模式：

```powershell
.\.venv\Scripts\python.exe -m uvicorn catstudio.main:app --host 127.0.0.1 --port 8776
# 另一个终端：
cd web
npm run dev
```

Vite 开发代理默认指向 8776。正式运行由 FastAPI 托管 `web/dist`，只有一个访问端口。

## 首次使用

1. 在“模型档案与设置”核对官网的实际版本、模式、参考图/音频上限、时长、画幅、分辨率、每候选积分与人民币换算。系统预置 Seedance、MiniMax H3、Vidu 的未核对档案，不预设当前能力或售价。
2. 如需 AI 辅助，在“LLM 配置”分别填写文本、多模态提供商、Base URL、实际模型 ID 和 API Key。可选 OpenAI 兼容协议或 Anthropic；没有凭证时可手工完成生产流程。
3. 创建项目，按 7 阶段确认关卡。官网生成前导出提交包，官网生成后回传到对应冻结记录。
4. 导出剪映素材包完成外部剪辑，回传成片，通过技术与人工检查后归档。
5. 手动发布、登记链接、导入平台 CSV，保存单变量实验，创建下一条简报。

详细操作和验收步骤见 [验收指南](docs/验收指南.md)。

## 实现结构

```text
catstudio/
  main.py       FastAPI 路由、输入检查、本机来源限制、静态页面
  db.py         SQLModel 表、SQLite WAL、版本与持久化字段
  services.py   关卡、版本依赖、绑定、冻结提交包、审片、预算、CSV、归档
  storage.py    SHA256 文件存储、ZIP、SQLite 在线备份及安全恢复
  media.py      FFprobe、每 0.5 秒抽帧、黑帧和静音检测
  llm.py        Jinja2 模板、Pydantic 输出、OpenAI/Anthropic HTTP 适配
  tasks.py      SQLite Huey 后台执行、状态持久化及中断恢复
web/src/        Vue 3、Element Plus 消息组件、Lucide 图标、ECharts 留存图
tests/          隔离数据目录中的端到端、边界及本地 LLM 协议测试
docs/           自测结果、验收指南和开发说明
data/           正式数据、文件、备份和日志（不纳入 Git）
```

业务表按 PRD 的项目、调研、剧本、资产、生成、交付、复盘和通用域命名。共同的 ID、项目/父级/镜头、版本、状态、排序、时长、金额、审计及软删除字段为 SQL 列，可变业务属性和冻结快照为 JSON。跨域规则由业务服务校验；候选选用有 SQLite 部分唯一索引兜底。此版初始化 schema 为 V1，后续数据库结构迁移需保留已有 `data` 并增加迁移脚本。

## 数据和凭证

- SQLite 和文件默认在本目录 `data/`，可用 `CATSTUDIO_DATA` 指定其他本地目录。数据目录应由单个服务实例独占，避免多台电脑同时打开同一云同步数据库。
- 文件按 SHA256 存储；定稿版本不可改写，候选、快照、费用记录保留。单文件上限 2GB。
- 金额以人民币分的整数保存。LLM 单价缺失时明确标记待核价；有单价时按实际 token 计为估算，可人工对账。平台不代收生成费用。
- API Key 用 Fernet 加密后保存，主密钥置于系统凭据管理器；API 不回传原文/密文。完整备份不含主密钥，换机后需重填 API Key。
- 应用运行期间每日自动备份，最近 7 份；手动备份可下载。恢复前验证 ZIP 路径与数据库完整性，并额外备份当前数据。
- 用户回传后的元数据、帧图与成片检测在后台执行。程序重启恢复本地处理；不会自动重放中断中的 LLM 请求。

## 测试

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests -q --junitxml=docs/test-results.xml
cd web
npm run build
```

完整生产测试会用 FFmpeg 创建合成视频和声音；这些是系统验收素材，不是 AI 萌宠作品，也不用于证明剧情或画面质量。测试不使用真实供应商账号、不发生外部付费。

GitHub Actions 自动执行锁定安装、生产构建和完整测试。测试的 API Key 存入仅存在于测试进程内的临时凭证后端，不读写用户的系统凭据管理器。发布前另执行空数据目录的真实 HTTP 服务与浏览器检查，详见 V1.0 发布自测。

## 边界与后续

P0 的半手动生产链已实现；商品替换、从旧项目复用简报与资产、选题库保存与引用复用、跨视频指标及实验对照也可操作。P1 的剪映原生草稿工程仍待当前剪映版本的兼容性验证，本版提供已实现的通用 ZIP 素材包。专业剧本平台与视频/图片 API 直连、自动发布、多人协作不属于本版。

真实 LLM 账号、模型官网的能力与价格、平台实际 CSV 样例、当前剪映的原生工程兼容性需要用户环境验收。已验证的本地功能、协议测试与这些待验证事项分别记在 [自测报告](docs/自测报告.md)。
