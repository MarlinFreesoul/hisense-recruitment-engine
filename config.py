"""
统一配置中心
=============
从环境变量读取，配合项目根目录的 .env 使用（.env 不入库，见 .env.example）。
同事 clone 后：cp .env.example .env，填入自己的凭证即可跑。
"""
import os
import pathlib


def _load_env():
    """加载项目根目录 .env 到环境变量（不依赖 python-dotenv）。"""
    env_file = pathlib.Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_env()

# ============ 飞书 ============
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BASE_TOKEN = os.getenv("FEISHU_BASE_TOKEN", "Jy6Rbb2m5aJPoNswNWzcOhm9npg")

# 表格 ID
JD_TABLE_ID = os.getenv("JD_TABLE_ID", "tblizVYaGfzcPBak")          # 招聘需求表
RESUME_TABLE_ID = os.getenv("RESUME_TABLE_ID", "tblNcaGuBlskCm8x")  # 简历库
RESULT_TABLE_ID = os.getenv("RESULT_TABLE_ID", "tblqA6EPmKoM7Ei3")  # 评分结果表
WEIGHT_TABLE_ID = os.getenv("WEIGHT_TABLE_ID", "tblfY4SisSRMlXrc")  # 权重配置表
INTERVIEW_TABLE_ID = os.getenv("INTERVIEW_TABLE_ID", "tblbFeWzLARIFqL8")  # 面试记录表
PROGRESS_TABLE_ID = os.getenv("PROGRESS_TABLE_ID", "tbl7llDoJwAZu3fP")    # 招聘进度管理表
INTERVIEW_COLLECT_TABLE_ID = os.getenv("INTERVIEW_COLLECT_TABLE_ID", "tblhzLcVQeJCgHWP")  # 面试采集表
TALENT_POOL_TABLE_ID = os.getenv("TALENT_POOL_TABLE_ID", "")  # 人才储备池表（模块 4：Offer 递补；留空则仅内存池）
INTERNAL_TALENT_TABLE_ID = os.getenv("INTERNAL_TALENT_TABLE_ID", "tblfvT5JW1h16YqX")  # 内部人才库
HISTORICAL_TALENT_TABLE_ID = os.getenv("HISTORICAL_TALENT_TABLE_ID", "tblAYhymiftIWLsw")  # 历史候选人库

# ============ LLM（DeepSeek） ============
# 注意：DeepSeek 于 2026-08-17 起启用峰谷定价；沿用 deepseek-chat(V3.2) 可避开涨价。
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ============ 视频面试 · 腾讯云 TRTC（独立接入，后端自签 UserSig） ============
# TRTC 控制台「应用」页可拿到 SDKAppID 与「密钥」(Key)。后者仅用于后端签发 UserSig，
# 与下方腾讯云主账号的 SecretId/SecretKey 不是一回事，请勿混用。
TRTC_APP_ID = os.getenv("TRTC_APP_ID", "")
TRTC_SECRET_KEY = os.getenv("TRTC_SECRET_KEY", "")
TRTC_USER_SIG_EXPIRE = int(os.getenv("TRTC_USER_SIG_EXPIRE", "86400"))  # UserSig 有效期（秒）

# ============ 独立语音识别 · 腾讯云实时语音识别（不走 TRTC 内置 AI 识别） ============
# 用腾讯云主账号的 SecretId/SecretKey 鉴权；ASR_APP_ID 是语音识别应用的 AppId（≠ TRTC_APP_ID）。
TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID", "")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY", "")
ASR_APP_ID = os.getenv("ASR_APP_ID", "")
# 引擎模型：16k_zh(中文普通话) / 16k_zh_en(中英混合) / 16k_en(英文) 等
ASR_ENGINE_MODEL = os.getenv("ASR_ENGINE_MODEL", "16k_zh")
ASR_VOICE_FORMAT = int(os.getenv("ASR_VOICE_FORMAT", "1"))  # 1=pcm 16bit / 4=speex / 6=opus / 8=wav

