"""TwitCasting動画の文字起こしスクリプト。

パイプライン:
    yt-dlp (m3u8ストリーム取得) → ffmpeg (音声抽出) → チャンク分割
    → Whisper API または ローカルWhisper → 文字起こし

使い方:
    # OpenAI Whisper API を使用
    export OPENAI_API_KEY=sk-...
    python -m kane.transcribe https://twitcasting.tv/hakureifarm/movie/833748200?t=19 --api

    # ローカル Whisper を使用
    python -m kane.transcribe https://twitcasting.tv/hakureifarm/movie/833748200?t=19 --model medium
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# OpenAI Whisper APIのファイルサイズ上限 (25MB) に収まるよう、
# 安全マージンを取って1チャンクあたり約10分 (mp3 64kbpsで約4.6MB)
CHUNK_DURATION_SEC = 600


def _find_ffmpeg() -> str:
    """ffmpegバイナリのパスを返す。"""
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    print("ffmpegが見つかりません。インストールしてください。", file=sys.stderr)
    sys.exit(1)


def download_audio(url: str, output_path: Path) -> Path:
    """yt-dlpでTwitCasting動画のm3u8ストリームから音声のみをダウンロードする。"""
    ffmpeg_bin = _find_ffmpeg()
    # yt-dlpが内部でffmpegを呼び出すのでffmpeg_locationを指定
    audio_out = output_path / "audio.%(ext)s"
    cmd = [
        "yt-dlp",
        "--no-check-certificates",
        "--ffmpeg-location",
        str(Path(ffmpeg_bin).parent),
        "-f",
        "bestaudio/best",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "5",  # 中品質 (64-96kbps相当)
        "-o",
        str(audio_out),
        url,
    ]
    print(f"音声をダウンロード中: {url}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ダウンロードエラー:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    files = list(output_path.glob("audio.mp3"))
    if not files:
        files = list(output_path.glob("audio.*"))
    if not files:
        print("ダウンロードされた音声ファイルが見つかりません", file=sys.stderr)
        sys.exit(1)
    print(f"ダウンロード完了: {files[0]}")
    return files[0]


def get_audio_duration(audio_path: Path) -> float:
    """音声ファイルの長さ(秒)を取得する。"""
    ffmpeg_bin = _find_ffmpeg()
    # ffprobeは同ディレクトリにない場合があるのでffmpegで代替
    cmd = [
        ffmpeg_bin,
        "-i",
        str(audio_path),
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # ffmpegのstderrから "Duration: HH:MM:SS.xx" を抽出
    for line in result.stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            dur_str = line.split(",", 1)[0].replace("Duration:", "").strip()
            h, m, s = dur_str.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def split_audio(
    audio_path: Path,
    output_path: Path,
    start_sec: int = 0,
    chunk_sec: int = CHUNK_DURATION_SEC,
) -> list[Path]:
    """音声を一定時間のチャンクに分割する。"""
    ffmpeg_bin = _find_ffmpeg()
    chunks_dir = output_path / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss",
        str(start_sec),
        "-i",
        str(audio_path),
        "-f",
        "segment",
        "-segment_time",
        str(chunk_sec),
        "-c",
        "copy",
        str(chunks_dir / "chunk_%03d.mp3"),
    ]
    print(f"音声を {chunk_sec} 秒ごとのチャンクに分割中...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"チャンク分割エラー:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    chunks = sorted(chunks_dir.glob("chunk_*.mp3"))
    print(f"チャンク数: {len(chunks)}")
    return chunks


def transcribe_with_api(chunks: list[Path], start_offset: int = 0) -> str:
    """OpenAI Whisper APIで各チャンクを文字起こしする。"""
    try:
        from openai import OpenAI
    except ImportError:
        print("openai パッケージをインストールしてください: pip install openai", file=sys.stderr)
        sys.exit(1)

    client = OpenAI()
    lines = []
    cumulative_offset = float(start_offset)

    for i, chunk in enumerate(chunks, 1):
        print(f"  [{i}/{len(chunks)}] {chunk.name} を文字起こし中...")
        with chunk.open("rb") as f:
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="ja",
                response_format="verbose_json",
            )

        data = resp.model_dump() if hasattr(resp, "model_dump") else json.loads(str(resp))
        segments = data.get("segments", [])
        for seg in segments:
            start = seg["start"] + cumulative_offset
            end = seg["end"] + cumulative_offset
            text = seg["text"].strip()
            ts = f"{int(start // 60):02d}:{int(start % 60):02d}"
            lines.append(f"[{ts}] {text}")

        # 次のチャンクのオフセットを更新
        chunk_dur = get_audio_duration(chunk)
        cumulative_offset += chunk_dur

    return "\n".join(lines)


def transcribe_with_local(audio_path: Path, model_name: str, start_offset: int = 0) -> str:
    """ローカルWhisperモデルで音声を文字起こしする。"""
    import whisper

    print(f"ローカルWhisperモデル {model_name} をロード中...")
    model = whisper.load_model(model_name)
    print("文字起こし中...")
    result = model.transcribe(str(audio_path), language="ja", verbose=False)

    lines = []
    for seg in result.get("segments", []):
        start = seg["start"] + start_offset
        text = seg["text"].strip()
        ts = f"{int(start // 60):02d}:{int(start % 60):02d}"
        lines.append(f"[{ts}] {text}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="TwitCasting動画の文字起こし")
    parser.add_argument("url", help="TwitCasting動画のURL (?t=N で開始位置指定可)")
    parser.add_argument("--start", type=int, default=0, help="開始位置（秒）")
    parser.add_argument(
        "--api",
        action="store_true",
        help="OpenAI Whisper APIを使用する (OPENAI_API_KEY環境変数が必要)",
    )
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="ローカルWhisperモデルサイズ (--api未指定時)",
    )
    parser.add_argument(
        "--chunk-sec",
        type=int,
        default=CHUNK_DURATION_SEC,
        help=f"チャンク分割時間(秒) (default: {CHUNK_DURATION_SEC})",
    )
    parser.add_argument("--output", type=Path, default=None, help="出力ファイルパス")
    args = parser.parse_args()

    # ?t=N パラメータの処理
    start_sec = args.start
    url = args.url
    if "?t=" in url:
        url_part, t_param = url.split("?t=", 1)
        t_param = t_param.split("&", 1)[0]
        try:
            start_sec = int(t_param)
        except ValueError:
            pass
        url = url_part

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        audio_path = download_audio(url, tmppath)

        if args.api:
            chunks = split_audio(audio_path, tmppath, start_sec, args.chunk_sec)
            transcript = transcribe_with_api(chunks, start_offset=start_sec)
        else:
            # ローカルWhisperは長尺も直接処理可能だが、start_secはそのまま渡す
            if start_sec > 0:
                # 開始位置を反映した音声を作成
                trimmed = tmppath / "trimmed.mp3"
                ffmpeg_bin = _find_ffmpeg()
                subprocess.run(
                    [ffmpeg_bin, "-y", "-ss", str(start_sec), "-i", str(audio_path),
                     "-c", "copy", str(trimmed)],
                    capture_output=True,
                )
                audio_path = trimmed
            transcript = transcribe_with_local(audio_path, args.model, start_offset=start_sec)

    print("\n===== 文字起こし結果 =====\n")
    print(transcript)

    if args.output:
        args.output.write_text(transcript, encoding="utf-8")
        print(f"\n出力ファイル: {args.output}")


if __name__ == "__main__":
    main()
