# 猫片工场域名部署

本套配置为单个所有者提供完整服务：Python / FFmpeg / SQLite / 本地任务队列 / Vue 前端。
不会调用付费模型；模型配置仍需所有者在产品中填写。桌面版已有凭证和素材不会自动上传。

## 运行边界

- 单实例、单 Uvicorn worker；不配置多副本。数据和主密钥分别存入 Docker 命名卷。
- 后端只发布到宿主机 `127.0.0.1:8776`，所有页面、API、文件和文档均要求 HTTP Basic 登录。
- 域名必须用 HTTPS 代理；不要把明文 HTTP 临时入口发给用户输入密码。
- 公网域名白名单、认证文件、持久化主密钥缺一会拒绝启动。默认桌面启动方式不变。
- 已有 Nginx/Caddy/宝塔网关时，添加独立虚拟主机；不启动本目录的 Caddy 覆盖已有 80/443。
- 2GB 主机需先确认现有应用可用内存、磁盘、端口；不要为了本应用停止其他服务。

## 初次安装

先在授权服务器检查操作系统、磁盘/内存、容器运行时及已有代理配置，然后检出经 CI 验证的固定提交。
以下命令在仓库根目录执行；需要预先安装 Docker Engine 和 Compose v2。

```bash
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm --no-deps app \
  python scripts/create_server_auth.py --file /var/lib/catstudio/secrets/access.json
docker compose -f deploy/compose.yaml up -d --no-build
```

认证初始化会隐藏输入密码，要求至少 16 字符，文件只保存随机盐和 PBKDF2-SHA256 哈希。
脚本拒绝覆盖已有认证文件。主密钥第一次启动时以 0600 创建，后续必须保留，损坏时不会静默重建。
命名卷归容器 UID/GID 10001 所有；不要更改成全局可读。不要将密码、认证文件或主密钥放入 Git。

默认域名是 `maopian.migucomi.com`。需要变更时，在受控私有环境文件设置
`CATSTUDIO_DOMAIN`，并同步 DNS、TLS 和代理主机名；不要设通配符。

### 已有 Nginx

参考 `nginx.conf.example` 新建独立配置，先检查目标端口没有冲突。
HTTP 阶段仅提供 ACME 验证目录；证书签发后才启用 HTTPS server 块。
`nginx -t` 成功后平滑 reload，随后从外网验证未登录 401、HTTPS 证书和已登录读写。
现有证书如果没有覆盖该子域名，不能直接复用。

### 空闲主机使用 Caddy

仅在没有已有网关且 80/443 空闲时：

```bash
docker compose -f deploy/compose.yaml -f deploy/compose.caddy.yaml up -d --no-build
```

先将 `maopian` 的 A 记录解析到已授权服务器，并确认入站 80/443 按需要放通。
Caddy 自动申请和续签证书；其状态持久化在专用卷。访问认证由后端统一执行。

## 验收

### 已有 Podman 与 Caddy 的主机

可加载正式 Release 中经过 CI 全流程验证的 Linux amd64 镜像，先用随附 SHA256 文件核对下载。
镜像不包含认证、主密钥或运行数据。`deploy/catstudio.container` 为 Podman Quadlet 示例，
通过 systemd 管理重启、开机启动和资源限制；不要另外安装 Docker 覆盖已有容器环境。
初始化独立的 `catstudio-data`、`catstudio-secrets` 命名卷，确认所有者为 UID/GID 10001，
运行同一个 `scripts/create_server_auth.py` 初始化认证后再启动服务。
已有 Caddyfile 中只添加本域名的站点块并代理到 `127.0.0.1:8776`；保存原配置，
先 `caddy validate`，再平滑 reload；不要使用示例的独占 80/443 Caddy 容器。

1. 未登录访问 `/`、`/api/state`、`/files/...`、`/docs` 均返回 401；不存在可绕过的后端公网端口。
2. 登录后新建项目、走完 7 阶段；真实合成视频上传、候选检测、审片、剪辑包、成片质检、归档和 CSV 复盘都通过。
3. 验证视频 `Range` 返回 206、下载 ZIP 完整、外站 Origin 写入和错误 Host 都被拒绝。
4. 重启应用后项目、媒体、任务和加密凭证仍可使用。
5. HTTPS 证书有效，HTTP 重定向 HTTPS，既有站点和服务正常。

`scripts/smoke_server.py` 用于独立验收环境，会创建明确标记的自测项目和虚构模型配置。
真实模型或用户素材导入后不要再对生产数据执行它；正式环境使用手动验收项目。
CI 会自动构建容器、执行真实 HTTP 全链路并验证重启后数据及主密钥可恢复。

## 备份和回滚

- 应用每日生成最近 7 份数据库+素材备份；这些备份不含解密主密钥和访问认证文件。
- 服务器级灾备需额外备份 `catstudio_secrets`、`catstudio_data` 以及反向代理证书/配置。
  主密钥备份必须加密并限制权限，和业务备份分开保管；任何永久丢失都无法恢复已保存的 API Key。
- 维护前记录当前 Git SHA、镜像 ID 和卷位置；升级前导出备份、停止当前实例，禁止新旧版本同时写 SQLite。
- 回滚到此前验证过的代码/镜像，并保留当前数据卷；若涉及未来数据库迁移，先在独立环境验证备份恢复。
- 不使用 `docker compose down -v`，该命令会删除数据卷。停止/重启只使用 `stop` / `restart` / 不带 `-v` 的 `down`。
- 服务器身份核验、SSH 账户、过期续费、DNS 及已有站点配置由实际环境记录确定，本说明不代表域名已上线。
