"""
Telegram webhook for MargAI Ghost Tutor: receive message, map chat_id -> institute_id, RAG or escalate.
- Validate X-Telegram-Bot-Api-Secret-Token. Map chat_id to institute_id via Supabase (pilot: default 1).
- Insert query_logs; embed query; Pinecone query namespace=institute_id; Gemini gemini-2.5-flash.
- If ESCALATE: send clarifying message, set clarification_sent. If next message is "escalate": notify TA.
- Observability: log request duration (webhook received -> reply sent).
"""
import json
import logging
import os
import sys
import time
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone
from pathlib import Path

# Project root = parent of api/
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supabase import create_client
import google.generativeai as genai
from pinecone import Pinecone
import httpx

from lib.embedding import get_embedding
from lib.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# --- Telegram helpers ---
def send_telegram(bot_token: str, method: str, payload: dict) -> dict | None:
    """POST to Telegram Bot API. Returns JSON or None on failure."""
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.exception("Telegram API %s failed: %s", method, e)
        return None


def send_message(bot_token: str, chat_id: int | str, text: str) -> bool:
    return send_telegram(bot_token, "sendMessage", {"chat_id": chat_id, "text": text}) is not None


def get_file_url(bot_token: str, file_id: str) -> str | None:
    """Get download URL for a file_id (e.g. photo)."""
    data = send_telegram(bot_token, "getFile", {"file_id": file_id})
    if not data or not data.get("ok"):
        return None
    path = data.get("result", {}).get("file_path")
    if not path:
        return None
    return f"https://api.telegram.org/file/bot{bot_token}/{path}"


# --- Institute mapping: chat_id -> institute_id (pilot: default 1) ---
def resolve_institute_id(supabase, chat_id: int | str) -> int:
    """Map chat_id to institute_id. Pilot: single institute (env INSTITUTE_ID_DEFAULT=1)."""
    default = int(os.environ.get("INSTITUTE_ID_DEFAULT", "1"))
    # Optional: lookup from a mapping table if present, e.g. bot_chats(chat_id, institute_id)
    try:
        r = supabase.table("institutes").select("id").limit(1).execute()
        if r.data and len(r.data) > 0:
            return int(r.data[0]["id"])
    except Exception as e:
        logger.debug("resolve_institute_id lookup failed, using default: %s", e)
    return default


# --- RAG: embed, query Pinecone, Gemini generateContent ---
KNOWLEDGE_LOCK_SYSTEM = (
    "You are an assistant for the institute. Use ONLY the provided context to answer. "
    "If the answer is not in the context, do not make it up. Instead, say: "
    "'This wasn't covered in our current notes. I've flagged this for your teacher!' "
    "If you cannot answer from context, respond with exactly: ESCALATE. "
    "You may use general English/Math logic to explain steps; never introduce new outside facts."
)


def run_rag(
    query_text: str,
    institute_id: int,
    gemini_api_key: str,
    pinecone_api_key: str,
    index_name: str,
) -> tuple[str, list[dict]]:
    """
    Embed query, query Pinecone (namespace=institute_id), build prompt, call Gemini.
    Returns (response_text, context_chunks).
    """
    if not query_text or not query_text.strip():
        query_text = "student sent an image or empty message"
    query_embedding = get_embedding(
        query_text.strip(),
        gemini_api_key,
        task_type="retrieval_query",
    )
    pc = Pinecone(api_key=pinecone_api_key)
    index = pc.Index(index_name)
    ns = str(institute_id)
    result = index.query(
        vector=query_embedding,
        namespace=ns,
        top_k=10,
        include_metadata=True,
    )
    matches = result.get("matches") or []
    context_parts = []
    for m in matches:
        meta = m.get("metadata") or {}
        if meta.get("text"):
            context_parts.append(meta["text"])
    context = "\n\n".join(context_parts) if context_parts else "(No relevant passages found.)"
    prompt = f"Context from study material:\n{context}\n\nStudent question: {query_text}"
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(
        [KNOWLEDGE_LOCK_SYSTEM, prompt],
    )
    response_text = (response.text or "").strip()
    return response_text, [{"text": t} for t in context_parts]


def normalize_escalate(text: str) -> str:
    return (text or "").strip().upper()


