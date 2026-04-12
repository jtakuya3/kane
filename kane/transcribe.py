"""TwitCasting動画の文字起こしスクリプト。

使い方:
    python -m kane.transcribe https://twitcasting.tv/hakureifarm/movie/833748200 --start 19
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


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


def download_video(url: str, output_path: Path) -> Path:
    """yt-dlpでTwitCasting動画をダウンロードする。"""
    cmd = [
        "yt-dlp",
        "--no-check-certificates",
        "-o",
        str(output_path / "video.%(ext)s"),
        url,
    ]
    print(f"動画をダウンロード中: {url}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ダウンロードエラー: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    # ダウンロードされたファイルを探す
    files = list(output_path.glob("video.*"))
    if not files:
        print("ダウンロードされたファイルが見つかりません", file=sys.stderr)
        sys.exit(1)
    print(f"ダウンロード完了: {files[0]}")
    return files[0]


def extract_audio(video_path: Path, output_path: Path, start_sec: int = 0) -> Path:
    """ffmpegで動画から音声を抽出する。"""
    audio_path = output_path / "audio.wav"
    ffmpeg_bin = _find_ffmpeg()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(video_path),
    ]
    if start_sec > 0:
        cmd.extend(["-ss", str(start_sec)])
    cmd.extend([
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(audio_path),
    ])
    print(f"音声を抽出中 (開始: {start_sec}秒)...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"音声抽出エラー: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"音声抽出完了: {audio_path}")
    return audio_path


def transcribe_audio(audio_path: Path, model_name: str = "base") -> str:
    """Whisperで音声を文字起こしする。"""
    import whisper

    print(f"文字起こし中 (モデル: {model_name})...")
    model = whisper.load_model(model_name)
    result = model.transcribe(str(audio_path), language="ja")

    segments = result.get("segments", [])
    lines = []
    for seg in segments:
        start = seg["start"]
        end = seg["end"]
        text = seg["text"].strip()
        start_str = f"{int(start // 60):02d}:{int(start % 60):02d}"
        end_str = f"{int(end // 60):02d}:{int(end % 60):02d}"
        lines.append(f"[{start_str} - {end_str}] {text}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="TwitCasting動画の文字起こし")
    parser.add_argument("url", help="TwitCasting動画のURL")
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="開始位置（秒）",
    )
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisperモデルサイズ (default: base)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="出力ファイルパス (指定しない場合は標準出力)",
    )
    args = parser.parse_args()

    # ?t=N パラメータの処理
    start_sec = args.start
    if "?t=" in args.url:
        url_part, t_param = args.url.split("?t=", 1)
        try:
            start_sec = int(t_param)
        except ValueError:
            pass
        args.url = url_part

    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        video_path = download_video(args.url, tmppath)
        audio_path = extract_audio(video_path, tmppath, start_sec)
        transcript = transcribe_audio(audio_path, args.model)

    print("\n===== 文字起こし結果 =====\n")
    print(transcript)

    if args.output:
        args.output.write_text(transcript, encoding="utf-8")
        print(f"\n出力ファイル: {args.output}")


if __name__ == "__main__":
    main()
