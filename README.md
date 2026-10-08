# 多媒體傳達 Skills

以歌曲、旁白、字幕與動畫傳達內容的 Agent Skills。分類為 **多媒體傳達（Multimedia Communication）**，獨立維護，不納入 GIO 類別。

| Skill | 用途 |
| --- | --- |
| [local-narration-song](skills/local-narration-song/SKILL.md) | 本機 MiniMax Music 3 唱指定歌詞；檢查咬字、漏唱與自然度，依最終音訊對齊字幕與畫面，核對實際 MP4 音軌。 |

## 安裝

與 CloudWorkTools 既有 Skill 相同，使用 [skills CLI](https://github.com/vercel-labs/skills)。在要使用的專案執行：

```bash
DISABLE_TELEMETRY=1 npx --yes skills@1.5.24 add CloudWorkTools/multimedia-communication-skills --skill local-narration-song --agent codex --yes
```

加上 `--global` 可供所有專案使用；Claude Code 可將 `--agent codex` 改成 `--agent claude-code`。安裝的是指引、預設及檢查腳本，**不會下載模型或啟動生成**。

## 使用

> 用 $local-narration-song，以 MiniMax Music 3 唱出指定歌詞，優先清楚咬字，再依最終歌聲定位字幕與畫面。保留原稿與設定，核對實際影片開頭、中段、間奏後和結尾的同步。

已安裝的本機 `mm-synth` 與公開 GGUF 權重是必要前置。Python 需 `opencc-python-reimplemented`，媒體核對需 FFmpeg／ffprobe；模型安裝與編譯請依[執行器文件](https://github.com/ServeurpersoCom/minimaxmusic.cpp)。可透過 `MINIMAX_MUSIC3_HOME` 指定環境位置。詳細版本與參數見 [本機流程](skills/local-narration-song/references/local-workflow.md)。

- 原生歌手；目前本機入口沒有指定真人聲音複製功能。
- 自然度與字音仍須聽辨；ASR／字幕吻合不是每字唱對的證明。
- 音訊更換後重新核對時間軸；檢查渲染後的影片，不能只看 HTML 預覽。
- 一般朗讀 TTS 不在本 Skill 的生成範圍；已有旁白可沿用同步原則。
- 不包含私人素材、聲音樣本、案例影片或模型權重。不得將本地生成任務自動換成雲端／公開分享。

## 離線檢查

在有 OpenCC 的 Python 環境執行：

```bash
python skills/local-narration-song/scripts/test_generate_local_song.py
python skills/local-narration-song/scripts/check_song.py --self-test
```

這兩項不載入模型、不執行 GPU 生成。生成入口測試使用臨時假檔案，驗證 dry-run 無寫入、禁止覆寫、無效參數與缺少模型的拒絕行為；它不證明推論成功。

公開程式與指引採 MIT；第三方 runtime、模型與工具依其各自授權。GPU／記憶體與耗時紀錄是單一實測環境，不是最低硬體需求。