# --- Webhook handler ---
class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        t_start = time.perf_counter()
        if self.path != "/api/telegram_webhook" and not self.path.endswith("telegram_webhook"):
            self.send_response(404)
            self.end_headers()
            return

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""
        secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
        if webhook_secret and secret != webhook_secret:
            logger.warning("Invalid or missing webhook secret")
            self.send_response(200)  # Still 200 to avoid Telegram retries
            self.end_headers()
            return

        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            self.send_response(200)
            self.end_headers()
            return

        message = data.get("message") or data.get("edited_message")
        if not message:
            self.send_response(200)
            self.end_headers()
            return

        chat_id = message.get("chat", {}).get("id")
        if chat_id is None:
            logger.warning("Missing chat.id in Telegram update")
            self.send_response(200)
            self.end_headers()
            return
        from_user = message.get("from") or {}
        student_telegram_id = str(from_user.get("id", ""))
        student_name = (from_user.get("first_name") or "") + " " + (from_user.get("last_name") or "")
        text = (message.get("text") or "").strip()
        photo = message.get("photo")
        is_photo = bool(photo)
        query_text = text or ("[photo]" if is_photo else "")

        # Env
        settings = get_settings()
        supabase_url = os.environ.get("SUPABASE_URL") or settings.supabase_url
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or settings.supabase_service_role_key
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN") or settings.telegram_bot_token
        gemini_key = os.environ.get("GEMINI_API_KEY") or settings.gemini_api_key
        pinecone_key = os.environ.get("PINECONE_API_KEY") or settings.pinecone_api_key
        index_name = os.environ.get("PINECONE_INDEX_NAME") or settings.pinecone_index_name or "margai-ghost-tutor"

        if not all([supabase_url, supabase_key, bot_token, gemini_key, pinecone_key]):
            logger.error("Missing env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, PINECONE_API_KEY")
            self.send_response(200)
            self.end_headers()
            return

        sb = create_client(supabase_url, supabase_key)
        institute_id = resolve_institute_id(sb, chat_id)

        # Escalate intent: user replied "escalate" after a clarifying question
        if normalize_escalate(text) in ("ESCALATE", "SEND TO TA", "FORWARD TO TA"):
            r = sb.table("query_logs").select("id,query_text,is_photo").eq("student_telegram_id", student_telegram_id).eq("clarification_sent", True).eq("escalated", False).order("timestamp", desc=True).limit(1).execute()
            if r.data and len(r.data) > 0:
                row = r.data[0]
                sb.table("query_logs").update({"escalated": True}).eq("id", row["id"]).execute()
                send_message(bot_token, chat_id, "We've escalated your doubt to your TA – they'll get back to you.")
                # Notify TA
                inst = sb.table("institutes").select("ta_telegram_id").eq("id", institute_id).execute()
                ta_id = (inst.data or [{}])[0].get("ta_telegram_id") if inst.data else None
                if ta_id:
                    msg = f"From: {student_telegram_id} ({student_name})\n\n{row.get('query_text') or '[photo]'}"
                    send_message(bot_token, ta_id, msg)
                self.send_response(200)
                self.end_headers()
                logger.info("request_duration_seconds=%.2f action=escalate", time.perf_counter() - t_start)
                return

        # Insert query_logs
        ins = sb.table("query_logs").insert({
            "institute_id": institute_id,
            "student_telegram_id": student_telegram_id,
            "student_name": student_name.strip() or None,
            "query_text": query_text or None,
            "is_photo": is_photo,
            "escalated": False,
            "clarification_sent": False,
        }).execute()
        log_id = (ins.data or [{}])[0].get("id") if ins.data else None

        # RAG
        try:
            response_text, _ = run_rag(query_text or "student sent an image", institute_id, gemini_key, pinecone_key, index_name)
        except Exception as e:
            logger.exception("RAG failed: %s", e)
            send_message(bot_token, chat_id, "Something went wrong, please try again.")
            if log_id:
                sb.table("query_logs").update({"replied_at": datetime.now(timezone.utc).isoformat()}).eq("id", log_id).execute()
            self.send_response(200)
            self.end_headers()
            return

        normalized = normalize_escalate(response_text)

        if normalized == "ESCALATE":
            send_message(
                bot_token,
                chat_id,
                "I couldn't find a clear answer in your study material. Could you add a bit more detail (e.g. chapter or topic) or rephrase? If you'd prefer to send this to your TA, reply with **escalate**.",
            )
            if log_id:
                sb.table("query_logs").update({"clarification_sent": True}).eq("id", log_id).execute()
        else:
            send_message(bot_token, chat_id, response_text)
            if log_id:
                sb.table("query_logs").update({"replied_at": datetime.now(timezone.utc).isoformat()}).eq("id", log_id).execute()

        self.send_response(200)
        self.end_headers()
        logger.info("request_duration_seconds=%.2f action=reply", time.perf_counter() - t_start)

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Telegram webhook OK")
