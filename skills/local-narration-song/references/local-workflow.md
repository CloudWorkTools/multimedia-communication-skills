# MiniMax Music 3 本機流程與參數

目前採用原生歌手，指定歌詞優先。成功案例為木吉他民謠流行：90 BPM、C major、4/4，溫暖男聲、柔和鋼琴／貝斯／刷鼓、從容中文咬字。完整配方與同步流程見 [audio-video-sync.md](audio-video-sync.md)；新歌須重新核對。

## 本機環境

- 執行器：`$MINIMAX_MUSIC3_HOME/source/build/mm-synth`，commit `06668b14ab87c106127c9012411aecde92d2c03b`；CUDA，CLI 固定 STRICT 分階段載入。
- 權重：同 base 下 `models/`，LM／depth／DiT 為 Q8，condition／vocoder 為 F32；revision `d4f7a6402a4ca10c8b3ca2f648c8a46c103558bc`，安裝時保存下載 revision／SHA-256 清單；案例紀錄檔名為 `download_manifest.json`，不隨本包附帶。
- `MINIMAX_MUSIC3_HOME` 可指定執行器 base，預設 `~/.local/share/minimax-music3`。其下需有 `source/build/mm-synth`、`models/`、`gpu_library_paths.txt`；最後一個檔案放本機所需 GPU 動態庫搜尋路徑。不刪除其他工具共用的 CUDA 庫。
- Python 需要 `opencc-python-reimplemented`；核對媒體需要 `ffprobe`／FFmpeg。建議用目前專案已有環境；缺少時另建 venv，不修改系統 Python。ASR／Demucs 只在需要診斷時用目前專案已安裝工具，不依賴舊唱歌模型權重。
- 案例用 HDEMUCS_HIGH_MUSDB_PLUS 分軌、large-v3-turbo 辨識。這些模型、工具環境與權重不隨 Skill 安裝。
- 已實測 16GB RTX 4060 Ti 可跑短版，首版約 128 秒、修訂版約 192 秒；完整修訂版在同卡生成耗時 346.6 秒，音樂上限 180 秒、max-seq 8192，實際歌曲 103.201 秒；這不是其他歌詞的耗時保證。C++ 路線實際輸出 44.1kHz 立體聲，與官方示例的 32kHz 有差異，不能混用 metadata。

## 生成入口

保留繁體原稿；`[Verse]`、`[Chorus]`、`[Bridge]` 等標籤獨立一行。複製 [預設請求](minimax-default.json) 作新候選 JSON，以 caption／參數調整，不改已採用請求。

```bash
python \
  "/絕對路徑/skill/scripts/generate_local_song.py" \
  --lyrics /絕對路徑/歌詞.txt --out /絕對路徑/新候選 \
  --request /絕對路徑/請求.json --duration 180 --check
# 核對後移除 --check，執行本機推論。
```

helper 只產生原始 `song.wav`／replay `song.json`、精確設定與日誌，尚未完成音量、辨識、字幕或影片。`duration` 是音樂碼生成上限，EOS 可能提早停止；目前 C++ 實際輸出時間亦與上限略有差異，必須 ffprobe。helper 防誤用範圍 10–300 秒，不是所有 runtime 的通用範圍。長曲需同時核對文字 token、音樂碼及 KV context，不把調大上限當成一定能唱完。

## 參數搭配

