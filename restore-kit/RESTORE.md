# H3 復旧手順(新しいPodで)

このキットは、Podを終了したあとで、ComfyUI を今の状態(v0.38.0 + Veda + 差し替え高速ワークフロー)に戻すためのものです。
**`/start.sh`、`/workspace/runpod-slim/ComfyUI/.runpod-bundle-version`、アプリの本番 `i2v.json` は触りません。**

## かんたん版(コマンド2〜3回)

1. 新しいPodを起動し、JupyterLab かターミナルを開く。
2. キットを取り出す(どちらか一方):
   ```
   git clone -b h3-restore-kit https://github.com/shuichisaitofd/runpod-h3-mobile.git /workspace/runpod-slim/_kit && cp -r /workspace/runpod-slim/_kit/restore-kit /workspace/runpod-slim/restore_kit
   ```
   (GitHub に置けなかった場合は、保存した `restore_kit.tar.gz` を `/workspace/runpod-slim/` にアップロードして `cd /workspace/runpod-slim && tar xzf restore_kit.tar.gz`)
3. まず試運転(何も変えず、やることだけ表示):
   ```
   bash /workspace/runpod-slim/restore_kit/restore.sh --dry-run
   ```
4. 問題なければ本番(モデルのダウンロードで時間がかかります):
   ```
   bash /workspace/runpod-slim/restore_kit/restore.sh
   ```

`/workspace` はネットワークボリュームなので、同じボリュームをつなげば ComfyUI もモデルも残っています。その場合、`restore.sh` は「既にある」と判断して、ほとんど何もダウンロードしません(確認のため、モデルの sha256 計算に10〜20分かかります)。

## 手順の中身(自分で順に行いたいとき)

### 1. ComfyUI を v0.38.0 にする
```
cd /workspace/runpod-slim/ComfyUI
git rev-parse HEAD > /workspace/runpod-slim/restore_backup_git_head.txt                      # 戻す控え(先に取る)
.venv-cu128/bin/pip freeze > /workspace/runpod-slim/restore_backup_pip_freeze.txt          # 戻す控え
git fetch origin tag v0.38.0 && git checkout v0.38.0
PIP_CONSTRAINT=/opt/comfyui-runtime-constraints.txt .venv-cu128/bin/pip install --dry-run -r requirements.txt
```
`--dry-run` の `Would install` の行に **torch / torchvision / torchaudio が出ないこと**を確かめる。出たら進まない。問題なければ `--dry-run` を外して実行。
確認: `git -C /workspace/runpod-slim/ComfyUI describe --tags` → `v0.38.0`

### 2. Veda をコミット 60bfae6 で入れる
```
cd /workspace/runpod-slim/ComfyUI/custom_nodes
git clone https://github.com/veda-sparse/Veda-on-ComfyUI.git
git -C Veda-on-ComfyUI checkout 60bfae6
```
確認: `git -C /workspace/runpod-slim/ComfyUI/custom_nodes/Veda-on-ComfyUI log --oneline -1` → `60bfae6 release: 0.3.0`

### 3. モデルのダウンロード
`MODELS.md` の表のとおり(約 66.6 GB)。`restore.sh` が `models.tsv` を読んで、取得・サイズ確認・sha256確認まで自動で行います。
確認: `cd /workspace/runpod-slim/ComfyUI/models && sha256sum loras/h3_character_swap_pro4500_1000.safetensors` → `4b2a3f42…4e79` で始まる値(MODELS.md と同じ)

### 4. ワークフローの配置
- 画面用: `workflows/H3_CharacterSwap*.json` → `ComfyUI/user/default/workflows/`
- API形式: `workflows/*.json` → `/workspace/runpod-slim/`
- 作業スクリプト: `tools/*` → `/workspace/runpod-slim/`
- アプリ用 Veda 入り(90/80/70): `app_workflows/i2v.json.veda90` など → `ComfyUI/custom_nodes/ComfyUI-H3-Mobile/api_workflows/`(**本番の `i2v.json` には上書きしない**)
確認: `cd /workspace/runpod-slim/restore_kit/app_workflows && sha256sum -c SHA256SUMS`(配置先でも同じ表で確認可)

### 5. 切り替えコマンドの設置
`bin/veda_on`、`veda_on80`、`veda_pct`、`veda_off`、`veda_status` → `/workspace/bin/`(`chmod +x`)。
確認: `/workspace/bin/veda_status` → 「状態: …」が表示される
(使い方: `veda_on`=90%、`veda_on80`=80%、`veda_pct 70`=任意の%、`veda_off`=元に戻す)

### 6. ComfyUI の再起動
```
bash /workspace/runpod-slim/restore_kit/restart_comfyui.sh
```
確認: `curl -s http://127.0.0.1:8188/system_stats | head -c 100` → JSON が返る(起動に1〜2分)。画面でワークフロー `H3_CharacterSwap_Fast` を開く。

## 入っていないもの
元動画・人物画像(自分の素材は別途アップロード)、生成した動画、モデル本体、`/workspace/.claude`、ログイン情報・鍵類。
アプリ(ComfyUI-H3-Mobile)本体は Pod のテンプレートに含まれるものを使います。
元に戻したいとき: ComfyUI は `restore_backup_git_head.txt` のコミットに `git checkout` する。
