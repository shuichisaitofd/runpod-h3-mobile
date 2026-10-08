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

`/workspace` はネットワークボリュームなので、同じボリュームをつなげば ComfyUI もモデルも残っています。その場合、`restore.sh` は「既にある」と判断して、ほとん'何もダウンロードしません(確認のため、モデルの sha256 計算に10〜20分かかります)。
