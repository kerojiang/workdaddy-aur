# workdaddy-aur

[![Sync WorkDaddy release to AUR](https://github.com/kerojiang/workdaddy-aur/actions/workflows/aur-sync.yml/badge.svg)](https://github.com/kerojiang/workdaddy-aur/actions/workflows/aur-sync.yml)

把 [babygoton/WorkDaddy](https://github.com/babygoton/WorkDaddy) 官方 Linux DEB 重打包为 Arch Linux AUR 包 **`workdaddy-bin`**，并由 GitHub Actions **每天检查一次**上游 Release：发现新版本后自动更新 `PKGBUILD` / `.SRCINFO`、提交回本仓库、推送到 AUR。

- 上游：<https://github.com/babygoton/WorkDaddy>
- AUR 页面：<https://aur.archlinux.org/packages/workdaddy-bin>（当前 `1.2.22-3`，维护者 `kerojiang`）
- 上游许可证：`AGPL-3.0-or-later`；本仓库打包脚本许可证：`0BSD`

> **范围**：仅 WorkDaddy 主版本（`WorkDaddy_<版本>_amd64.deb` / `_arm64.deb`）。上游 Release 中的 WorkDaddy-AI、CodeDaddy、CodeDaddy-CN 一律不打包。

---

## 安装

AUR 助手：

```bash
yay -S workdaddy-bin
# 或
paru -S workdaddy-bin
```

手动：

```bash
git clone https://aur.archlinux.org/workdaddy-bin.git
cd workdaddy-bin
makepkg -si
```

支持 `x86_64` 与 `aarch64`。包提供 `workdaddy`、与 `workdaddy` 冲突。可选依赖为 WorkBuddy 桌面客户端，下面两个包**任选其一**，二者互斥、不可同时安装：

| 可选依赖 | 说明 |
| --- | --- |
| `workbuddy` | 官方 DEB 解包，用系统 `electron` 运行 |
| `workbuddy-agent` | 同一官方 DEB 的原生二进制版本，AUR 上声明 `conflicts=('workbuddy')`，可替代 `workbuddy` |

依据：两个 AUR 包的 `package()` 都安装 `/usr/bin/workbuddy` → `/opt/WorkBuddy/workbuddy` 与 `usr/share/applications/workbuddy.desktop`；上游 README 第 143 行「请先安装并登录同架构的官方客户端」、第 256 行「不修改 WorkBuddy 二进制」；官方 DEB `control` 的 `Depends` 不含 WorkBuddy 客户端。`PKGBUILD(5)` 原文：*"optdepends are currently for informational purposes only and are not utilized by pacman during dependency resolution."* —— 因此只能双列提示，不能让 pacman 自动把其中一个解析为另一个；两个包的 `provides=()` 均为空，也不存在可用的虚拟包名。

运行时依赖由 `PKGBUILD` 的 `depends` 声明：`bash`、`ca-certificates`、`curl`、`gcc-libs`、`glibc`、`hicolor-icon-theme`、`procps-ng`、`util-linux`、`xdg-utils`。

### `zenity` 是可选依赖

官方 DEB 的 `control` 与上游 `scripts/build-linux-deb.sh:159` 把 `zenity` 写进 `Depends`；但 Arch `extra/zenity` 4.2.2 的 `depends` 为 `['glib2', 'glibc', 'gtk4', 'hicolor-icon-theme', 'libadwaita', 'libgcc', 'pango']`，会拉入一整串 GTK4/libadwaita 依赖。`PKGBUILD(5)` 对 `optdepends` 的定义是 *"not essential for base functionality, but may be necessary to make full use of the contents of this package"*，因此本包把 `zenity` 从 `depends` 移到 `optdepends`，不强制安装。

官方 payload 中 `zenity` 共 17 处引用，集中在 `scripts/launch-gui-linux.sh` 与 `scripts/wallpaper-rotation.js`；启动器自身有无 zenity 降级路径（`launch-gui-linux.sh:31` 用 `command -v zenity` 探测，`:35` 无图形会话时主动置空）。未安装 zenity 时的实际行为：

| 位置 | 行为 |
| --- | --- |
| `launch-gui-linux.sh:90` `run_action` | 同步执行命令，无进度条，功能正常 |
| `:110` / `:120` `show_result` / `fail_result` | 输出改为 `printf`；`.desktop` 为 `Terminal=false`，桌面双击时看不到启动结果与报错 |
| `:129` `confirm_restart` | `return 0` 等同同意重启：**不再弹确认框就重启 WorkBuddy 窗口**，当前窗口被关闭，未保存的对话内容不在脚本保护范围内 |
| `:255` 主菜单 | 退化为终端文本菜单；桌面图标传参 `cn` 不走该分支 |
| `wallpaper-rotation.js:263` | 无降级，`execFile('zenity')` 失败，壁纸目录选择按钮失效，手动填写路径仍可用 |

需要完整图形启动器时执行 `pacman -S zenity`。

### 为什么包名带 `-bin`

ArchWiki《[AUR submission guidelines](https://wiki.archlinux.org/title/AUR_submission_guidelines)》原文：

> *"Packages that use prebuilt deliverables, when the sources are available, must use the `-bin` suffix."*

本包直接解包上游官方预编译 DEB 的 `data.tar.xz`，不本地编译，因此必须带 `-bin`。官方 DEB 的 control 归档中只有 `./control`、没有 maintainer scripts，所以解包时无需模拟 dpkg 维护脚本。

### 本包补丁（pkgrel ≥ 4）

| 补丁 | 解决的问题 | 细节 |
| --- | --- | --- |
| `workdaddy-default-icon.patch` | 桌面启动器图标空白 | 上游 `scripts/install-desktop-linux.sh:24` 引用 `~/.local/share/workdaddy/icons/workdaddy-launcher.png`，但整个 payload 没有任何脚本会生成该文件；缺失时回退 `Icon=workbuddy`，而 `workbuddy-agent` 提供客户端时系统不存在该图标名。补丁把回退值改为 `workdaddy`——官方 DEB 自带 `/usr/share/icons/hicolor/1024x1024/apps/workdaddy.png`，本包必然安装 |
| `workdaddy-exit-guard.patch` | WorkBuddy 退出后 daemon 常驻不退 | 上游 daemon 由 `install-linux.sh:224` 的 `setsid nohup` 脱离进程树，且 `daemon.js` 没有任何「客户端退出 → 自杀」逻辑。补丁在 `startClientRunningMonitor()` 之后复用既有 `clientRunningState`（15s 周期探测 `linuxWorkBuddyPids`，按 argv0/realpath 精确匹配）：启动宽限 5 分钟 → 连续 4 次探测为 false（约 60s）→ 走 SIGTERM 清理流程退出。探测失败(null)与数据过旧不判定，单次误报自动清零 |

守卫环境变量：`WORKDADDY_EXIT_GUARD=0` 关闭；`WORKDADDY_EXIT_GUARD_GRACE_MS` / `WORKDADDY_EXIT_GUARD_INTERVAL_MS` 调整宽限与轮询间隔。`scripts/sync-release.py` 只重写 DEB 的 `sha256sums_x86_64/aarch64` 两行，补丁校验和在版本升级时自动保留。

---

## 仓库内容

| 文件 | 作用 |
| --- | --- |
| `PKGBUILD` | 解包对应架构的官方 DEB，应用 `patches/` 下两个补丁，并安装上游许可证到 `/usr/share/licenses/workdaddy-bin/LICENSE` |
| `patches/workdaddy-default-icon.patch` | 启动器图标回退到系统 hicolor 的 workdaddy 图标 |
| `patches/workdaddy-exit-guard.patch` | WorkBuddy 退出后 daemon 自动完全退出（可环境变量关闭） |
| `.SRCINFO` | 由 `makepkg --printsrcinfo` 生成，AUR 必需 |
| `LICENSE` | 本仓库 PKGBUILD 与脚本的 0BSD 许可证 |
| `LICENSE.upstream` | 上游 tag `1.2.22` 的 LICENSE 原文，随包安装 |
| `.github/workflows/aur-sync.yml` | 定时任务与手动触发入口 |
| `scripts/sync-release.py` | 查询上游 latest release、校验资产、重算 SHA-256、改写 `PKGBUILD` / `.SRCINFO` |
| `scripts/publish-aur.sh` | 用 SSH 密钥把包文件推到 `ssh://aur@aur.archlinux.org/workdaddy-bin.git` 的 `master` |

`.gitignore` 排除构建产物、下载的 DEB 和任何私钥；AUR 私钥存放在仓库之外，仅通过 GitHub Secret 注入 CI。

---

## 自动跟随

```yaml
# .github/workflows/aur-sync.yml
on:
  schedule:
    - cron: '23 3 * * *'   # 每天 UTC 03:23 / 北京 11:23
  workflow_dispatch:
```

每次运行的流程：

1. 调用 GitHub API `repos/babygoton/WorkDaddy/releases/latest` 取最新版本；
2. 校验该 Release 同时包含 `WorkDaddy_<版本>_amd64.deb` 与 `_arm64.deb`；
3. 下载两个 DEB，计算 SHA-256，并与 GitHub asset `digest` 交叉校验；
4. 改写 `pkgver`、`pkgrel`（重置为 1）、两架构的 `sha256sums` 与 `.SRCINFO` 中的 `source_*` URL；
5. `git commit` + `git push` 回本仓库；
6. 克隆 AUR 仓库，覆盖 `PKGBUILD`、`.SRCINFO`、`LICENSE`、`LICENSE.upstream`，推送 `master`。

防错设计：

- 草稿版或预发布版直接报错退出，不发布；
- 缺少任意一个架构的 DEB 直接报错退出，不发布半个包；
- 资产摘要与实际下载字节不一致直接报错退出；
- 下游版本号不高于本地版本时不产生任何提交；
- `publish-aur.sh` 用 `git diff --cached --quiet` 做幂等判断，AUR 内容一致时不提交、不推送；
- 因此**没有新版本的日子里也会做一次 AUR 一致性对齐**：配好密钥后首次发布会自动完成，推送失败也会在下一次定时运行时自愈重试。

**手动触发**：GitHub → Actions → *Sync WorkDaddy release to AUR* → *Run workflow*。勾选 `force` 会重新应用当前上游版本，用于重试一次失败的 AUR 推送。

依据 GitHub 官方《[Events that trigger workflows](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows)》：

> *"By default, scheduled workflows run in UTC."*
>
> *"The `schedule` event can be delayed during periods of high loads of GitHub Actions workflow runs."*
>
> *"In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days."*

即：定时基于 UTC，高负载时会延迟；本仓库为 public，连续 60 天无任何仓库活动后需到 Actions 页面重新启用该 workflow。每天一次的检查意味着上游发版后最长 24 小时被检测到，GitHub 高负载造成的额外延迟不计入这 24 小时。

---

## AUR 密钥配置（已完成）

AUR 推送只走 SSH 公钥认证，不使用账号密码。ArchWiki 原文：

> *"you need to have an SSH key pair. The content of the public key needs to be copied to your profile in My Account"*
>
> *"The AUR only allows pushes to the master branch."*

**当前状态**：`workdaddy-bin 1.2.22-3` 已发布（首发为 `1.2.22-1`，AUR 首发提交 `233c078`）。首发使用本机 `~/.ssh/aur`，该密钥已绑定 AUR 账号 `kerojiang`（`ssh -T aur@aur.archlinux.org` 返回 `Welcome to AUR, kerojiang!`）。同一把私钥已用 libsodium sealed box 加密写入 GitHub Actions Secret `AUR_SSH_PRIVATE_KEY`（GitHub API 返回 `201 Created`），GitHub runner 用它成功 clone 了 AUR 仓库（Run `43681612115` 日志：`AUR_SSH_PRIVATE_KEY: ***`、`Cloning into ...`、`AUR already matches local files`）。

| Secret | 状态 | 说明 |
| --- | --- | --- |
| `AUR_SSH_PRIVATE_KEY` | 已配置 | 与 AUR 账号绑定密钥对应的私钥全文，含 `-----BEGIN OPENSSH PRIVATE KEY-----` 头尾 |
| `AUR_USERNAME` | 未配置 | AUR 提交使用的 git user.name，默认 `jiangjie`；不影响推送权限 |
| `AUR_EMAIL` | 未配置 | AUR 提交使用的 git user.email，默认 `kero_jiang@126.com` |

未配置 `AUR_SSH_PRIVATE_KEY` 时，发布步骤打印 warning 后安全跳过，不影响仓库其余步骤。如需轮换密钥：在 AUR → My Account → SSH Public Key 追加新公钥（AUR 支持多公钥换行分隔），再到 GitHub → Settings → Secrets and variables → Actions 更新同名 Secret。

`publish-aur.sh` 会把 AUR 主机密钥固定写入 `known_hosts`（`StrictHostKeyChecking yes`），避免依赖 runner 上不可信的主机密钥。

---

## 本地验证

需要 Arch Linux 与 `base-devel`、`libarchive`（提供 `bsdtar`）：

```bash
# 构建并安装包
makepkg -si

# 仅构建，不安装（CI 之外无需 --nodeps）
makepkg -f --noconfirm

# 重新生成 .SRCINFO（改动 PKGBUILD 后必须同步）
makepkg --printsrcinfo > .SRCINFO

# 本地跑一次上游版本检查；目录内需已存放当前版本的两个官方 DEB，
# 设置该变量后脚本不再联网下载 DEB（仍会查询 GitHub API 取最新版本）
WORKDADDY_DEB_DIR=/path/to/debs python3 scripts/sync-release.py --repo-root .
```

已完成的验证记录：

| 项目 | 结果 |
| --- | --- |
| 实构 | `makepkg -f --nodeps --noconfirm` 通过；产物 129 个文件；检查 `control.tar` / `debian-binary` / `data.tar` 无残留 |
| 回归 | 模拟本地为 `1.2.21` 且校验和置零后运行同步脚本，两条 `optdepends` 全部保留、`.SRCINFO` 与 `makepkg --printsrcinfo` 逐字节一致；日常路径运行时 `PKGBUILD` / `.SRCINFO` 的 SHA-256 不变，输出 `changed=false` |
| CI 日常路径 | Run `43680253465`，`conclusion: success`，无版本变化时提交步骤 `skipped` |
| CI 发现更新路径 | Run `43680284204`（`force=true` 模拟），`conclusion: success`，提交步骤与 AUR 发布步骤均为 `success` |
| AUR 首发 | `git push origin master` 返回 `* [new branch] master -> master`；AUR 仓库 HEAD `233c078`；包页面 HTTP 200 且显示 `workdaddy-bin 1.2.22-1`、`AGPL-3.0-or-later`；远端 4 个文件与本地 SHA-256 逐项一致 |
| 端到端闭环 | Run `43681612115`，`conclusion: success`；日志显示 `AUR_SSH_PRIVATE_KEY: ***` 已注入、`Cloning into ...` 成功、`AUR already matches local files (version 1.2.22); nothing to push`，无 `Permission denied (publickey)` |
| zenity 移出硬依赖 | `depends` 移除 `zenity`（实构产物 `.PKGINFO` 的 9 条 `depend` 无 zenity），`optdepends` 增第 3 条并写明启动器弹窗/重启确认/壁纸目录选择用途；回归确认升级后三条 `optdepends` 全部保留。Arch `zenity` 4.2.2 依赖 `gtk4`/`libadwaita`/`pango`，移除后不再强制拉入该依赖链 |
| optdepends 双列 | 本次把 `workbuddy-agent` 列为 `workbuddy` 的替代客户端，并按 `PKGBUILD(5)`「incremented for intermediate PKGBUILD updates」将 `pkgrel` 递增至 2；`makepkg -f --nodeps --noconfirm` 产物 `.PKGINFO` 含两条 `optdepend`：`workbuddy`、`workbuddy-agent`；无 `control.tar` / `debian-binary` / `data.tar` 残留。GitHub commit `93f7eee`；CI Run `43682922558` `conclusion: success`，日志 `233c078..ef05a74 master -> master`、`pushed workdaddy-bin 1.2.22 to AUR`；AUR HEAD `ef05a74`，4 个文件与本地 SHA-256 一致；包页面 HTTP 200 显示 `1.2.22-2` 且含 `workbuddy-agent` |

AUR RPC 索引在首发后未即时刷新（`type=info` 仍返回 `resultcount:0`），包页面与 git 仓库已生效；`yay` / `paru` 等依赖 RPC 的客户端需等待 AUR 索引更新后才能搜到该包。

---

## 许可证

- 本仓库的 `PKGBUILD`、`.SRCINFO` 与 `scripts/`：[0BSD](LICENSE)。
- 上游 WorkDaddy 应用：[AGPL-3.0-or-later](LICENSE.upstream)，原文随包安装到 `/usr/share/licenses/workdaddy-bin/LICENSE`。

重打包不改变上游二进制的许可条款。
