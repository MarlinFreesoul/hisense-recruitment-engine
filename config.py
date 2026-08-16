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
INTERNAL_TALENT_TABLE_ID = os.getenv("INTERNAL_TALENT_TABLE_ID", "tblfvT5JW1h16YqX")  # 内部人才库
HISTORICAL_TALENT_TABLE_ID = os.getenv("HISTORICAL_TALENT_TABLE_ID", "tblAYhymiftIWLsw")  # 历史候选人库
INTERVIEW_COLLECT_TABLE_ID = os.getenv("INTERVIEW_COLLECT_TABLE_ID", "tblhzLcVQeJCgHWP")  # 面试采集表

# ============ LLM（DeepSeek） ============
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ============ 匹配配置 ============
TOP_N_CANDIDATES = int(os.getenv("TOP_N_CANDIDATES", "5"))
