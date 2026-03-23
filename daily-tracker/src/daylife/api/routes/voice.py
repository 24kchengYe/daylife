"""语音转文字路由 — 使用 OpenAI Whisper API (via OpenRouter)"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from daylife.core.llm import get_llm_client
from daylife.core.schemas import ApiResponse

router = APIRouter()


@router.post("/transcribe", response_model=ApiResponse)
async def transcribe(file: UploadFile = File(...)):
    """接收音频文件，调用 Whisper API 转文字"""
    client, _ = get_llm_client()
    if not client:
        return ApiResponse(code=500, message="未配置 OPENAI_API_KEY")

    # 保存上传文件到临时目录
    suffix = Path(file.filename).suffix if file.filename else ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="openai/whisper-large-v3",
                file=audio_file,
            )
        text = transcript.text if hasattr(transcript, 'text') else str(transcript)
        return ApiResponse(data={"text": text.strip()})
    except Exception as e:
        return ApiResponse(code=500, message=f"语音识别失败: {str(e)}")
    finally:
        try:
            Path(tmp_path).unlink()
        except Exception:
            pass
