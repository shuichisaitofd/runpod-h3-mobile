# 必要なモデル一覧

置き場所は `ComfyUI/models/` からの相対パス。`restore.sh` が `models.tsv`(同じ内容)を読んで自動で取得し、sha256 で確認します。
サイズ・sha256 は Hugging Face の公開情報と、このPod上の実ファイルの両方で一致を確認済みです。

| ファイル(置き場所) | 用途 | サイズ | 取得元(Hugging Face) | sha256 |
|---|---|---|---|---|
| `diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 差し替え(Ref2VA)本体 | 20.97 GB | `Comfy-Org/MiniMax-H3` の `diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors` | `9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779` |
| `diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors` | アプリの I2V 本体 | 20.97 GB | `Comfy-Org/MiniMax-H3` の `diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a` |
| `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | テキストエンコーダ(共通) | 15.69 GB | `Comfy-Org/MiniMax-H3` の `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6` |
| `vae/minimax_h3_video_vae_fp16.safetensors` | 動画VAE(共通) | 5.21 GB | `Comfy-Org/MiniMax-H3` の `vae/minimax_h3_video_vae_fp16.safetensors` | `7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522` |
| `vae/minimax_h3_audio_vae_fp32.safetensors` | 音声VAE(共通) | 0.61 GB | `Comfy-Org/MiniMax-H3` の `vae/minimax_h3_audio_vae_fp32.safetensors` | `8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48` |
| `loras/h3_character_swap_pro4500_1000.safetensors` | 差し替えLoRA(強さ1.0) | 0.16 GB | `akatz-ai/MiniMax-H3-Character-Swap-LoRA` の `h3_character_swap_pro4500_1000.safetensors` | `4b2a3f420ae804c0aa3422761ff84dbd1bf52eef6900ffab6d2e66df63cb4e79` |
| `loras/minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors` | 公式Turbo 8ステップLoRA | 1.96 GB | `lightx2v/Minimax-h3-Turbo` の `minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors` | `6a56f41ab4229c9dd845b9501bbd475ee57e112d846cf2e819d534a1ae928c5a` |
| `loras/minimax_h3_turbo_v4_step600_ema.safetensors` | アプリのTurbo LoRA | 0.78 GB | `larryvrh/MiniMax-H3-Turbo-Lora` の `minimax_h3_turbo_v4_step600_ema.safetensors` | `5f3a626cd72c93a8b9318d6760c510bc5092d2ab13aaba1f932c5bab07a416d3` |
| `veda/minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors` | Veda予測器(アプリのVeda用) | 0.28 GB | `Veda-Sparse/Minimax-H3-T2VA-Veda-8NFE-600Step-Preview` の `minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors` | `2a8d8845c5342756a2781e8e69563940e4bb573c9a40ebb534915ff8fd76573a` |

合計: 約 **66.6 GB**(ダウンロード時間の目安: 100〜300 MB/s なら 4〜12 分、遅い場合は最大1時間強)。

## 入れていないもの
- INT8の動画VAE(`vae/minimax_h3_video_vae_int8_convrot.safetensors`、2.8 GB): 今のワークフローは fp16 の動画VAEを使うため不要。公式テンプレートを使うときだけ、`Comfy-Org/MiniMax-H3` の `vae/` から取得。
- 他のLoRA(アプリ用の各種LoRAなど): 今回の復旧対象外。
