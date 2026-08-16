"""
视频面试 · 录制文件落盘（腾讯云 COS）
===================================
TRTC 云端录制默认把文件落到云点播(VOD)；本项目把录制产物（或转码后的 mp4）
再归档到 COS，便于按合规周期长期留存、回看与权限管控。

依赖：cos-python-sdk-v5（已在 requirements.txt 增加）。
"""
from __future__ import annotations
import os

from config import COS_BUCKET, COS_REGION, COS_RECORD_PREFIX
from qcloud_cos import CosConfig, CosS3Client


def get_cos_client():
    """构造 COS 客户端（用腾讯云主账号 SecretId/SecretKey）。"""
    from config import TENCENT_SECRET_ID, TENCENT_SECRET_KEY
    if not (COS_BUCKET and COS_REGION and TENCENT_SECRET_ID and TENCENT_SECRET_KEY):
        raise RuntimeError("未配置 COS_BUCKET / COS_REGION / TENCENT_SECRET_ID / TENCENT_SECRET_KEY")
    conf = CosConfig(Region=COS_REGION, SecretId=TENCENT_SECRET_ID, SecretKey=TENCENT_SECRET_KEY)
    return CosS3Client(conf)


def upload_recording(local_path: str, candidate_id: str, room_id: str) -> dict:
    """上传一段面试录制到 COS，返回访问信息。

    路径规则：<COS_RECORD_PREFIX><candidate_id>/<room_id>_<时间戳>.mp4
    """
    client = get_cos_client()
    ext = os.path.splitext(local_path)[1] or ".mp4"
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    key = f"{COS_RECORD_PREFIX}{candidate_id}/{room_id}_{ts}{ext}"
    client.upload_file(Bucket=COS_BUCKET, Key=key, LocalFilePath=local_path)
    return {
        "bucket": COS_BUCKET,
        "key": key,
        "region": COS_REGION,
        "url": f"https://{COS_BUCKET}.cos.{COS_REGION}.myqcloud.com/{key}",
    }


def build_presigned_url(key: str, expired: int = 3600) -> str:
    """生成带时效的回看链接（HR 复核用，避免长期公开）。"""
    client = get_cos_client()
    return client.get_presigned_download_url(Bucket=COS_BUCKET, Key=key, Expired=expired)


if __name__ == "__main__":
    print("COS 模块已加载。上传需在 .env 配置 COS_BUCKET/COS_REGION 及腾讯云凭证后调用。")
