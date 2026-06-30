# Heartbeat Companion / 心跳陪伴

让 Shinsekai 当前角色在用户安静一段时间后主动开口。每次心跳会按权重选择：

- 复用 Moondream Vision 查看屏幕并回应；
- 按当前角色人设说一两句自言自语；
- 结合当前时间主动问用户一个简短问题。

用户发送任何正常消息后，下一次心跳会重新等待完整间隔。

> Target: Shinsekai 2.1.0+ · Version: 0.1.0 · License: MIT

## 安装

将仓库内容安装为：

```text
Shinsekai/plugins/heartbeat_companion/
```

在 `data/config/plugins.yaml` 中登记：

```yaml
- entry: plugins.heartbeat_companion.plugin:HeartbeatCompanionPlugin
  enabled: true
```

然后完整重启 Shinsekai。首次加载会创建：

```text
data/plugins/io.github.hard_to_tell.heartbeat_companion/config.json
```

## 配置

直接编辑生成的 `config.json`；插件每秒检查文件，保存后无需重启：

```json
{
  "enabled": true,
  "interval_minutes": 10,
  "mode_weights": {
    "screen": 50,
    "monologue": 25,
    "question": 25
  },
  "monitor_index": -1,
  "screen_question": "In one short sentence, describe what the user appears to be doing on screen.",
  "monologue_instruction": "Keep the current character persona and naturally say one or two short sentences.",
  "question_instruction": "Considering the current local time, naturally ask the user one short question."
}
```

- `interval_minutes`：允许 `0.1–1440`，默认 10 分钟。
- `mode_weights`：三个非负权重；设为 `0` 可关闭对应模式。
- `monitor_index`：`-1` 沿用 Moondream Vision 设置；也可指定显示器序号。
- 全部权重为 `0` 时自动使用自言自语。
- JSON 暂时写坏时会保留上一份有效配置，修正并保存即可。

心跳触发会作为一条简短用户消息显示在聊天记录中，角色回复继续使用当前 LLM、聊天窗和 TTS。

## 可选识屏

识屏模式依赖单独安装并启用的 [Shinsekai Moondream Vision](https://github.com/RachelForster/Shinsekai-Moondream-Vision)。本插件会寻找它注册的 `moondream_query_screen` 工具，不复制模型代码，也不增加视觉依赖。

建议关闭 Moondream Vision 自身的自动监屏触发，只保留插件与识屏工具，避免两个插件同时主动说话。Moondream 缺失、模型仍在加载或推理失败时，本次心跳会立即降级为自言自语或提问。

视觉推理期间如果用户发了新消息，推理结果会被丢弃，心跳重新计时。

## 开发与测试

使用 Shinsekai 2.1.0 自带 Python：

```powershell
& C:\path\to\Shinsekai\runtime\python.exe -m unittest discover -s tests -v
```

本插件没有直接的第三方运行时依赖。

## English

Heartbeat Companion lets the current Shinsekai character speak after the user has been idle for a configurable period. Each heartbeat uses weighted random selection between screen context, a short in-character monologue, and a time-aware question.

Install the repository as `plugins/heartbeat_companion`, add the manifest entry shown above, restart Shinsekai, and edit the generated JSON configuration. Screen understanding is an optional integration with the separately installed Moondream Vision plugin; failures automatically fall back to a non-visual heartbeat.

User input resets the idle timer. If the user speaks while a screen query is running, that heartbeat is cancelled.

## Publication metadata

- Plugin ID: `io.github.hard_to_tell.heartbeat_companion`
- Entry: `plugins.heartbeat_companion.plugin:HeartbeatCompanionPlugin`
- Author: `Hard-to-tell`
- Repository: `https://github.com/Hard-to-tell/shinsekai-heartbeat`
- Minimum Shinsekai version: `>=2.1.0`
- Tags: `heartbeat`, `companion`, `automation`, `vision`
