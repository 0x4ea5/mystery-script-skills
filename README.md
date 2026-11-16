# 剧本杀 Skills

一套面向 AI 助手的中文剧本杀工作流：从原件归档、主持准备、独立玩家模拟，到多人对白配音。适合 DM 啃本、试跑流程、复盘卡点，以及把已有模拟记录做成可收听的音频。

仓库公开可用，可以直接把链接发给朋友，克隆或下载 ZIP 后按下方说明安装。

## 工作流与分工

```text
原件与版本核对
  → 逐页 OCR / 看图校订 / 来源索引
  → 主持准备：阶段、发放、问题、规则、提示和转场
  → 独立 DM + 独立玩家，按进度发材料并讨论
  → 冻结实际对白、提示记录和阶段认知
  → 固定声线配音、字幕与项目播放器
  → 验证、交付，保存可继续的停点
```

| Skill | 职责 | 入口 |
| --- | --- | --- |
| `mystery-script-ocr` | 原件归档、OCR、逐页校订、补页与来源追溯 | [说明](skills/mystery-script-ocr/SKILL.md) |
| `mystery-script-workflow` | 流程入口：主持准备、实际模拟、进度记录及配音交接 | [说明](skills/mystery-script-workflow/SKILL.md) |
| `mystery-dm` | 发放、规则、节奏、参与、扶车、裁定与转场 | [说明](skills/mystery-dm/SKILL.md) |
| `mystery-player` | 独立玩家推理、交流和个人 `记忆.md` | [说明](skills/mystery-player/SKILL.md) |
| `local-dialogue-audio` | 已有对白与获准读本的配音、缓存、字幕与交付 | [说明](skills/local-dialogue-audio/SKILL.md) |

核心原则：DM 保障玩家体验，让游戏继续推进；玩家只读本人已发材料和当时公开信息。保留真实错误、提示与改口，各自维护私有记忆，按事件记录恢复进度。全知助手编写的对白应标为虚构改编，不能称为独立玩家模拟。

## 安装

先下载并解压仓库，或直接克隆：

```shell
git clone https://github.com/0x4ea5/mystery-script-skills.git
cd mystery-script-skills
```

把 `skills/` 下的五个目录一起放到 Codex 的个人技能目录。相互引用依赖这五个目录位于同一级，复制后重新打开会话。下面的命令从仓库根目录执行；如果已经安装同名技能，会停止，请先比较或备份旧版。

PowerShell：

```powershell
$skillTarget = Join-Path $HOME '.codex/skills'
$skillFolders = Get-ChildItem -LiteralPath './skills' -Directory
foreach ($folder in $skillFolders) {
    if (Test-Path -LiteralPath (Join-Path $skillTarget $folder.Name)) {
        throw "已安装 $($folder.Name)，请先比较或备份旧版。"
    }
}
New-Item -ItemType Directory -Path $skillTarget -Force | Out-Null
foreach ($folder in $skillFolders) {
    Copy-Item -LiteralPath $folder.FullName -Destination $skillTarget -Recurse
}
```

macOS / Linux（Bash）：

```bash
(
  skill_target="${CODEX_HOME:-$HOME/.codex}/skills"
  for skill_dir in skills/*; do
    if [ -e "$skill_target/$(basename "$skill_dir")" ]; then
      echo "已安装同名技能，请先比较或备份：$skill_dir" >&2
      exit 1
    fi
  done
  mkdir -p "$skill_target"
  for skill_dir in skills/*; do
    cp -R "$skill_dir" "$skill_target/"
  done
)
```

其他助手也可以阅读 `SKILL.md` 并按流程执行，但技能发现、工具调用与独立实例的启动方式需要适配其运行环境。

## 直接这样使用

把路径、人数、版本和停止点换成你自己的项目。只做需要的阶段，已有可靠档案可以复用。

**整套流程**

```text
用 $mystery-script-workflow 处理这个项目。原件在“我的剧本/原件”，
先核对版本并归档，再准备主持流程，用独立DM和本作所需人数的玩家实际模拟到结局，
最后把真实对白制作成固定声线的分章音频。保留来源、提示和断点记录。
```

**只模拟 / 续局**

```text
用 $mystery-script-workflow 从“我的剧本/制作进度.json”继续。
复用已核档案，恢复每名玩家的私有记忆和漏读事件，本次只运行到第二幕结束。
```

**只配音**

```text
用 $local-dialogue-audio 把“我的剧本/已冻结对白”做成固定声线音频。
先检查来源和发放顺序，做一小段试听；确认声音配置后续做，输出MP3、字幕和制作记录。
```

## 需要哪些工具

- **归档**：能读取原件并渲染页面的工具；扫描件需要 OCR。看图校订需要实际查看页图，文字提取本身不证明已校对。
- **独立模拟**：支持独立上下文和文件读写的代理环境。默认示例为 DM + 六名玩家，实际人数依作品调整；并发不足可分批唤醒原身份。只读范围需要运行环境配合，提示词不等于文件系统强隔离。
- **配音**：Python 虚拟环境、Qwen3-TTS 依赖和本地模型；现有渲染路径面向兼容 CUDA / BF16 的设备。见[运行环境](skills/local-dialogue-audio/references/local-runtime.md)。模型、参考 WAV、虚拟环境均未附带。

包内提供中性的 DM / P1—P6 声线描述和参考台词。需要用户提供已授权且与台词一致的录音，或在项目目录生成新声音并试听。初始化和后续渲染命令见[执行流程](skills/local-dialogue-audio/references/pipeline.md)。脚本使用本地模型，不自动下载权重。

## 已有脚本与能力边界

| 内容 | 当前提供什么 |
| --- | --- |
| OCR 与主持、玩家技能 | 工作规则、模板及交接约定；需助手和实际工具执行 |
| `render_dialogue.py` | 单稿配音、固定参考声音、分句缓存、MP3 与 SRT |
| `build_audiobook.py` | 章级清单检查、续做、连续版和基础播放器打包 |
| `player.html` | 章级播放器模板，支持逐句定位与播放进度 |
| 跳过读本、LRC、动态称呼与分段目录 | 已定义[交付契约](skills/local-dialogue-audio/references/segmented-delivery.md)，需要项目编排或后处理实现，当前模板未全部实现 |

这是一套可安装、可衔接的技能包，尚未提供从原件到成品的一键运行器。不要把工作流要求当成脚本已经实现的功能。

每个项目可交付：来源索引与校订稿、分阶段主持资料、发放账、私有记忆、实际公开对白、提示与裁定记录、续做状态，以及明确完成范围内的音频成品。私人记忆和主持答案保持各自的可见范围。

## 检查与内容范围

在仓库根目录运行，无需 GPU、模型或第三方 Python 依赖：

```shell
python scripts/validate_repo.py
```

检查技能入口、相对链接、Python 语法、JSON、示例对白和声线配置；GitHub Actions 运行相同检查。它不验证 OCR 正确性、真实独立推理、模型兼容性或音频听感。

仓库仅收录通用方法、模板、脚本及中性示例。未包含剧本原件、具体作品的答案与模拟记录、个人路径、NAS 位置、参考音频或模型。原作材料及音频的读取、改编和分享范围由各项目自行确认。