| 調整 | 方式與作用 | 目前基準／合理比較 |
| --- | --- | --- |
| 音樂風格 | caption 的 Global Metadata；genre、BPM、key、拍號、情緒 | acoustic folk pop，90 BPM，C major，4/4 |
| 咬字 | Vocal Details 的文字引導，沒有獨立數值清晰度旋鈕 | `exceptionally clear standard Mandarin pronunciation, unhurried syllables, smooth connected vowels, comfortable mid-range` |
| 配器／遮字 | Arrangement 指定稀疏編制、歌聲前置、克制過門 | 吉他、柔和鋼琴、貝斯、輕刷鼓；避免自行加入 Solo／長間奏標籤 |
| 男／女聲與音色 | caption 描述 warm male／clear female 等 | 可引導，無指定人聲複製輸入；seed 也不是固定歌手 ID |
| `lm_cfg` | 語言模型與 depth 解碼的條件引導，影響音樂碼選擇 | 1.5；必要時單獨比較 1.3／1.7，效果需聽辨，不是越大越清楚 |
| `lm_top_k` | LM 條件分支的候選排序／取樣範圍 | 50；25／75 可作單變因探索，較少候選不保證少錯字 |
| `dit_cfg` | 合成階段的條件引導 | 1.7；先試 1.5／1.9，觀察金屬感／音色／混音，不能保證修正漏唱 |
| `steps` | 每個合成視窗的 Euler 步數 | 30；必要時比較 40，時間增加且品質未必提升 |
| `lm_seed` | 音樂碼取樣種子 | 42；換它通常改旋律、節奏與唱法，不盲目換 seed |
| `seed` | 合成噪音種子 | 42；可配合 replay 固定碼比較聲音合成，不等於固定聲線 |
| `audio_codes` | 執行器 replay 固定音樂碼，再合成 | 適合只調 steps／dit_cfg／seed；不能修正既有碼中的漏句。helper 的新歌詞入口不接受，需直接用 CLI 跑 replay JSON |
| batch | 歌曲／同碼合成變體數 | 本機固定 1，減少 RAM／VRAM 峰值 |
| 輸出／峰值 | wav32 保留原始 float；其他格式的 peak_clip 是百分位正規化 | 原始 wav32、peak_clip 0；另做有限值、削波及 true peak 檢查後輸出 WAV／MP3 |

本機 request.h／request.cpp 沒有 temperature、top_p、negative_prompt、reference_audio 或 pronunciation-dictionary 欄位；不要套用別的框架參數。CFG、top-k、步數的比較值是探索規劃，尚未實測最優。

## 建議比較順序

先採已接受風格。要更清楚時，固定歌詞、seed 與全部數值，只強調自然的逐音節咬字、短句尾換氣、單一主唱與稀疏伴奏，避免把唱歌提示成機械念字。需要比較風格再依序做：溫暖木吉他民謠、較明亮鋼琴流行、輕快木吉他流行；每版先用相同代表短段測咬字與異音。速度可比較 90／100 BPM，但不保證實際速度符合。選定風格後才測數值參數，不做全部組合搜尋。

## 後處理、辨識與影片

保留原始音檔。完成混音以整曲增益／必要的音量處理預留峰值，不分段各自正規化。輸出 WAV／MP3，FFmpeg 解碼檢查。需要分軌時重用目前專案的本機分軌工具，確認輸入與新輸出目錄；本包不包含 Demucs 執行器。

ASR 使用已快取模型、temperature=0、condition_on_previous_text=False、word_timestamps=True、language=zh，不給目標提示。重用目前專案的本機辨識工具；低可信樂句裁切重辨並加回 offset。本包不包含 Whisper 執行器。

```bash
python \
  "/絕對路徑/skill/scripts/check_song.py" \
  --lyrics /絕對路徑/生成設定.json --asr /絕對路徑/混音辨識.json \
  --subtitles /絕對路徑/歌唱字幕.srt --audio /絕對路徑/完整混音.wav \
  --report /絕對路徑/歌唱核對.json
```

影片沿用目前專案核定畫面與已安裝工具；案例固定 HyperFrames 0.8.127、GSAP 3.14.2，不代表所有專案都必須採用。核對實際命令離線行為，關閉遙測、更新、自動安裝，按本輪歌曲實際句界重新產生字幕與各鏡時間，不能沿用舊模型或另一個 seed 的錨點。渲染與檢查按專案 README，不使用 usage／feedback／publish／cloud 或讀登入憑證。

來源：[官方模型與 caption 三部分](https://huggingface.co/MiniMaxAI/MiniMax-Music3)、[本機執行器參數及 replay](https://github.com/ServeurpersoCom/minimaxmusic.cpp/blob/main/docs/ARCHITECTURE.md)。本機行為以已固定 commit 的 source 為準。
