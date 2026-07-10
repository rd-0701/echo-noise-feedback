"""声音工坊 API：上传 / 录制 / 合成 / 频谱调整。"""
import os
import uuid
import time
import threading
import numpy as np
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from scipy.io import wavfile

from ..config import UPLOADS_DIR, SOUNDS_DIR
from ..db import database
from ..audio.sounds import synthesize_sound, SR
from ..core.events import emit

router = APIRouter(prefix="/api/sounds")


def _wav_duration_ms(path: str) -> int:
    try:
        sr, data = wavfile.read(path)
        return int(len(data) / sr * 1000)
    except Exception:
        return 0


def _save_upload_audio(sid: str, raw: bytes, ext: str) -> str:
    """保存上传音频并统一转为标准 16-bit PCM WAV。"""
    src_path = os.path.join(UPLOADS_DIR, f"{sid}.{ext}")
    with open(src_path, "wb") as f:
        f.write(raw)
    wav_path = os.path.join(UPLOADS_DIR, f"{sid}.wav")
    if ext.lower() == "wav":
        # 校验/重采样为标准 16-bit PCM
        try:
            sr, data = wavfile.read(src_path)
            if data.ndim > 1:
                data = data[:, 0]
            data = _to_int16(data)
            if sr != SR:
                # 简单线性重采样
                data = np.interp(
                    np.linspace(0, len(data), int(len(data) * SR / sr)),
                    np.arange(len(data)), data).astype(np.int16)
                sr = SR
            wavfile.write(wav_path, sr, data)
        except Exception:
            wav_path = src_path
        else:
            # 转换成功后删除原始文件
            if os.path.exists(src_path) and src_path != wav_path:
                try:
                    os.remove(src_path)
                except OSError:
                    pass
    else:
        # 非 WAV 尝试用 soundfile 转码
        try:
            import soundfile as sf
            data, sr = sf.read(src_path, dtype="int16", always_2d=False)
            if data.ndim > 1:
                data = data[:, 0]
            if sr != SR:
                data = np.interp(
                    np.linspace(0, len(data), int(len(data) * SR / sr)),
                    np.arange(len(data)), data).astype(np.int16)
            wavfile.write(wav_path, SR, data)
        except Exception as e:
            raise HTTPException(400, f"不支持的音频格式({ext})，请上传 WAV: {e}")
        else:
            # 转换成功后删除原始文件
            if os.path.exists(src_path):
                try:
                    os.remove(src_path)
                except OSError:
                    pass
    return wav_path


def _to_int16(data: np.ndarray) -> np.ndarray:
    """将任意 dtype 的音频数据统一转换为 int16 量级。"""
    if data.dtype == np.int16:
        return data
    if data.dtype == np.int32:
        # 24-bit WAV 在 scipy 中以 int32 返回，需右移 8 位
        return (data // 256).astype(np.int16)
    if data.dtype == np.uint8:
        # 8-bit PCM 以无符号存储，中心为 128
        return ((data.astype(np.int16) - 128) * 256).astype(np.int16)
    if data.dtype == np.float32 or data.dtype == np.float64:
        # float WAV 值域 [-1, 1]
        return (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
    return data.astype(np.int16)


# ===== 上传 =====
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB

@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lstrip(".").lower() or "wav"
    if ext not in ("wav", "mp3", "flac", "ogg"):
        raise HTTPException(400, "仅支持 wav/mp3/flac/ogg")
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"文件过大（>{MAX_UPLOAD_BYTES // 1024 // 1024}MB）")
    sid = uuid.uuid4().hex[:12]
    try:
        path = _save_upload_audio(sid, raw, ext)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"保存失败: {e}")
    duration_ms = _wav_duration_ms(path)
    database.upsert_sound(sid, file.filename or f"upload_{sid}", "uploaded",
                          path, duration_ms, datetime.now().isoformat())
    emit("info", msg=f"新音频上传: {file.filename}")
    return {"id": sid, "name": file.filename, "path": path,
            "duration_ms": duration_ms}


# ===== 录制（PC 麦克风） =====
class RecordPayload(BaseModel):
    seconds: int = 5


