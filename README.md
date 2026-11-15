# workdaddy-aur

[![Sync WorkDaddy release to AUR](https://github.com/kerojiang/workdaddy-aur/actions/workflows/aur-sync.yml/badge.svg)](https://github.com/kerojiang/workdaddy-aur/actions/workflows/aur-sync.yml)

把 [babygoton/WorkDaddy](https://github.com/babygoton/WorkDaddy) 官方 Linux DEB 重打包为 Arch Linux AUR 包 **`workdaddy-bin`**，并由 GitHub Actions **每天检查一次**上游 Release：发现新版本后自动更新 `PKGBUILD` / `.SRCINFO`、提交回本仓库、推送到 AUR。

- 上游：<https://github.com/babygoton/WorkDaddy>
- AUR 页面：<https://aur.archlinux.org/packages/workdaddy-bin>（首次发布后可用）
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

支持 `x86_64` 与 `aarch64`。包提供 `workdaddy`、与 `workdaddy` 冲突，可选依赖为 `workbuddy`（WorkBuddy 桌面客户端）。运行时依赖由 `PKGBUILD` 的 `depends` 声明：`bash`、`ca-certificates`、`curl`、`gcc-libs`、`glibc`、`hicolor-icon-theme`、`procps-ng`、`util-linux`、`xdg-utils`、`zenity`。

### 为什么包名带 `-bin`

ArchWiki《[AUR submission guidelines](https://wiki.archlinux.org/title/AUR_submission_guidelines)》原文：

> *"Packages that use prebuilt deliverables, when the sources are available, must use the `-bin` suffix."*

本包直接解包上游官方预编译 DEB 的 `data.tar.xz`，不本地编译，因此必须带 `-bin`。官方 DEB 的 control 归档中只有 `./control`、没有 maintainer scripts，所以解包时无需模拟 dpkg 维护脚本。

---

## 仓库内容

| 文件 | 作用 |
| --- | --- |
| `PKGBUILD` | 解包对应架构的官方 DEB，并安装上游许可证到 `/usr/share/licenses/workdaddy-bin/LICENSE` |
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

## 首次上线需要配置的两处

AUR 推送只走 SSH 公钥认证，不使用账号密码。ArchWiki 原文：

> *"you need to have an SSH key pair. The content of the public key needs to be copied to your profile in My Account"*
>
> *"The AUR only allows pushes to the master branch."*

1. **AUR**：生成一对专用密钥（`ssh-keygen -t ed25519`），登录 AUR → My Account → SSH Public Key 填入公钥并保存。
2. **GitHub**：仓库 Settings → Secrets and variables → Actions → New repository secret，添加：

   | Secret | 必填 | 说明 |
   | --- | --- | --- |
   | `AUR_SSH_PRIVATE_KEY` | 是 | 上一步对应的私钥全文，含 `-----BEGIN OPENSSH PRIVATE KEY-----` 头尾 |
   | `AUR_USERNAME` | 否 | AUR 提交使用的 git user.name，默认 `jiangjie` |
   | `AUR_EMAIL` | 否 | AUR 提交使用的 git user.email，默认 `kero_jiang@126.com` |

未配置 `AUR_SSH_PRIVATE_KEY` 时，发布步骤打印 warning 后安全跳过，不影响仓库其余步骤。配置完成后，等当天定时运行或手动点一次 *Run workflow* 即完成首发。

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
| 回归 | 模拟本地为 `1.2.21` 且校验和置零后运行同步脚本，`PKGBUILD` 与原文逐字节一致，`.SRCINFO` 与 `makepkg --printsrcinfo` 逐字节一致，二次运行输出 `changed=false` |
| CI 日常路径 | Run `43680253465`，`conclusion: success`，无版本变化时提交步骤 `skipped` |
| CI 发现更新路径 | Run `43680284204`（`force=true` 模拟），`conclusion: success`，提交步骤与 AUR 发布步骤均为 `success` |

---

## 许可证

- 本仓库的 `PKGBUILD`、`.SRCINFO` 与 `scripts/`：[0BSD](LICENSE)。
- 上游 WorkDaddy 应用：[AGPL-3.0-or-later](LICENSE.upstream)，原文随包安装到 `/usr/share/licenses/workdaddy-bin/LICENSE`。

重打包不改变上游二进制的许可条款。