# ============ 录制存储 · 腾讯云 COS ============
COS_BUCKET = os.getenv("COS_BUCKET", "")
COS_REGION = os.getenv("COS_REGION", "")
COS_RECORD_PREFIX = os.getenv("COS_RECORD_PREFIX", "interview-records/")

# ============ TRTC 云端录制（事后文件识别的音频来源） ============
# 开启后，面试开始由后端启动云端录制落盘 → 走 asr_file 做带说话人分离的权威纪要。
# 默认开启：让「实时 ASR 辅助 → 云端录制 → 文件识别 → 评分 → 写飞书」默认具备录制音频源，
# 形成开箱即用的端到端闭环；无 TRTC 凭证时前端会优雅降级到本地转写兜底回写。
TRTC_RECORD_ENABLED = os.getenv("TRTC_RECORD_ENABLED", "true").lower() in ("1", "true", "yes", "on")

# 云端录制机器人：一个「进房录制」的服务端用户，需后端签 UserSig。
TRTC_RECORD_BOT_USER = os.getenv("TRTC_RECORD_BOT_USER", "rec_bot")
# 录制模式：Audio（仅音频，最省，且正是 ASR 所需）/ Video / VideoAndAudio
TRTC_RECORD_MODE = os.getenv("TRTC_RECORD_MODE", "Audio")
# 录制落盘目标：cos（腾讯云对象存储，本项目默认）/ vod（云点播）
TRTC_RECORD_STORAGE = os.getenv("TRTC_RECORD_STORAGE", "cos")

# 腾讯云回调校验令牌（可选）：录制完成回调 /video/recording/callback 时用于验签。
VIDEO_CALLBACK_TOKEN = os.getenv("VIDEO_CALLBACK_TOKEN", "")

# ============ TRTC 单流分轨录制（更稳的线上说话人分离方案） ============
# 不设置 MixTranscodeParams 即「单流录制」：房间内每个用户(HR / 候选人)各生成独立音频文件，
# 文件名内含 base64(UserId)。后端据此按「轨道(UserID)」直接标说话人，无需说话人分离，
# 比「合流 + diarization」更稳、更省（diarization 对合成音/相似声线易并为一类）。
TRTC_RECORD_SINGLE_STREAM = os.getenv("TRTC_RECORD_SINGLE_STREAM", "true").lower() in ("1", "true", "yes", "on")

# ============ 候选人面试资格门禁（真实飞书简历 + 资料完整） ============
# 每个真实候选人 = 飞书简历库(RESUME_TABLE_ID)的一条记录，record_id 即其唯一 ID。
# 仅当该记录存在且以下必填字段均已填写，才允许被分配视频房间与 HR 面试，
# 保证「每一次视频对话都是真实候选人填完资料后才可以跟 HR 面试」。
CANDIDATE_REQUIRED_FIELDS = [
    f.strip() for f in os.getenv(
        "CANDIDATE_REQUIRED_FIELDS", "姓名,最近职位,最近公司,工作年限"
    ).split(",") if f.strip()
]

# ============ 录音文件识别（事后权威纪要，腾讯云 ASR 文件识别） ============
# 与 realtime_asr（实时流式·单说话人）互补：文件识别异步、支持说话人分离，
# 用于产出带说话人标签的双人权威转写 + 面试评分（赛题模块 3 硬要求）。
ASR_FILE_ENGINE = os.getenv("ASR_FILE_ENGINE", "16k_zh")   # 文件识别引擎（默认中文普通话）
ASR_FILE_REGION = os.getenv("ASR_FILE_REGION", "ap-guangzhou")

# ============ 视频面试前端页（候选人浏览器/H5 打开地址） ============
VIDEO_INTERVIEW_BASE_URL = os.getenv("VIDEO_INTERVIEW_BASE_URL", "http://localhost:8000")

# ============ 匹配配置 ============
TOP_N_CANDIDATES = int(os.getenv("TOP_N_CANDIDATES", "5"))
