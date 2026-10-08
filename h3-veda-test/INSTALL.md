# H3 Veda テスト版(画像から動画のみ)

スマホのH3 Mobileの画面で、Vedaのオン/オフと数値(スパース率)を変えられるテスト用ページです。
本番のアプリ(ComfyUI-H3-Mobile)と `i2v.json` は変更しません。入れるのは新しいフォルダ `ComfyUI-H3-Veda-Test` だけです。

## Podに入れる(2行)
Veda(Veda-on-ComfyUI とモデル)が入っているPodで、Claudeのターミナルに次を渡す。

```
git clone -b h3-veda-test https://github.com/shuichisaitofd/runpod-h3-mobile.git /workspace/runpod-slim/_veda_test
bash /workspace/runpod-slim/_veda_test/h3-veda-test/install.sh
```

ComfyUIが再起動します(1〜2分)。生成中に実行しないこと。

## 使う
- いつものアプリのURLの末尾を `/h3-veda/` にして開く(例: `https://xxxx-8188.proxy.runpod.net/h3-veda/`)。
- 画面は普通のアプリと同じ。右下に「Veda OFF」のボタンが出る。押すと、OFF/ON、数値のスライダー、40/70/80/90のボタンが出る。
- 設定は次の生成から効く。設定はこの端末のブラウザに残る(最初は OFF)。
- 対象は「画像から動画」だけ。「参照から動画」には効かない。
- 普通のアプリ(`/h3-mobile/`)は、これまで通りで、Vedaは入らない(Pod側の `i2v.json` が元のままの場合)。

## 外す
```
bash /workspace/runpod-slim/_veda_test/h3-veda-test/install.sh --remove
```

## しくみ
ページを開くたびに、本番の画面(index.html)を読み、Vedaのパネル(veda-panel.js)を足して返す。パネルは、ブラウザ内で、画像から動画のワークフローを受け取った直後に、Vedaノードを足す/外す。サーバーのファイルは書き換えない。
