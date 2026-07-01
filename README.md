# 心跳陪伴（Heartbeat Companion）

让 Shinsekai 当前角色在用户空闲一段时间后主动开口。插件会随机选择识屏、自言自语或主动提问模式；用户正常发送消息、角色回复完成、TTS 播放完成后都会重新计时，避免在对话进行中插入新的心跳。

适用于 Shinsekai 2.1.0 及以上版本。插件本身没有额外 Python 运行时依赖。

## 功能

- 空闲一段随机时间后，让当前角色主动说话。
- 支持三种触发模式：识屏、自言自语、主动提问。
- 支持 Shinsekai 插件配置页，不需要手动编辑 JSON。
- 配置保存后会写回 `config.json`，通常无需重启即可热加载。
- 可选调用 Moondream Vision 的 `moondream_query_screen` 工具；未安装或识屏失败时会自动回退到非识屏模式。
- 避免连续重复相同模式、固定问题或语气词。
- 角色正在生成回复或播放 TTS 时暂停心跳触发。

## 安装

### 从插件市场安装

如果 Shinsekai 的插件管理器里已经能看到 Heartbeat Companion，优先直接从插件市场安装。安装后重启 Shinsekai。

### 手动安装

1. 在本仓库页面点击 **Code -> Download ZIP**，下载后解压。
2. 打开 Shinsekai 主程序目录里的 `plugins` 文件夹。
3. 新建文件夹 `heartbeat_companion`，把解压出来的插件文件复制进去。

复制完成后应类似：

```text
Shinsekai/
└─ plugins/
   └─ heartbeat_companion/
      ├─ plugin.py
      ├─ config.py
      ├─ runtime.py
      ├─ scheduler.py
      └─ ...
```

4. 打开 `Shinsekai/data/config/plugins.yaml`，在文件末尾加入：

```yaml
- entry: plugins.heartbeat_companion.plugin:HeartbeatCompanionPlugin
  enabled: true
```

不要删除文件里已有的其他插件。保存后完整关闭并重新启动 Shinsekai。

首次成功加载后会自动生成配置文件：

```text
Shinsekai/data/plugins/io.github.hard_to_tell.heartbeat_companion/config.json
```

## 配置

### 推荐方式：插件配置页

安装并重启 Shinsekai 后，进入插件管理器，找到 **Heartbeat Companion**，点击配置按钮。配置页提供以下项目：

- 启用或关闭心跳陪伴。
- 设置最短和最长空闲时间。
- 设置识屏、自言自语、提问三种模式的相对权重。
- 设置回复句数范围。
- 设置显示器索引。
- 编辑识屏、自言自语、提问提示词。
- 编辑固定问题列表和常用语气词/动作列表，每行一条。
- 设置使用固定问题和附加语气词的概率百分比。

保存后插件会把表单内容转换回原来的 `config.json` 格式。只修改这些配置通常会自动生效；更新插件代码或版本后仍建议重启 Shinsekai。

### 手动方式：编辑 config.json

也可以直接编辑：

```text
Shinsekai/data/plugins/io.github.hard_to_tell.heartbeat_companion/config.json
```

默认结构如下：

```json
{
  "enabled": true,
  "interval_minutes_range": [5, 15],
  "mode_weights": {
    "screen": 50,
    "monologue": 25,
    "question": 25
  },
  "reply_sentence_range": [1, 4],
  "monitor_index": -1,
  "screen_question": "In one short sentence, describe what the user appears to be doing on screen.",
  "monologue_instruction": "Keep the current character persona and say something naturally.",
  "question_instruction": "Considering the current local time, naturally ask the user a question.",
  "fixed_question_chance": 0.45,
  "fixed_questions": [
    "这么晚了，为什么还不睡？",
    "今天过得怎么样？",
    "忙了这么久，要不要休息一下？"
  ],
  "expression_chance": 0.35,
  "common_expressions": [
    "唔……",
    "嗯哼~",
    "（轻轻叹气）",
    "😊"
  ]
}
```

主要字段：

- `enabled`：是否启用插件。
- `interval_minutes_range`：随机空闲时间范围，单位是分钟，例如 `[10, 30]`。
- `mode_weights`：三种模式的抽取权重；某一项设为 `0` 就会关闭该模式。
- `reply_sentence_range`：请求回复的句数范围。
- `monitor_index`：`-1` 表示沿用 Moondream Vision 的显示器设置；`0` 到 `32` 可强制指定显示器。
- `screen_question`：识屏模式发送给 Moondream 的问题。
- `monologue_instruction`：自言自语模式的提示词。
- `question_instruction`：提问模式的提示词。
- `fixed_question_chance`：抽到提问模式时使用固定问题的概率，`0.45` 表示 45%。
- `fixed_questions`：固定问题列表。
- `expression_chance`：附加常用语气词或动作的概率。
- `common_expressions`：常用语气词、动作或 emoji 列表。

编辑 JSON 时请使用英文双引号，项目之间用英文逗号，最后一项后面不要加逗号。配置写错时，插件会继续使用上一份有效配置。

## 常用配置

快速测试，6 到 12 秒触发一次：

```json
"interval_minutes_range": [0.1, 0.2]
```

关闭识屏，只保留自言自语和提问：

```json
"mode_weights": {
  "screen": 0,
  "monologue": 50,
  "question": 50
}
```

关闭固定问题和附加语气词：

```json
"fixed_question_chance": 0,
"expression_chance": 0
```

临时关闭插件：

```json
"enabled": false
```

## 可选识屏

识屏需要另外安装并启用 [Shinsekai Moondream Vision](https://github.com/RachelForster/Shinsekai-Moondream-Vision)。Heartbeat Companion 只调用它提供的 `moondream_query_screen` 工具，不会自己保存截图或识屏结果。

如果 Moondream Vision 未安装、模型仍在加载、工具报错或识屏返回为空，本插件会自动改用自言自语或提问模式。

建议关闭 Moondream Vision 自带的自动监屏触发，只保留识屏工具，避免两个插件同时主动说话。

## 使用说明

- 心跳触发文本会进入当前对话流程，继续使用当前角色、LLM、输出解析器、UI 和 TTS 设置。
- 每次用户发送消息、角色回复完成、TTS 播放结束或跳过语音后，都会重新等待一个完整随机间隔。
- 插件会尽量避免连续抽到同一个模式、固定问题或语气词；如果列表只有一项，则只能继续使用这一项。
- 修改配置通常无需重启；修改插件代码或更新版本后需要重启 Shinsekai。

## 更新

如果插件目录是 Git 仓库：

```powershell
git pull
```

如果想固定到某个发布版本：

```powershell
git fetch --tags
git checkout v0.3.0
```

如果通过 Shinsekai 插件管理器安装，请优先使用插件管理器的更新功能。

## 开发验证

运行标准库测试：

```powershell
python -m unittest
```

本仓库还包含：

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)：插件运行结构说明。
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)：本地集成和发布检查流程。

## License

MIT
