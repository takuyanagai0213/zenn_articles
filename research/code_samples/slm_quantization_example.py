#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
小規模言語モデル（SLM）量子化実装サンプル
==========================================

このスクリプトは、小規模言語モデルの量子化実装方法を示すサンプルコードです。
GPTQ量子化とAWQ量子化の両方の実装例を含んでいます。

必要なライブラリ:
- PyTorch 2.0+
- transformers 4.30.0+
- optimum 1.8.0+
- auto-gptq (GPTQ用)
- awq (AWQ用)

注意: このコードは教育目的のサンプルであり、本番環境での使用前にテストと最適化が必要です。
"""

import os
import time
import torch
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple

from transformers import AutoTokenizer, AutoModelForCausalLM, TextGenerationPipeline
from optimum.gptq import GPTQQuantizer
from awq import AutoAWQForCausalLM

# ロギング設定
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class SLMQuantizer:
    """小規模言語モデル量子化クラス"""

    def __init__(
        self,
        model_name: str,
        output_dir: str,
        quantization_method: str = "gptq",
        bits: int = 4,
        group_size: int = 128,
        device: str = "cuda" if torch.cuda.is_available() else "cpu",
    ):
        """
        初期化関数

        Args:
            model_name: Hugging Face Hub上のモデル名またはローカルパス
            output_dir: 量子化モデルの保存先ディレクトリ
            quantization_method: 量子化方式 ("gptq" または "awq")
            bits: 量子化ビット数 (通常は4または8)
            group_size: 量子化グループサイズ
            device: 使用デバイス ("cuda" または "cpu")
        """
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.quantization_method = quantization_method.lower()
        self.bits = bits
        self.group_size = group_size
        self.device = device

        # 出力ディレクトリがなければ作成
        os.makedirs(self.output_dir, exist_ok=True)

        # トークナイザーの読み込み
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        logger.info(f"モデル {model_name} の量子化を開始します（方式: {quantization_method}, {bits}ビット）")

    def prepare_calibration_data(self, texts: List[str] = None) -> List[Dict]:
        """
        キャリブレーションデータの準備

        Args:
            texts: キャリブレーション用テキストリスト。指定がなければサンプルデータを使用。

        Returns:
            キャリブレーション用のトークン化されたデータ
        """
        # テキストが提供されていない場合はサンプルを使用
        if texts is None:
            texts = [
                "人工知能技術の急速な発展により、小規模言語モデルの活用が広がっています。",
                "小規模言語モデル（SLM）は、エッジデバイスでの推論が可能なサイズに最適化されています。",
                "企業におけるAI導入においては、コスト効率と性能のバランスが重要な検討要素です。",
                "自然言語処理技術の進化により、日本語対応の言語モデルも高精度になっています。",
                "量子化技術によって、モデルサイズを削減しつつ性能を維持することが可能になります。"
            ]

        # トークン化
        tokenized_data = []
        for text in texts:
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                padding="max_length",
                max_length=512,
                truncation=True,
            )
            tokenized_data.append({
                "input_ids": inputs["input_ids"].to(self.device),
                "attention_mask": inputs["attention_mask"].to(self.device),
            })

        logger.info(f"{len(tokenized_data)}件のキャリブレーションデータを準備しました")
        return tokenized_data

    def quantize_gptq(self, calibration_data: List[Dict]) -> None:
        """
        GPTQ量子化を実行

        Args:
            calibration_data: キャリブレーション用のトークン化されたデータ
        """
        logger.info("GPTQによる量子化を開始します")
        start_time = time.time()

        # モデルをFP16で読み込み
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16,
            device_map=self.device
        )

        # 量子化オプション設定
        quantizer = GPTQQuantizer(
            bits=self.bits,
            group_size=self.group_size,
            desc_act=True,  # アクティベーション記述子を使用
        )

        # 量子化実行
        quantized_model = quantizer.quantize_model(
            model,
            calibration_data,
            tokenizer=self.tokenizer,
        )

        # 量子化モデル保存
        gptq_output_dir = self.output_dir / f"gptq_{self.bits}bit"
        quantized_model.save_pretrained(gptq_output_dir)
        self.tokenizer.save_pretrained(gptq_output_dir)

        elapsed_time = time.time() - start_time
        logger.info(f"GPTQ量子化が完了しました（所要時間: {elapsed_time:.2f}秒）")
        logger.info(f"量子化モデルを {gptq_output_dir} に保存しました")

    def quantize_awq(self, calibration_data: List[Dict]) -> None:
        """
        AWQ量子化を実行

        Args:
            calibration_data: キャリブレーション用のトークン化されたデータ
        """
        logger.info("AWQによる量子化を開始します")
        start_time = time.time()

        # AWQ用にテキストデータを準備
        texts = [
            self.tokenizer.decode(item["input_ids"][0], skip_special_tokens=True)
            for item in calibration_data
        ]

        # AWQモデルのロード
        model = AutoAWQForCausalLM.from_pretrained(
            self.model_name,
            device_map=self.device,
        )

        # 量子化の実行
        model.quantize(
            tokenizer=self.tokenizer,
            quant_config={
                "bits": self.bits,           # 量子化ビット数
                "group_size": self.group_size,  # グループサイズ
                "zero_point": True,          # ゼロポイント量子化を使用
                "q_group_size": 128,         # 内部パラメータ
                "version": "GEMM",           # バックエンドバージョン
            },
            calib_data=texts,
        )

        # 量子化モデル保存
        awq_output_dir = self.output_dir / f"awq_{self.bits}bit"
        model.save_pretrained(awq_output_dir)
        self.tokenizer.save_pretrained(awq_output_dir)

        elapsed_time = time.time() - start_time
        logger.info(f"AWQ量子化が完了しました（所要時間: {elapsed_time:.2f}秒）")
        logger.info(f"量子化モデルを {awq_output_dir} に保存しました")

    def quantize(self) -> None:
        """量子化処理のメイン関数"""
        # キャリブレーションデータの準備
        calibration_data = self.prepare_calibration_data()

        # 指定された方式で量子化を実行
        if self.quantization_method == "gptq":
            self.quantize_gptq(calibration_data)
        elif self.quantization_method == "awq":
            self.quantize_awq(calibration_data)
        else:
            raise ValueError(f"未対応の量子化方式です: {self.quantization_method}")

    def run_inference_benchmark(
        self,
        quantized_model_path: Optional[str] = None,
        input_text: str = "小規模言語モデルの主な利点は、",
        max_length: int = 128,
        num_runs: int = 5,
    ) -> Dict:
        """
        推論ベンチマークを実行

        Args:
            quantized_model_path: 量子化済みモデルのパス
            input_text: 入力テキスト
            max_length: 生成する最大トークン数
            num_runs: ベンチマーク実行回数

        Returns:
            ベンチマーク結果の辞書
        """
        if quantized_model_path is None:
            if self.quantization_method == "gptq":
                quantized_model_path = str(self.output_dir / f"gptq_{self.bits}bit")
            else:
                quantized_model_path = str(self.output_dir / f"awq_{self.bits}bit")

        logger.info(f"モデル {quantized_model_path} の推論ベンチマークを開始します")

        # モデルとトークナイザーのロード
        tokenizer = AutoTokenizer.from_pretrained(quantized_model_path)
        if self.quantization_method == "gptq":
            from optimum.gptq import GPTQForCausalLM
            model = GPTQForCausalLM.from_pretrained(
                quantized_model_path,
                device_map=self.device,
            )
        else:  # AWQ
            model = AutoAWQForCausalLM.from_pretrained(
                quantized_model_path,
                device_map=self.device,
            )

        # パイプラインの設定
        pipeline = TextGenerationPipeline(
            model=model,
            tokenizer=tokenizer,
            device=0 if self.device == "cuda" else -1,
        )

        # 推論速度ベンチマーク
        latencies = []
        tokens_per_second = []
        total_tokens = []

        for i in range(num_runs):
            logger.info(f"ベンチマーク実行 {i+1}/{num_runs}")
            start_time = time.time()

            # 推論実行
            outputs = pipeline(
                input_text,
                max_length=max_length,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
                return_full_text=True,
            )

            end_time = time.time()

            # 出力テキスト
            generated_text = outputs[0]["generated_text"]

            # トークン数計算
            tokens = len(tokenizer.encode(generated_text))
            elapsed = end_time - start_time

            latencies.append(elapsed)
            total_tokens.append(tokens)
            tokens_per_second.append(tokens / elapsed)

            logger.info(f"生成されたテキスト: {generated_text[:100]}...")
            logger.info(f"推論時間: {elapsed:.4f}秒、トークン数: {tokens}、速度: {tokens/elapsed:.2f}トークン/秒")

        # 結果集計
        avg_latency = sum(latencies) / len(latencies)
        avg_tokens_per_second = sum(tokens_per_second) / len(tokens_per_second)

        result = {
            "model": quantized_model_path,
            "quantization_method": self.quantization_method,
            "bits": self.bits,
            "device": self.device,
            "avg_latency": avg_latency,
            "avg_tokens_per_second": avg_tokens_per_second,
            "input_text": input_text,
            "max_length": max_length,
            "num_runs": num_runs,
        }

        logger.info(f"ベンチマーク結果: 平均レイテンシ {avg_latency:.4f}秒、平均速度 {avg_tokens_per_second:.2f}トークン/秒")
        return result


def compare_memory_usage(
    original_model_name: str,
    quantized_model_dirs: List[str],
    device: str = "cuda",
) -> Dict:
    """
    元モデルと量子化モデルのメモリ使用量を比較

    Args:
        original_model_name: 元のモデル名
        quantized_model_dirs: 量子化モデルのディレクトリリスト
        device: 使用デバイス

    Returns:
        メモリ使用量の比較結果
    """
    logger.info("モデルのメモリ使用量比較を開始します")
    results = {}

    # 元モデルのメモリ使用量測定
    logger.info(f"元モデル {original_model_name} のメモリ使用量を測定")
    torch.cuda.empty_cache()
    start_mem = torch.cuda.memory_allocated() if device == "cuda" else 0

    model = AutoModelForCausalLM.from_pretrained(
        original_model_name,
        torch_dtype=torch.float16,
        device_map=device,
    )

    end_mem = torch.cuda.memory_allocated() if device == "cuda" else 0
    original_mem_usage = (end_mem - start_mem) / (1024 ** 2)  # MB単位

    # モデルサイズ取得（概算）
    param_size = sum(p.numel() * p.element_size() for p in model.parameters()) / (1024 ** 2)  # MB単位

    results["original"] = {
        "model_name": original_model_name,
        "memory_usage_mb": original_mem_usage,
        "parameter_size_mb": param_size,
    }

    logger.info(f"元モデルのメモリ使用量: {original_mem_usage:.2f} MB、パラメータサイズ: {param_size:.2f} MB")

    # 量子化モデルのメモリ使用量測定
    for quant_dir in quantized_model_dirs:
        model_name = Path(quant_dir).name
        logger.info(f"量子化モデル {model_name} のメモリ使用量を測定")

        torch.cuda.empty_cache()
        start_mem = torch.cuda.memory_allocated() if device == "cuda" else 0

        if "gptq" in model_name:
            from optimum.gptq import GPTQForCausalLM
            quant_model = GPTQForCausalLM.from_pretrained(
                quant_dir,
                device_map=device,
            )
        elif "awq" in model_name:
            quant_model = AutoAWQForCausalLM.from_pretrained(
                quant_dir,
                device_map=device,
            )
        else:
            logger.warning(f"未対応の量子化モデル: {quant_dir}")
            continue

        end_mem = torch.cuda.memory_allocated() if device == "cuda" else 0
        quant_mem_usage = (end_mem - start_mem) / (1024 ** 2)  # MB単位

        # モデルサイズ取得（概算）
        quant_param_size = sum(p.numel() * p.element_size() for p in quant_model.parameters()) / (1024 ** 2)  # MB単位

        compression_ratio = original_mem_usage / quant_mem_usage if quant_mem_usage > 0 else float('inf')

        results[model_name] = {
            "model_name": quant_dir,
            "memory_usage_mb": quant_mem_usage,
            "parameter_size_mb": quant_param_size,
            "compression_ratio": compression_ratio,
        }

        logger.info(f"量子化モデルのメモリ使用量: {quant_mem_usage:.2f} MB、圧縮率: {compression_ratio:.2f}倍")

    return results


def optimize_for_edge_device(
    model_dir: str,
    output_dir: str,
    framework: str = "onnx",
    target_device: str = "cpu",
) -> None:
    """
    エッジデバイス向けにモデルを最適化

    Args:
        model_dir: 量子化済みモデルのディレクトリ
        output_dir: 最適化モデルの出力先
        framework: 変換フレームワーク ("onnx" or "tensorrt")
        target_device: ターゲットデバイス ("cpu", "gpu", "tensorrt")
    """
    logger.info(f"モデル {model_dir} をエッジデバイス向けに最適化します（フレームワーク: {framework}）")
    os.makedirs(output_dir, exist_ok=True)

    if framework.lower() == "onnx":
        optimize_for_onnx(model_dir, output_dir, target_device)
    elif framework.lower() == "tensorrt":
        optimize_for_tensorrt(model_dir, output_dir)
    else:
        raise ValueError(f"未対応のフレームワークです: {framework}")


def optimize_for_onnx(model_dir: str, output_dir: str, target_device: str) -> None:
    """
    ONNXフォーマットへの変換と最適化

    Args:
        model_dir: 量子化済みモデルのディレクトリ
        output_dir: 最適化モデルの出力先
        target_device: ターゲットデバイス
    """
    try:
        from optimum.onnxruntime import ORTModelForCausalLM
        from transformers import AutoTokenizer
        from onnxruntime.quantization import quantize_dynamic, QuantType
    except ImportError:
        logger.error("ONNX変換に必要なライブラリがインストールされていません。")
        logger.error("pip install optimum[onnxruntime] onnxruntime-gpu を実行してください。")
        return

    logger.info("モデルをONNXフォーマットに変換しています...")

    # モデルとトークナイザーのロード
    tokenizer = AutoTokenizer.from_pretrained(model_dir)

    # ONNXへの変換
    ort_model = ORTModelForCausalLM.from_pretrained(
        model_dir,
        export=True,
        provider="CUDAExecutionProvider" if target_device == "gpu" else "CPUExecutionProvider",
    )

    # モデルの保存
    onnx_output_dir = os.path.join(output_dir, "onnx_model")
    ort_model.save_pretrained(onnx_output_dir)
    tokenizer.save_pretrained(onnx_output_dir)

    logger.info(f"ONNXモデルを {onnx_output_dir} に保存しました")

    # 量子化済みモデルの場合は追加の最適化は不要な場合が多い
    logger.info("モデルはすでに量子化済みのため、追加のONNX量子化は実行しません")


def optimize_for_tensorrt(model_dir: str, output_dir: str) -> None:
    """
    TensorRTフォーマットへの変換と最適化

    Args:
        model_dir: 量子化済みモデルのディレクトリ
        output_dir: 最適化モデルの出力先
    """
    try:
        import tensorrt as trt
        from transformers import AutoTokenizer
        from transformers.onnx import export
        import onnx
    except ImportError:
        logger.error("TensorRT変換に必要なライブラリがインストールされていません。")
        logger.error("TensorRTのインストールは公式ドキュメントを参照してください。")
        return

    logger.info("モデルをTensorRTフォーマットに変換しています...")

    # これは概念的な実装であり、実際のTensorRT変換はより複雑になります
    # 本番環境では、NVIDIA TensorRT公式のツールとサンプルを参照してください
    logger.warning("TensorRT変換は概念的な実装であり、実際の変換には追加の手順が必要です")

    # トークナイザーの保存
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    tensorrt_output_dir = os.path.join(output_dir, "tensorrt_model")
    os.makedirs(tensorrt_output_dir, exist_ok=True)
    tokenizer.save_pretrained(tensorrt_output_dir)

    logger.info(f"トークナイザーを {tensorrt_output_dir} に保存しました")
    logger.info("実際のTensorRT変換は、NVIDIA TensorRT公式のツールを使用して行ってください")


def main():
    """メイン関数"""
    # 使用例1: GPTQによる量子化
    model_name = "elyza/ELYZA-japanese-Llama-2-7b-instruct"  # 小規模日本語モデルの例
    output_dir = "./quantized_models"

    # GPTQ量子化
    gptq_quantizer = SLMQuantizer(
        model_name=model_name,
        output_dir=output_dir,
        quantization_method="gptq",
        bits=4,
        group_size=128,
    )
    gptq_quantizer.quantize()

    # 推論ベンチマーク実行
    gptq_benchmark = gptq_quantizer.run_inference_benchmark(
        input_text="小規模言語モデルの企業での活用事例には、次のようなものがあります：",
        max_length=150,
        num_runs=3,
    )

    # 使用例2: AWQによる量子化
    awq_quantizer = SLMQuantizer(
        model_name=model_name,
        output_dir=output_dir,
        quantization_method="awq",
        bits=4,
        group_size=128,
    )
    awq_quantizer.quantize()

    # 推論ベンチマーク実行
    awq_benchmark = awq_quantizer.run_inference_benchmark(
        input_text="小規模言語モデルの企業での活用事例には、次のようなものがあります：",
        max_length=150,
        num_runs=3,
    )

    # メモリ使用量の比較
    quantized_dirs = [
        os.path.join(output_dir, "gptq_4bit"),
        os.path.join(output_dir, "awq_4bit"),
    ]
    memory_comparison = compare_memory_usage(
        original_model_name=model_name,
        quantized_model_dirs=quantized_dirs,
    )

    # ONNX最適化
    optimize_for_edge_device(
        model_dir=os.path.join(output_dir, "gptq_4bit"),
        output_dir=os.path.join(output_dir, "optimized"),
        framework="onnx",
        target_device="cpu",
    )

    logger.info("量子化と最適化のデモが完了しました")


if __name__ == "__main__":
    main()
