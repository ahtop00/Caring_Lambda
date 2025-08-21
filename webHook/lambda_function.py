### Ec2ToDiscordWebHook ###
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
import os

def lambda_handler(event, context):
    # 환경 변수에서 웹훅 URL 가져옴
    DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

    # 환경 변수가 설정되었는지 확인
    if not DISCORD_WEBHOOK_URL:
        error_message = "❌ FATAL: Discord webhook URL is not configured. Please set the 'DISCORD_WEBHOOK_URL' environment variable."
        print(error_message)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        }

    try:
        detail = event.get("detail", {})
        event_name = detail.get("eventName", "UnknownEvent")
        user_identity = detail.get("userIdentity", {})
        user_name = user_identity.get("userName", "unknown")
        user_arn = user_identity.get("arn", "unknown")
        event_time_utc = detail.get("eventTime", "unknown")

        # 시간 변환 (UTC -> KST)
        try:
            dt_utc = datetime.strptime(event_time_utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            dt_kst = dt_utc.astimezone(timezone(timedelta(hours=9)))
            event_time_kst = dt_kst.strftime("%Y-%m-%d %H:%M:%S (KST)")
        except Exception as e:
            event_time_kst = f"{event_time_utc} (변환 실패)"

        # 인스턴스 ID 추출
        instance_items = detail.get("requestParameters", {}).get("instancesSet", {}).get("items", [])
        instance_ids = ', '.join([item.get("instanceId", "unknown") for item in instance_items])

        # Discord 메시지 구성
        message = (
            f"📢 **EC2 {event_name} 실행됨**\n"
            f"🖥️ 인스턴스 ID: `{instance_ids}`\n"
            f"👤 사용자: `{user_name}`\n"
            f"🔗 ARN: `{user_arn}`\n"
            f"⏰ 실행 시각: `{event_time_kst}`\n"
        )

        payload = json.dumps({"content": message}).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; DiscordBot/1.0)"
        }

        # DISCORD_WEBHOOK_URL 변수를 사용하여 요청
        req = urllib.request.Request(DISCORD_WEBHOOK_URL, data=payload, headers=headers)

        with urllib.request.urlopen(req) as response:
            print(f"✅ Discord 응답 코드: {response.getcode()}")
            print(f"📦 응답 내용: {response.read().decode('utf-8')}")

        return {"statusCode": 200, "body": "Notification sent successfully"}

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ HTTPError: {e.code} - {error_body}")
        return {"statusCode": e.code, "body": f"HTTPError: {error_body}"}

    except urllib.error.URLError as e:
        print(f"❌ URLError: {e.reason}")
        return {"statusCode": 500, "body": f"URLError: {e.reason}"}

    except Exception as e:
        print(f"❌ Exception: {e}")
        return {"statusCode": 500, "body": f"Exception: {str(e)}"}