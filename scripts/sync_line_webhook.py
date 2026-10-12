"""等 ngrok 起來 → 把 LINE webhook 指到 <public_url>/callback → 呼叫 LINE webhook 測試。

用法：uv run python scripts/sync_line_webhook.py [--inspect 127.0.0.1:4040] [--port 8010]
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from line_webhook.endpoint_sync import callback_url, sync_endpoint, wait_for_public_url  # noqa: E402


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", default=os.environ.get("NGROK_INSPECT_ADDR", "127.0.0.1:4040"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("WEBHOOK_PORT", "8010")))
    args = ap.parse_args()

    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        print("⚠️ 未設定 LINE_CHANNEL_ACCESS_TOKEN，略過同步", file=sys.stderr)
        return 1
    with httpx.Client() as client:
        try:
            target = callback_url(wait_for_public_url(args.inspect, args.port, client))
            result = sync_endpoint(target, token, client)
        except (RuntimeError, httpx.HTTPError) as e:
            print(f"⚠️ {e}", file=sys.stderr)
            return 1
    print(f"LINE webhook → {result.endpoint}（{'已更新' if result.changed else '未變動'}）")
    print(f"webhook 測試：{'成功' if result.test_success else '失敗'}（{result.test_detail}）")
    return 0 if result.test_success else 1


if __name__ == "__main__":
    sys.exit(main())
