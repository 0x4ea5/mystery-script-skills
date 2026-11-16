# 稿件、清单与执行

## 稿件格式

UTF-8文本；起止标记各出现一次。正文只允许小节标题、阅读节点和单行发言，未知声线或漏标记会报错。

```text
本章范围、版本、具体文件/PDF页、改编说明
=== 配音正文 ===
--- 读完自述后 ---
〔阅读节点：此处只记录已经发放的材料，不参与配音。〕
DM：我们先把能确认的线索放在桌上。
P1：等一下，这里只说见过，没有说认出了身份。
P2：那我把刚才那条等号改成问号。
=== 正文结束 ===
其他来源与待核项
```

包内默认ID为DM、P1—P6；P1—P3女声，P4—P6男声。按本项目人数和已认可配置选择，不要求每段全员发言。内部ID是稳定的声音身份，字幕称呼另按[逐发言认知](source-and-names.md)记录。自定义声线通过 `--voices` JSON和 `--references` 目录传入：每个ID有 `reference_text`、`label`，设计新声线时再需要 `description`；目录中配对应ID.wav。参考文本必须与录音一致。本仓库只附声线配置，不附WAV；首次使用先按下面的初始化命令准备参考音频。

同一发言过长时按完整语义断句，别把扫描/排版的硬换行当成句末，导致一个词跨两个合成片段。可以接入已有真实追问，不能补造互答或截掉关键词。坐标/数字若需易读写法，记录明确改写，并让音频与字幕来自同一台词；保留可回查的原句。

## 项目清单

下例是现有脚本的章级清单格式，路径相对于清单所在目录。`reviewed`由执行agent在内容门槛核对后设置；不表示用户另行批准或音频已全听校。分段type、来源边界与动态字幕由[分段清单](segmented-delivery.md)或项目适配层补充，不要假定本例已实现过滤播放。

```json
{
  "title": "模拟打本·对话版",
  "source_note": "当前版本及出处；讨论口语改编，不逐字朗读材料。",
  "chapter_gap_seconds": 3,
  "chapters": [
    {"id":"R01", "title":"入场与委托", "folder":"章节/R01", "script":"穿插对话稿.txt", "name":"R01_入场", "reviewed":true},
    {"id":"R02", "title":"第一次讨论", "folder":"章节/R02", "script":"穿插对话稿.txt", "name":"R02_讨论", "reviewed":true}
  ]
}
```

## 现有脚本与命令

- `scripts/render_dialogue.py`：单稿配音、固定参考声音、分句缓存、异常重配、MP3/SRT。
- `scripts/build_audiobook.py`：章级清单检查、续做与连续版/旧式打包。分段、LRC、动态称呼及checkbox使用项目已验证的编排/后处理工具，不向旧脚本传未实现的参数。

用已安装依赖的Python执行，不用系统Python碰运气。以下 `python` 指该解释器；`SKILL`、`MODELS`、`PROJECT`代表本次解析出的绝对路径，实际调用时用参数数组或正确引用路径。

```text
python SKILL/scripts/build_audiobook.py --manifest PROJECT/制作清单.json --models MODELS --references PROJECT/voices --voices SKILL/assets/voices/声线模板.json --check
python SKILL/scripts/build_audiobook.py --manifest PROJECT/制作清单.json --models MODELS --references PROJECT/voices --voices SKILL/assets/voices/声线模板.json --render --output PROJECT/成品 --batch-size 8
```

第二条是需要现有连续版打包能力时的命令，会按章渲染后打包；它不是分段默认交付必须执行的一步。再次执行会比较脚本哈希与声音指纹，跳过未变成品。默认只读取模型目录下已下载的Base权重，无网络下载。

单章、试听或独立段返工使用单稿渲染；输出到独立目录，保留原版：

```text
python SKILL/scripts/render_dialogue.py --script PROJECT/试听稿.txt --output PROJECT/试听 --models MODELS --references PROJECT/voices --voices SKILL/assets/voices/声线模板.json --name 七声线试听
python SKILL/scripts/render_dialogue.py --script PROJECT/章节/R01/穿插对话稿.txt --output PROJECT/章节/R01 --models MODELS --references PROJECT/voices --voices SKILL/assets/voices/声线模板.json --name R01_入场
```

`--plan`在既有参考声线齐备且不设计新声线时只解析稿件并列缓存，不加载模型或生成音频；`--check`仅检查清单、稿件及参考配置，两者都不等于音频、字幕、播放器或ZIP的完整交付验收。`--assemble-only`只合并已验证缓存，缺少普通台词或停顿缓存会失败，不在合并时补造。不要同时以设计新参考声线的参数冒称纯检查。完整项目已有单章音频时，不加 `--render` 可走现有校验/打包流程。

若确需新设计参考声线：先复制/撰写自定义voices JSON，明确输出到项目目录，用 `--voices ... --references PROJECT/新声线 --design-missing --references-only`；仍需 `--script`、`--output`、`--models`。需本地VoiceDesign权重。本仓库不附参考WAV。首次使用可先执行下面的命令，在项目目录生成参考声音；它会加载模型并实际合成，应在用户要求配音时运行：

```text
python SKILL/scripts/render_dialogue.py --script SKILL/assets/example-dialogue.txt --output PROJECT/voice-setup --models MODELS --references PROJECT/voices --voices SKILL/assets/voices/声线模板.json --design-missing --references-only
```

