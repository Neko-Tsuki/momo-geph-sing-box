Momo + sing-box 1.13.x + Loyalsoldier + Geph 5.8 配置包
======================================================

文件
----
- momofake-1.13x-momo-loyalsoldier.json：最终配置，保留原有 6 个 Momo 入站和策略组。
- build_rules.py / build_rules.sh：下载 Loyalsoldier 列表、V2Fly 域名分类基础数据及 FakeIP filter，并使用 sing-box 1.13.x 编译成本地 .srs。
- rule_set/：运行构建脚本后生成，包含配置引用的 20 个 .srs 文件。

Geph 连接
---------
配置已写入 SOCKS5 出站：127.0.0.1:9909，TCP only。请确保 Geph 5.8 的本地 SOCKS5 开启、VPN 模式关闭、系统代理接管关闭。
Geph 5 的传输基于可靠流/TCP；本配置将 UDP/443 拒绝以促使浏览器回退 TCP，其他 UDP 直连以兼容游戏、语音和局域网。若你的业务要求所有 UDP 也必须经代理，不能仅靠这个 SOCKS 出站实现，需要另外采用支持 UDP 的隧道方案。

构建规则集
-----------
建议在 Linux x86_64 电脑上安装 Python 3 和 sing-box 1.13.x，再运行：

  cd loyalsoldier-rule-builder
  python3 build_rules.py --sing-box /path/to/sing-box-1.13 --out-dir ./rule_set

需要能够访问 GitHub / raw.githubusercontent.com；脚本对 raw 文件提供 jsDelivr 回退。成功后应得到 20 个 .srs 文件。

部署到 OpenWrt
--------------
1. 先备份 Momo 当前配置和 /etc/momo/rule_set/。
2. 将所有 rule_set/*.srs 上传到 OpenWrt 的 /etc/momo/rule_set/。
3. 将 JSON 配置导入 Momo，确认 Momo 使用的 sing-box 核心确实是 1.13.x。
4. 在 OpenWrt 上用 Momo 实际使用的 sing-box 二进制执行配置检查：

  sing-box check -c /path/to/momofake-1.13x-momo-loyalsoldier.json

   如果 Momo 使用独立核心路径，请替换成该核心路径；不要只用电脑上的其他版本代替检查。
5. 确认 Geph 正在监听 127.0.0.1:9909，再启动 Momo。

分流行为
--------
- LAN / 私有 IP：直连。
- Momo Direct 模式：直连；Global 模式：交给 GLOBAL 选择器。
- geosite-cn：优先直连；geoip-cn：解析后优先直连。
- AI、YouTube、Google、GitHub、Telegram、TikTok、Netflix、PayPal、Steam、Microsoft、OneDrive、Apple：各自策略组默认选 Geph，可手动切换原有地区节点。
- geosite-!cn：默认代理；未命中规则：漏网之鱼策略组（默认代理）。
- UDP/443：拒绝，促使支持回退的应用使用 TCP；其他 UDP：直连。
- DNS：国内域名走 local；FakeIP filter 走 local；境外 A/AAAA 使用 Momo FakeIP；境外 DNS 默认经默认代理。

重要说明
--------
- 这是基于你之前提供的 Loyalsoldier 构建包修订的配置。保留 6 个 inbound 和原策略组；新增 Geph SOCKS outbound，并修正原配置里 geoip-apple 引用与构建产物不一致的问题。
- 当前环境无法联网下载规则数据，也没有可执行的 sing-box 1.13 二进制，因此本包不伪造已编译的 .srs 文件。请运行构建脚本生成真实规则文件，再部署。
- JSON 结构及规则集引用已做本地一致性检查，但尚未通过你的 OpenWrt Momo 实际 sing-box 二进制执行 `sing-box check`；上线前必须完成这一步。
- 国内域名优先级可能使部分在国内可访问的 Apple/Google 服务直连，这是预期行为。若某个具体域名在国内不可用，可单独加到代理例外规则中，不建议整体降低 geosite-cn 优先级。
