"""
海信 AI 招聘智能体 · 主入口
============================
持续运行的服务入口 + 单次操作。

用法：
  python main.py                  # 默认：启动 API 服务（持续运行）
  python main.py --host 0.0.0.0 --port 8000   # 指定监听地址/端口
  python main.py --match          # 单次：跑匹配评分，写回飞书
  python main.py --parse "简历文本" # 单次：LLM 解析一份简历

启动后同事访问：http://<你的IP>:8000/docs （自动接口文档）
"""
import argparse
import json


def serve(host: str = "0.0.0.0", port: int = 8000):
    """启动 API 服务（持续运行）。"""
    import uvicorn
    print(f"🚀 API 服务启动: http://{host}:{port}")
    print(f"   接口文档: http://{host}:{port}/docs")
    uvicorn.run("api.server:app", host=host, port=port, reload=False)


def run_match():
    """单次：跑匹配评分，写回飞书。"""
    from src.matcher_v2 import run_matching, report_text
    print(report_text(run_matching(write_back=True)))


def parse_resume(text: str):
    """单次：LLM 解析简历文本。"""
    from src.llm_resume_parser import parse_resume_with_llm, llm_result_to_feishu_fields
    parsed = parse_resume_with_llm(text)
    print("=== 解析结果 ===")
    print(json.dumps(parsed, ensure_ascii=False, indent=2))
    print("\n=== 飞书字段 ===")
    print(json.dumps(llm_result_to_feishu_fields(parsed), ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser(description="海信 AI 招聘智能体")
    p.add_argument("--host", default="0.0.0.0", help="API 服务监听地址（默认 0.0.0.0，局域网可访问）")
    p.add_argument("--port", type=int, default=8000, help="API 服务端口（默认 8000）")
    p.add_argument("--match", action="store_true", help="单次跑匹配评分（不启动服务）")
    p.add_argument("--parse", type=str, help="单次解析简历文本（不启动服务）")
    args = p.parse_args()

    if args.parse:
        parse_resume(args.parse)
        return
    if args.match:
        run_match()
        return
    # 默认：启动 API 服务（持续运行）
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