`MODELS` 下需有 Base 和 VoiceDesign 权重。试听参考WAV及一小段真实对白后，后续渲染、`--plan`、`--check`和打包均传同一个 `--references` / `--voices` 配置。已获认可的项目声音保持不变；更改声线时另建目录。

## 缓存与错误

### 按资源与吞吐调度并发

不固定禁止单GPU多进程，也不因瞬时利用率低就直接增加worker。只有本次授权包含启动TTS时才运行性能短测；文档、纯编排或检查任务不为测吞吐自行加载模型。

1. 确认当前可用显存、GPU利用率与已有任务，记录单任务/现有配置的基线及batch。同机其他工作区或对话可能也启动了模型，按GPU上的实际总进程与占用调度，不能把本项目worker数当作整机并发；资源变化时调整自己负责的作业，不擅自停止其他任务。吞吐可用合格音频秒/墙钟秒或固定任务集完成耗时，比较时保持输入、质量要求与计时口径一致，区分加载预热和稳定生成时间。
2. 用两份互不重叠的小任务短测GPU并发，覆盖本次真实句长分布，包含较长段落，不能只测短句后直接推广到整章。每个worker使用独立cache/output和状态文件，或由统一调度预分配互不重叠的分句及唯一写入者；参考WAV可共享只读。不能让两个进程同时改同一制作状态、覆盖同一分句或重复领取任务。成片仍按冻结清单复原，不按任务完成先后排序。
3. 记录并发时显存峰值、OOM/失败情况、CPU/IO等待及整体吞吐，再决定并发数和batch。显存容量与整体收益优先于瞬时SM百分比；低利用率也可能来自供数或写盘等待。实测有收益且资源允许时可以GPU并行，CPU整理、编码及上游已授权的OCR或下一幕准备也可并行。
4. 并发无收益或出现OOM时，有限回退并发/batch、释放失败worker占用，保留通过校验的缓存，仅重试未完成分句。同时观察首批及尾批的实际产出延迟；高GPU利用率但长时间没有合格分句，也需要排查和重新调度，不能等到报OOM才处理。不把显存接近容量直接断言为唯一原因。不要无限重启或全量重做；质量校验失败仍按下述单句重配上限处理。

渲染使用冻结稿件/配置快照；修改中的下一稿不替换正在渲染的输入。并行任务只写各自负责的产物，汇总方验证脚本哈希、声音指纹和分句完整性后再合并。

让出GPU资源时，优先停止领取新任务，或等本批正常结束后退出worker；工具支持经核实的批间暂停时再使用。不要把强制终止正在执行的CUDA任务当常规调度办法，尤其同GPU还有其他工作。发生CUDA上下文或非法内存访问异常时，让失败进程退出，在干净进程中有限续做并重新校验缓存，不在损坏的上下文里无限重试，也不凭时间上的相邻就认定唯一故障原因。

分句缓存指纹包含模型目录与配置、全部参考WAV内容/参考文本、内部speaker ID和台词；字幕显示名单独记录。更换模型权重时使用新的模型目录；不要在原目录静默替换权重后继续沿用旧缓存。参考文本或WAV改变会失效对应配置的缓存。仅调整播放顺序、分段或字幕称呼时复用未变台词，不重设计声音；成片顺序仍须核回冻结稿件。

`本地配音制作状态.json`记录实际完成分句和成片；只有 `complete`、当前脚本哈希与当前声音指纹匹配才可打包。修改稿件后直接续跑；不手工把状态改成complete。异常废片保存在 `_需重配`，不会放进成品包。单句最多3次尝试；失败会停止当前运行并保留日志，修复原因后续做。

非静音、有限采样、过短或异常拖长检查失败时保留废片，每句最多3次生成尝试（含初次，重试时换种子）；仍失败则停止该句并处理文本/参考音频，不无限重试。用户要求的新声线先做独立试听，不覆盖整章状态。中文普通对话的过短/过长阈值是工程筛查，不证明措辞和生僻姓名都读对。特别检查异常长句、漏读与关键姓名；技术核验报告不得冒充人工全听。

单独一行的纯省略号（如 `……` 或 `...`）保留在稿件和字幕中，以0.65秒明确静音停顿呈现，不送入语音模型反复重试；状态标记为 `written_ellipsis_pause`。只对这类纯省略号分句允许静音，校验其精确时长；普通台词、参考声音和整章仍执行原有非静音检查。`--assemble-only` 缺少停顿缓存也必须失败，不在合并时补造缓存。

逐字用双破折号拉开的装饰台词，如 `——请——核——对——线——索——`，合成输入用字间逗号形成间隔，原词顺序不变；稿件、字幕和缓存身份仍保留原排版。只匹配整句这种装饰格式，不改普通台词里的破折号。实际合成替换记入 `synthesis_normalizations`，原有人声时长及非静音检查保持不变。

## 字幕与成品

当前渲染器的SRT使用模板静态label。需要动态称呼时，后处理按稳定turn映射应用本次显示名，不修改原台词或声音；切成独立段后把LRC/SRT移到当前段的局部时间轴。不要把播放器仅改目录标题当成字幕也已改好。

默认分章/分段成品、可选连续版、播放器过滤与交付验证见[分段播放与交付](segmented-delivery.md)。离线播放器优先相对本地引用；内置浏览器限制file协议时提供本地文件入口或已授权站点，不绕过访问限制。
