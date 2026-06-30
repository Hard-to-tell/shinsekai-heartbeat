# 心跳陪伴（Heartbeat Companion）

让 Shinsekai 当前角色在用户安静一段时间后主动开口。插件会随机选择识屏、自言自语或主动提问；用户正常讲话后会重新计时。角色正在生成回复或播放 TTS 时不会插入新的心跳。

适用于 Shinsekai 2.1.0 及以上版本。插件本身不需要安装额外的 Python 依赖。

## 安装

1. 在本仓库页面点击 **Code → Download ZIP**，下载后解压。
2. 打开 Shinsekai 主程序所在文件夹，再打开其中的 `plugins` 文件夹。
3. 新建文件夹 `heartbeat_companion`，把解压出来的全部文件复制进去。

复制完成后必须是下面这种结构，不能再多套一层文件夹：

```text
Shinsekai/
└─ plugins/
   └─ heartbeat_companion/
      ├─ plugin.py
      ├─ config.py
      ├─ scheduler.py
      └─ ...
```

4. 用记事本打开 `Shinsekai/data/config/plugins.yaml`，在文件末尾加入：

```yaml
- entry: plugins.heartbeat_companion.plugin:HeartbeatCompanionPlugin
  enabled: true
```

不要删除文件里原有的其他插件。保存后完整关闭并重新启动 Shinsekai。

首次成功加载会自动生成配置文件：

```text
Shinsekai/data/plugins/io.github.hard_to_tell.heartbeat_companion/config.json
```

## 修改配置

用记事本打开上面的 `config.json`。保存后插件通常会在 1 秒内读取新配置，不需要重启。

默认配置如下：

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
    "嗯哼～",
    "（轻轻叹气）",
    "😊"
  ]
}
```

主要字段：

- `interval_minutes_range`：随机间隔的最短和最长分钟数，例如 `[10, 30]`。
- `mode_weights`：识屏、自言自语、提问的抽取权重；某项设为 `0` 就会关闭。
- `reply_sentence_range`：回复句数范围，可设为 1–8。
- `fixed_questions`：可自由增删固定问题。
- `fixed_question_chance`：抽到提问模式时使用固定问题的概率，`0.45` 表示 45%。
- `common_expressions`：可添加语气词、动作、颜文字或 emoji。
- `expression_chance`：使用上面表达的概率。
- `monitor_index`：`-1` 表示沿用 Moondream Vision 的显示器设置。

插件会尽量避免连续抽到相同的模式、固定问题和表达。如果某个列表只有一项，则只能继续使用这一项。

### 常用改法

快速测试（6–12 秒触发一次）：

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

关闭固定问题和附加表达：

```json
"fixed_question_chance": 0,
"expression_chance": 0
```

编辑 JSON 时注意：文字使用英文双引号，项目之间使用英文逗号，最后一项后面不要加逗号，也不能写注释。建议修改前先复制一份配置作为备份。配置暂时写错时，插件会继续使用上一份有效配置。

## 可选识屏

识屏需要另外安装并启用 [Shinsekai Moondream Vision](https://github.com/RachelForster/Shinsekai-Moondream-Vision)。本插件只调用它提供的 `moondream_query_screen` 工具；未安装、模型仍在加载或识屏失败时，会自动改为自言自语或提问。

建议关闭 Moondream Vision 自带的自动监屏触发，只保留识屏工具，避免两个插件同时主动说话。识屏期间如果用户发了消息，本次心跳会被取消。

## 使用说明

- 心跳触发文本可在聊天窗口右上角设置菜单的 **对话历史记录** 中查看，不会显示在中央角色对白框。
- 每次用户消息、角色回复/对白播放完成后，都会重新等待一整个随机间隔。
- 修改插件代码或更新插件版本后需要重启；只修改 `config.json` 不需要重启。
- 如需暂时关闭，在配置中把 `"enabled"` 改为 `false`。
