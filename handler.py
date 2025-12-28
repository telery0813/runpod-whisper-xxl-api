import os
import base64
import tempfile
import subprocess
import glob
import shutil
import runpod
import urllib.request


def _run(cmd):
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if p.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(cmd)
            + "\n\nSTDOUT:\n"
            + p.stdout
            + "\n\nSTDERR:\n"
            + p.stderr
        )


def _download_to_file(url: str, dst_path: str):
    # 下載 audio_url 到指定路徑（標準庫，不用額外裝 requests）
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        if getattr(resp, "status", 200) >= 400:
            raise RuntimeError(f"Download failed with status {resp.status}")
        data = resp.read()
    with open(dst_path, "wb") as f:
        f.write(data)


def handler(job):
    """
    Supported input JSON (RunPod job["input"]):

    A) Base64:
    {
      "audio_base64": "<base64 string>",
      "filename": "audio.wav",
      "model": "large-v2",
      "language": "zh",
      "vad_method": "pyannote_v3",
      "diarize": "pyannote_v3.1",
      "output_format": "txt"
    }

    B) URL:
    {
      "audio_url": "https://....../1.flac",
      "filename": "1.flac",            # 可選；沒填會用 audio.bin
      "model": "large-v2",
      "language": "zh",
      "vad_method": "pyannote_v3",
      "diarize": "pyannote_v3.1",
      "output_format": "txt"
    }
    """

    inp = job.get("input", {}) or {}

    audio_b64 = inp.get("audio_base64")
    audio_url = inp.get("audio_url")

    if not audio_b64 and not audio_url:
        return {"error": "missing input.audio_base64 or input.audio_url"}

    filename = inp.get("filename", "audio.bin")
    model = inp.get("model", "large-v2")
    language = inp.get("language", "zh")
    vad_method = inp.get("vad_method", "pyannote_v3")
    diarize = inp.get("diarize", "pyannote_v3.1")
    output_format = inp.get("output_format", "txt")

    # 找 faster-whisper-xxl 執行檔
    fw = shutil.which("faster-whisper-xxl")
    if not fw and os.path.exists("/faster-whisper-xxl"):
        fw = "/faster-whisper-xxl"
    if not fw:
        return {"error": "faster-whisper-xxl binary not found"}

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1) 取得音檔到本機（raw_path）
        raw_path = os.path.join(tmpdir, filename)

        try:
            if audio_url:
                # 若 filename 沒帶副檔名，盡量從 URL 推斷
                if filename == "audio.bin":
                    # 嘗試用 URL 的最後一段命名
                    try:
                        name = audio_url.split("?")[0].split("/")[-1]
                        if name:
                            raw_path = os.path.join(tmpdir, name)
                            filename = name
                    except Exception:
                        pass

                _download_to_file(audio_url, raw_path)

            else:
                # base64
                with open(raw_path, "wb") as f:
                    f.write(base64.b64decode(audio_b64))

        except Exception as e:
            return {"error": f"failed to get audio: {str(e)}"}

        # 2) 若非 mp3，轉成 mp3（你原本的流程保留）
        ext = os.path.splitext(filename)[1].lower()
        mp3_path = os.path.join(tmpdir, "input.mp3")
        if ext != ".mp3":
            _run([
                "ffmpeg", "-y",
                "-i", raw_path,
                "-vn",
                "-acodec", "libmp3lame",
                "-q:a", "2",
                mp3_path
            ])
            input_audio = mp3_path
        else:
            input_audio = raw_path

        # 3) 執行 faster-whisper-xxl
        out_dir = os.path.join(tmpdir, "out")
        os.makedirs(out_dir, exist_ok=True)

        cmd = [
            fw, input_audio,
            "--model", model,
            "--language", language,
            "--vad_method", vad_method,
            "--diarize", diarize,
            "--output_format", output_format,
            "--output_dir", out_dir
        ]

        try:
            _run(cmd)
        except Exception as e:
            # 把 out_dir 的檔案也回傳，方便你 debug
            return {
                "error": str(e),
                "out_dir_files": os.listdir(out_dir) if os.path.exists(out_dir) else []
            }

        # 4) 讀取輸出 txt
        txt_files = glob.glob(os.path.join(out_dir, "*.txt"))
        if not txt_files:
            return {
                "error": "no transcript generated",
                "files": os.listdir(out_dir)
            }

        with open(txt_files[0], "r", encoding="utf-8", errors="ignore") as f:
            transcript = f.read()

        return {
            "filename": filename,
            "model": model,
            "language": language,
            "vad_method": vad_method,
            "diarize": diarize,
            "output_format": output_format,
            "transcript_txt": transcript
        }


runpod.serverless.start({"handler": handler})
