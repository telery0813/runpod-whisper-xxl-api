import os
import base64
import tempfile
import subprocess
import glob
import shutil
import runpod


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


def handler(job):
    """
    Expected input JSON:
    {
      "audio_base64": "<base64 string>",
      "filename": "audio.wav",
      "model": "large-v2",
      "language": "zh",
      "vad_method": "pyannote_v3",
      "diarize": "pyannote_v3.1",
      "output_format": "txt"
    }
    """

    inp = job.get("input", {}) or {}

    audio_b64 = inp.get("audio_base64")
    if not audio_b64:
        return {"error": "missing input.audio_base64"}

    filename = inp.get("filename", "audio.wav")
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
        # 1) 寫入原始音檔
        raw_path = os.path.join(tmpdir, filename)
        with open(raw_path, "wb") as f:
            f.write(base64.b64decode(audio_b64))

        # 2) 若非 mp3，轉成 mp3
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
        _run(cmd)

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
            "transcript_txt": transcript
        }


runpod.serverless.start({"handler": handler})
