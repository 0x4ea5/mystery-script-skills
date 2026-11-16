# 运行环境与模型

技能说明可直接用于资料整理和主持准备；运行配音脚本需要另行准备Python环境、依赖和本地模型。本仓库不附虚拟环境、模型权重或参考WAV，也不假设已经配置GPU。

## 依赖与检查

- 使用项目虚拟环境。渲染脚本依赖 `qwen-tts`、PyTorch、NumPy、soundfile、imageio-ffmpeg；打包脚本依赖后面三项。模型依赖按官方兼容要求安装。
- 官方来源：[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)、[Base模型](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base)、[VoiceDesign模型](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign)、[PyTorch安装](https://pytorch.org/get-started/locally/)。安装时核对当前说明，不照搬其他机器的CUDA或版本。
- `--models` 指向模型根目录，其下使用 `Qwen3-TTS-12Hz-1.7B-Base/`；设计新参考声音时另需同级 `Qwen3-TTS-12Hz-1.7B-VoiceDesign/`。提前完整下载权重及配置；渲染脚本使用离线模式，不负责下载。
- 确认 `torch.cuda.is_available()`、实际可用显存及脚本使用的数据类型/设备。现有渲染路径以CUDA和BF16为目标，未验证CPU或所有显卡；没有兼容环境时先交对白与制作清单。
- 包内只有DM与P1—P6的中性设计配置。录音由用户提供，或按[执行流程](pipeline.md)先生成参考WAV，再试听确认。语音性别不代表角色身份。

## 缓存、并发和交付

每个任务使用自己的输出、状态与缓存目录；batch和并发依当前显存及真实吞吐选择。不要让多个进程争写同一分句或状态。

只有当堆栈确认缓存或临时目录写入受阻时，再把该次进程的 `NUMBA_CACHE_DIR`、`TEMP` / `TMP` 指向项目可写目录；不修改全局环境，也不因单条可选依赖提示重装环境。

成品默认保存在本项目。远端站点、网盘、NAS及媒体库位置按用户本次指定或仍有效授权确定，不继承其他用户的上传许可。复制完成、媒体服务扫描及客户端歌词显示分别核验，见[交付约定](segmented-delivery.md)。