@router.post("/record")
def record(payload: RecordPayload):
    import sounddevice as sd
    from ..config import get_config
    sid = uuid.uuid4().hex[:12]
    name = f"录制_{datetime.now().strftime('%m%d_%H%M')}"
    path = os.path.join(UPLOADS_DIR, f"{sid}.wav")
    seconds = max(1, min(int(payload.seconds), 60))

    def _do_record():
        try:
            # 使用配置的输入设备（与检测流一致），未配置则用系统默认
            dev = get_config()["audio"].get("input_device")
            data = sd.rec(int(seconds * SR), samplerate=SR,
                          channels=1, dtype="int16", device=dev)
            sd.wait()
            wavfile.write(path, SR, data)
            duration_ms = int(seconds * 1000)
            database.upsert_sound(sid, name, "recorded", path, duration_ms,
                                  datetime.now().isoformat())
            emit("info", msg=f"录制完成: {name}")
        except Exception as e:
            emit("alert", msg=f"录制失败: {e}")

    threading.Thread(target=_do_record, daemon=True).start()
    return {"id": sid, "name": name, "seconds": seconds, "recording": True}


# ===== 合成 =====
class SynthPayload(BaseModel):
    name: str = "合成音"
    kind: str = "sweep"        # sweep / tone
    f0: float = 40.0
    f1: float = 150.0
    duration_s: float = 5.0


@router.post("/synthesize")
def synthesize(payload: SynthPayload):
    sid = uuid.uuid4().hex[:12]
    try:
        path = synthesize_sound(sid, payload.name, payload.kind,
                                payload.f0, payload.f1, payload.duration_s)
    except Exception as e:
        raise HTTPException(400, f"合成失败: {e}")
    duration_ms = int(payload.duration_s * 1000)
    database.upsert_sound(sid, payload.name, "synthesized", path,
                          duration_ms, datetime.now().isoformat())
    emit("info", msg=f"新合成音频: {payload.name}")
    return {"id": sid, "name": payload.name, "duration_ms": duration_ms}


# ===== 频谱调整（EQ） =====
class EQBand(BaseModel):
    freq_low: float
    freq_high: float
    gain_db: float


class EQPayload(BaseModel):
    bands: list[EQBand]


@router.post("/{sid}/equalize")
def equalize(sid: str, payload: EQPayload):
    row = database.get_sound(sid)
    if row is None:
        raise HTTPException(404, "音频不存在")
    path = row["path"]
    if not os.path.exists(path):
        raise HTTPException(404, "音频文件丢失")
    try:
        sr, data = wavfile.read(path)
        if data.ndim > 1:
            data = data[:, 0]
        # 先统一转 int16，再归一化到 [-1, 1] 进行频谱处理
        data = _to_int16(data)
        data = data.astype(np.float64) / 32767.0
        n = len(data)
        spectrum = np.fft.rfft(data)
        freqs = np.fft.rfftfreq(n, 1.0 / sr)
        for band in payload.bands:
            gain = 10 ** (band.gain_db / 20.0)
            mask = (freqs >= band.freq_low) & (freqs <= band.freq_high)
            spectrum[mask] *= gain
        out = np.fft.irfft(spectrum, n=n)
        # 仅在真正削顶时归一化，保留原始音量比例
        peak = np.max(np.abs(out))
        if peak > 1.0:
            out = out / peak * 0.95
        out = (out * 32767).astype(np.int16)
        # 保存为新音频（保留原文件）
        new_sid = uuid.uuid4().hex[:12]
        new_name = f"{row['name']}_EQ"
        new_path = os.path.join(UPLOADS_DIR, f"{new_sid}.wav")
        wavfile.write(new_path, sr, out)
        duration_ms = int(len(out) / sr * 1000)
        database.upsert_sound(new_sid, new_name, "synthesized", new_path,
                              duration_ms, datetime.now().isoformat())
        emit("info", msg=f"频谱调整完成: {new_name}")
        return {"id": new_sid, "name": new_name, "duration_ms": duration_ms}
    except Exception as e:
        raise HTTPException(400, f"频谱调整失败: {e}")
