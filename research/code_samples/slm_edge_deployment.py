#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
小規模言語モデル（SLM）エッジデバイス実装サンプル
================================================

このスクリプトは、Raspberry PiなどのエッジデバイスでONNX変換された
小規模言語モデル（SLM）を実行するためのサンプルコードです。
REST APIサーバーとして機能し、テキスト生成リクエストを処理します。

必要なライブラリ:
- onnxruntime 1.14.0+
- transformers 4.30.0+
- Flask 2.0.0+
- numpy 1.22.0+

注意: エッジデバイスの性能に合わせてバッチサイズ、シーケンス長を調整してください。
"""

import os
import time
import json
import logging
import argparse
import threading
import numpy as np
from typing import Dict, List, Optional, Union, Tuple
from pathlib import Path

import onnxruntime as ort
from transformers import AutoTokenizer
from flask import Flask, request, jsonify

# ロギング設定
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# グローバル変数
global_model = None
global_tokenizer = None
global_session = None
global_model_info = {}

app = Flask(__name__)


class ONNXSLMModel:
    """ONNX変換された小規模言語モデルの推論クラス"""

    def __init__(
        self,
        model_path: str,
        tokenizer_path: Optional[str] = None,
        device: str = "cpu",
        optimization_level: int = 99,
    ):
        """
        初期化関数

        Args:
            model_path: ONNXモデルファイルのパス
            tokenizer_path: トークナイザーのパス。Noneの場合はmodel_pathを使用
            device: 実行デバイス（'cpu' または 'cuda'）
            optimization_level: ONNXランタイムの最適化レベル
        """
        self.model_path = Path(model_path)
        self.tokenizer_path = Path(tokenizer_path) if tokenizer_path else self.model_path.parent
        self.device = device.lower()

        # システム情報の取得
        self.system_info = self._get_system_info()
        logger.info(f"システム情報: {self.system_info}")

        # トークナイザーの読み込み
        self.load_tokenizer()

        # ONNXセッションオプションの設定
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = optimization_level
        session_options.enable_cpu_mem_arena = True
        session_options.enable_mem_pattern = True

        # スレッド数の設定（エッジデバイスの場合は少なめに）
        session_options.intra_op_num_threads = min(4, os.cpu_count() or 1)
        session_options.inter_op_num_threads = min(2, os.cpu_count() or 1)

        # エッジデバイスのメモリ制約を考慮
        session_options.enable_mem_reuse = True

        # プロバイダー選択
        providers = ["CPUExecutionProvider"]
        if self.device == "cuda" and "CUDAExecutionProvider" in ort.get_available_providers():
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

        logger.info(f"利用可能なプロバイダー: {ort.get_available_providers()}")
        logger.info(f"選択されたプロバイダー: {providers}")

        # ONNXランタイムセッションの作成
        if self.model_path.is_dir():
            # ディレクトリ内のONNXファイルを検索
            onnx_files = list(self.model_path.glob("*.onnx"))
            if not onnx_files:
                raise FileNotFoundError(f"{self.model_path}内にONNXファイルが見つかりません")
            model_file = onnx_files[0]
        else:
            model_file = self.model_path

        logger.info(f"モデルファイル: {model_file}")

        # モデルサイズの確認
        model_size_mb = os.path.getsize(model_file) / (1024 * 1024)
        logger.info(f"モデルサイズ: {model_size_mb:.2f} MB")

        try:
            logger.info(f"ONNXモデルを読み込んでいます: {model_file}")
            self.session = ort.InferenceSession(
                str(model_file),
                sess_options=session_options,
                providers=providers,
            )

            # モデル情報の取得
            self.input_names = [input.name for input in self.session.get_inputs()]
            self.output_names = [output.name for output in self.session.get_outputs()]

            logger.info(f"入力名: {self.input_names}")
            logger.info(f"出力名: {self.output_names}")

            global global_session
            global_session = self.session

        except Exception as e:
            logger.error(f"モデルの読み込みに失敗しました: {e}")
            raise

    def _get_system_info(self) -> Dict:
        """システム情報を取得する"""
        import platform
        import psutil

        try:
            memory = psutil.virtual_memory()
            cpu_info = {
                "count": os.cpu_count(),
                "usage": psutil.cpu_percent(interval=1),
            }

            # Raspberry Piの場合に温度を取得
            temperature = None
            if platform.machine() in ["armv7l", "aarch64"]:
                try:
                    with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                        temp = int(f.read()) / 1000.0
                        temperature = f"{temp:.1f}°C"
                except:
                    pass

            return {
                "platform": platform.platform(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "memory_total_gb": memory.total / (1024**3),
                "memory_available_gb": memory.available / (1024**3),
                "cpu": cpu_info,
                "temperature": temperature,
                "onnxruntime_version": ort.__version__,
            }
        except Exception as e:
            logger.warning(f"システム情報の取得に一部失敗: {e}")
            return {"error": str(e)}

    def load_tokenizer(self):
        """トークナイザーを読み込む"""
        try:
            logger.info(f"トークナイザーを読み込んでいます: {self.tokenizer_path}")
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.tokenizer_path))

            # トークナイザー設定の確認
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            global global_tokenizer
            global_tokenizer = self.tokenizer

            logger.info("トークナイザーを正常に読み込みました")
        except Exception as e:
            logger.error(f"トークナイザーの読み込みに失敗しました: {e}")
            raise

    def generate_text(
        self,
        prompt: str,
        max_length: int = 128,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        num_return_sequences: int = 1,
    ) -> List[str]:
        """
        テキスト生成を実行

        Args:
            prompt: 入力プロンプト
            max_length: 生成する最大トークン数
            temperature: 生成の温度パラメータ
            top_p: top-pサンプリングのパラメータ
            top_k: top-kサンプリングのパラメータ
            num_return_sequences: 生成するシーケンス数

        Returns:
            生成されたテキストのリスト
        """
        # エッジデバイスの制約を考慮してmax_lengthを制限
        max_length = min(max_length, 512)

        start_time = time.time()

        # 入力のトークン化
        inputs = self.tokenizer(
            prompt,
            return_tensors="np",
            padding=True,
            truncation=True,
            max_length=max_length,
        )

        input_ids = inputs["input_ids"]
        attention_mask = inputs["attention_mask"]

        # デバッグ情報
        logger.info(f"入力トークン数: {input_ids.shape[1]}")
        logger.info(f"入力テキスト: {prompt[:100]}...")

        # メモリ使用量を考慮し、バッチサイズは1に固定
        batch_size = 1

        generated_sequences = []

        try:
            # 自動回帰的生成（トークンごとに繰り返し）
            # 小規模エッジデバイスのための簡易実装
            for i in range(num_return_sequences):
                # 現在の入力ID
                curr_input_ids = input_ids.copy()
                curr_attention_mask = attention_mask.copy()

                # 最大長まで生成
                for _ in range(max_length - curr_input_ids.shape[1]):
                    # 入力の準備
                    onnx_inputs = {
                        "input_ids": curr_input_ids.astype(np.int64),
                        "attention_mask": curr_attention_mask.astype(np.int64),
                    }

                    # 次の単語のロジットを取得
                    outputs = self.session.run(self.output_names, onnx_inputs)

                    # logitsを取得（モデルによって出力形式が異なる場合がある）
                    if isinstance(outputs, dict) and "logits" in outputs:
                        next_token_logits = outputs["logits"][:, -1, :]
                    else:
                        # 一般的なONNXモデルでは最初の出力がlogits
                        next_token_logits = outputs[0][:, -1, :]

                    # サンプリング
                    if temperature == 0:
                        # グリーディ選択
                        next_tokens = np.argmax(next_token_logits, axis=-1, keepdims=True)
                    else:
                        # 温度適用
                        scaled_logits = next_token_logits / max(temperature, 1e-8)

                        # top-k
                        if top_k > 0:
                            indices_to_remove = np.argpartition(scaled_logits, -top_k, axis=-1)[:, :-top_k]
                            scaled_logits[np.arange(scaled_logits.shape[0])[:, None], indices_to_remove] = -float('inf')

                        # top-p
                        if 0 < top_p < 1.0:
                            sorted_logits = np.sort(scaled_logits, axis=-1)[:, ::-1]
                            sorted_indices = np.argsort(scaled_logits, axis=-1)[:, ::-1]
                            cumulative_probs = np.cumsum(np.exp(sorted_logits) / np.sum(np.exp(sorted_logits), axis=-1, keepdims=True), axis=-1)

                            sorted_indices_to_remove = cumulative_probs > top_p
                            sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].copy()
                            sorted_indices_to_remove[:, 0] = 0

                            indices_to_remove = np.zeros_like(scaled_logits, dtype=bool)
                            for batch_idx in range(batch_size):
                                indices_to_remove[batch_idx, sorted_indices[batch_idx, sorted_indices_to_remove[batch_idx]]] = True

                            scaled_logits[indices_to_remove] = -float('inf')

                        # softmax計算
                        exp_logits = np.exp(scaled_logits)
                        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)

                        # サンプリング
                        next_tokens = np.zeros((batch_size, 1), dtype=np.int64)
                        for batch_idx in range(batch_size):
                            next_tokens[batch_idx, 0] = np.random.choice(probs.shape[-1], p=probs[batch_idx])

                    # 停止条件: EOSトークンが生成された場合
                    if next_tokens[0, 0] == self.tokenizer.eos_token_id:
                        break

                    # 入力の拡張
                    curr_input_ids = np.concatenate([curr_input_ids, next_tokens], axis=1)
                    curr_attention_mask = np.concatenate([curr_attention_mask, np.ones((batch_size, 1), dtype=np.int64)], axis=1)

                # 生成されたテキストをデコード
                generated_text = self.tokenizer.decode(curr_input_ids[0], skip_special_tokens=True)
                generated_sequences.append(generated_text)

        except Exception as e:
            logger.error(f"テキスト生成中にエラーが発生しました: {e}")
            return [f"エラー: {str(e)}"]

        elapsed_time = time.time() - start_time
        tokens_generated = sum(len(self.tokenizer.encode(seq)) for seq in generated_sequences) - len(self.tokenizer.encode(prompt)) * num_return_sequences
        tokens_per_second = tokens_generated / elapsed_time if elapsed_time > 0 else 0

        logger.info(f"生成時間: {elapsed_time:.2f}秒、生成トークン数: {tokens_generated}、速度: {tokens_per_second:.2f}トークン/秒")

        return generated_sequences


def initialize_model(
    model_path: str,
    tokenizer_path: Optional[str] = None,
    device: str = "cpu",
) -> None:
    """
    グローバルモデルを初期化する

    Args:
        model_path: ONNXモデルのパス
        tokenizer_path: トークナイザーのパス
        device: デバイス指定
    """
    global global_model, global_model_info

    try:
        logger.info(f"モデルを初期化しています: {model_path}")
        start_time = time.time()

        global_model = ONNXSLMModel(
            model_path=model_path,
            tokenizer_path=tokenizer_path,
            device=device,
        )

        init_time = time.time() - start_time

        # モデル情報を設定
        global_model_info = {
            "model_path": model_path,
            "device": device,
            "initialization_time": f"{init_time:.2f}秒",
            "system_info": global_model.system_info,
            "onnx_providers": ort.get_available_providers(),
            "input_names": global_model.input_names,
            "output_names": global_model.output_names,
        }

        logger.info(f"モデルの初期化が完了しました（所要時間: {init_time:.2f}秒）")
    except Exception as e:
        logger.error(f"モデルの初期化に失敗しました: {e}")
        global_model_info = {"error": str(e)}
        raise


@app.route("/", methods=["GET"])
def index():
    """ルートエンドポイント - サーバーステータスを返す"""
    return jsonify({
        "status": "running",
        "model_info": global_model_info,
        "endpoints": [
            {"path": "/", "method": "GET", "description": "サーバーステータスを返す"},
            {"path": "/generate", "method": "POST", "description": "テキスト生成を実行"},
            {"path": "/health", "method": "GET", "description": "ヘルスチェック"},
        ]
    })


@app.route("/health", methods=["GET"])
def health_check():
    """ヘルスチェックエンドポイント"""
    if global_model is None or global_tokenizer is None:
        return jsonify({"status": "error", "message": "モデルが初期化されていません"}), 503

    # システム情報の更新
    try:
        import psutil

        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.5)

        # Raspberry Piの場合の温度チェック
        temperature = None
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = int(f.read()) / 1000.0
                temperature = f"{temp:.1f}°C"
        except:
            pass

        health_info = {
            "status": "healthy",
            "memory_used_percent": memory.percent,
            "cpu_percent": cpu_percent,
            "temperature": temperature,
        }

        # 高負荷の警告
        if memory.percent > 90:
            health_info["warnings"] = ["メモリ使用率が高すぎます"]

        return jsonify(health_info)
    except Exception as e:
        return jsonify({"status": "warning", "message": str(e)}), 200


@app.route("/generate", methods=["POST"])
def generate():
    """テキスト生成エンドポイント"""
    if global_model is None:
        return jsonify({"error": "モデルが初期化されていません"}), 503

    data = request.json

    if not data or "prompt" not in data:
        return jsonify({"error": "プロンプトが指定されていません"}), 400

    prompt = data["prompt"]

    # パラメータの取得（デフォルト値付き）
    max_length = min(data.get("max_length", 128), 512)  # エッジデバイスの制約
    temperature = max(0.0, min(data.get("temperature", 0.7), 2.0))  # 0.0〜2.0に制限
    top_p = max(0.0, min(data.get("top_p", 0.9), 1.0))  # 0.0〜1.0に制限
    top_k = max(1, min(data.get("top_k", 50), 100))  # 1〜100に制限
    num_return_sequences = max(1, min(data.get("num_return_sequences", 1), 3))  # エッジデバイスでは制限

    try:
        # 非同期処理を避けて、シンプルに実装
        start_time = time.time()

        # テキスト生成
        generated_texts = global_model.generate_text(
            prompt=prompt,
            max_length=max_length,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            num_return_sequences=num_return_sequences,
        )

        elapsed_time = time.time() - start_time

        # 応答の作成
        response = {
            "generated_texts": generated_texts,
            "meta": {
                "prompt": prompt,
                "parameters": {
                    "max_length": max_length,
                    "temperature": temperature,
                    "top_p": top_p,
                    "top_k": top_k,
                    "num_return_sequences": num_return_sequences,
                },
                "generation_time": f"{elapsed_time:.2f}秒",
            }
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"生成中にエラーが発生しました: {e}")
        return jsonify({"error": str(e)}), 500


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="小規模言語モデル（SLM）エッジデプロイメントサーバー")
    parser.add_argument("--model", type=str, required=True, help="ONNXモデルのパス")
    parser.add_argument("--tokenizer", type=str, help="トークナイザーのパス（指定なしの場合はモデルパスを使用）")
    parser.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"], help="実行デバイス")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="サーバーのホストアドレス")
    parser.add_argument("--port", type=int, default=8000, help="サーバーのポート")
    parser.add_argument("--debug", action="store_true", help="デバッグモードで実行")

    args = parser.parse_args()

    # モデルの初期化
    try:
        initialize_model(
            model_path=args.model,
            tokenizer_path=args.tokenizer,
            device=args.device,
        )
    except Exception as e:
        logger.error(f"モデルの初期化に失敗しました: {e}")
        return

    # サーバー起動
    logger.info(f"サーバーを起動しています: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
