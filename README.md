# Momo + sing-box 1.13.x + Geph 5.8 + Loyalsoldier

本项目采用 **GitHub Actions 构建和发布，OpenWrt 主动拉取 Release** 的方式。OpenWrt 位于 NAT 后面也能使用，不需要公网 SSH、端口转发或 GitHub Runner 连接路由器。

## 工作流程

1. GitHub Actions 每天 04:15（北京时间）运行，也支持手动运行。
2. 使用固定版本 sing-box 1.13.21 编译 20 个本地 `.srs`。
3. 检查配置中的 20 个 rule-set tag 与实际生成文件是否一致。
4. 生成 `rule-set-<run-id>-<attempt>.tar.gz`，计算 SHA-256。
5. 上传版本化压缩包到固定 Release `rules-latest`。
6. 最后更新 `latest.txt` 指针。OpenWrt 先下载指针，再下载对应压缩包并校验 SHA-256。

**安全性：** 版本化归档先上传，`latest.txt` 最后更新。若归档上传失败，路由器仍会看到旧指针，不会误下载未完成的新包。Release 必须为公开仓库，才能让 OpenWrt 不带 GitHub Token 下载。

## 文件结构

- `momofake-1.13x-momo-geph58.json`：Momo 配置，Geph SOCKS5 为 `127.0.0.1:9909`。
- `loyalsoldier-rule-builder/build_rules.py`：生成 20 个 sing-box 1.13.x 本地规则集。
- `.github/workflows/update-rules.yml`：构建、校验、打包和发布。
- `openwrt/update-momo-rules.sh`：OpenWrt 主动拉取、校验并安装脚本。
- `openwrt/rule-updater.conf.example`：OpenWrt 下载配置示例。

## 一、创建 GitHub 仓库

1. 创建一个 **Public** 仓库，例如 `momo-geph-sing-box`。
2. 解压本项目 ZIP，将 `momo-geph-sing-box-automation/` 内的全部内容上传到仓库根目录。
3. 打开 `Actions`，允许工作流运行。
4. 进入 `Actions -> Build and publish Momo Loyalsoldier rule sets -> Run workflow` 手动执行首次构建。

成功后，在 `Releases` 中应看到 `rules-latest`，其中有：
- `latest.txt`
- `rule-set-<run-id>-<attempt>.tar.gz`
- `momofake-1.13x-momo-geph58.json`

## 二、OpenWrt 安装更新脚本

先确认路由器有 `curl` 或 `wget`、`tar` 和 `sha256sum`。BusyBox 通常提供 tar、wget、sha256sum；若缺少 curl/wget 或 HTTPS CA 证书，请安装相应软件包（常见为 `curl`、`ca-bundle`）。

将 `openwrt/update-momo-rules.sh` 上传至路由器 `/usr/bin/update-momo-rules.sh`，并赋予执行权限：

```sh
chmod 755 /usr/bin/update-momo-rules.sh
```

复制配置文件：

```sh
cp rule-updater.conf.example /etc/momo/rule-updater.conf
vi /etc/momo/rule-updater.conf
```

把 `GITHUB_REPO` 改为自己的 `用户名/仓库名`。确认 `DEST_DIR` 为 `/etc/momo/rule_set`，它必须与 JSON 中 20 个本地 rule-set 路径一致。

配置文件权限：

```sh
chmod 600 /etc/momo/rule-updater.conf
```

手动执行首次更新：

```sh
/usr/bin/update-momo-rules.sh
```

脚本会：
- 下载 `latest.txt` 和版本化归档；
- 校验 SHA-256；
- 检查压缩包只有 20 个平铺 `.srs` 文件；
- 检查 20 个预期文件均存在且非空；
- 先解压到临时目录，再替换规则目录；
- 记录已安装 SHA-256，重复版本不会重复下载。

## 三、设置 OpenWrt 定时任务

建议在北京时间 04:35 执行，比 Actions 的 04:15 晚 20 分钟：

```sh
echo '35 4 * * * /usr/bin/update-momo-rules.sh >> /tmp/momo-rule-update.log 2>&1' >> /etc/crontabs/root
/etc/init.d/cron restart
```

确认路由器时区正确。也可在 LuCI 的系统计划任务中添加同一条命令。

## 四、Momo 是否需要重启？

脚本默认只更新规则文件，不会擅自重启 Momo，因为不同 Momo/OpenWrt 版本的 init.d 服务名可能不同。

如果确认实际服务名，例如 `/etc/init.d/momo`，可在 `/etc/momo/rule-updater.conf` 设置：

```sh
RESTART_SERVICE="momo"
```

脚本安装成功后才会调用该服务的 `restart`。如果你的 Momo 通过 LuCI 管理或服务名不同，保持空值，并按你的插件方式手动 reload/restart。更新 `.srs` 文件不等于运行中的 sing-box 一定会重新加载它们。

## 五、验证

查看更新日志：

```sh
tail -n 100 /tmp/momo-rule-update.log
```

查看最后安装的 SHA-256：

```sh
cat /etc/momo/.momo-rule-set-sha256
```

查看规则文件：

```sh
ls -lh /etc/momo/rule_set/*.srs
```

## 注意

- 本项目发布的是规则文件，不会自动覆盖路由器现有配置 JSON。
- Release 使用固定 tag `rules-latest`，归档文件名按每次 Actions 运行生成，`latest.txt` 是最新版本指针。
- 版本化归档会累积在 Release 资产中；可以定期在 GitHub Release 页面清理旧归档，但必须保留 `latest.txt` 指向的当前归档。
- 若仓库设为 Private，OpenWrt 需要额外提供 GitHub Token；建议先使用公开仓库，不要把 Token 写入脚本或公开配置。
- Actions 构建通过不代表路由器上的 Momo 已经加载规则；部署后请检查 Momo 日志。
