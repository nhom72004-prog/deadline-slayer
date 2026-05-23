import streamlit as st
from datetime import datetime
import pandas as pd
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from zoneinfo import ZoneInfo
import json
import os
import random

# --- TẠO CHÌA KHÓA TRÊN CLOUD TỪ SECRETS ---
if not os.path.exists("credentials.json"):
    if "gcp_service_account" in st.secrets:
        with open("credentials.json", "w") as f:
            json.dump(dict(st.secrets["gcp_service_account"]), f)

# ─── TIMEZONE CONFIG ────────────────────────────────────────
TZ = ZoneInfo("Asia/Ho_Chi_Minh")
def NOW():
    return datetime.now(TZ)

# ─── PAGE CONFIGURATION ──────────────────────────────────────
st.set_page_config(
    page_title="Deadline Slayer ⚔️",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "sheet_name" not in st.session_state:
    st.session_state["sheet_name"] = "DeadlineSlayer_DB"
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'current_user' not in st.session_state:
    st.session_state['current_user'] = None

# ─── CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
[data-testid="metric-container"] {
    background: #16161a; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px; padding: 16px !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.2);
}
.stButton > button[kind="primary"] {
    background: #5865F2; border: none; border-radius: 8px;
    font-weight: 700; color: white;
}
.stButton > button[kind="primary"]:hover { background: #404EED; }
.chat-card {
    background: #1e1f22; border-radius: 8px; padding: 10px 14px;
    margin-bottom: 8px; border: 1px solid #2b2d31;
}
.chat-private {
    background: #1a233a; border-radius: 8px; padding: 10px 14px;
    margin-bottom: 8px; border: 1px solid #3b4898;
}
.chat-me {
    background: #1a2e1a; border-radius: 8px; padding: 10px 14px;
    margin-bottom: 8px; border: 1px solid #2d6a2d;
}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
#  1. GOOGLE SHEETS SCHEMA
# ═══════════════════════════════════════════════════════════

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

WS_TASKS  = "Tasks"
WS_USERS  = "Users"
WS_GROUPS = "Groups"
WS_PROOFS = "Proofs"
WS_CHAT   = "ChatRoom"
WS_DM     = "DirectMessages"

TASK_COLS  = ["ID", "Tên_Công_Việc", "Môn_Học", "Người_Phụ_Trách_ID", "Deadline",
              "Độ_Ưu_Tiên", "Trạng_Thái", "Tiến_Độ_%", "Giai_Đoạn_Hiện_Tại",
              "Ghi_Chú", "Nhắc_Mỗi_Phút", "Nhắc_Lần_Cuối", "Ngày_Tạo", "Ngày_Cập_Nhật"]
USER_COLS  = ["User_ID", "Password", "Tên", "Email", "Bạn_Bè", "Discord_Webhook_DM", "Ngày_Tạo"]
GROUP_COLS = ["Group_ID", "Tên_Nhóm", "Trưởng_Nhóm_ID", "Thành_Viên_IDs", "Discord_Webhook", "Ngày_Tạo"]
PROOF_COLS = ["Task_ID", "Người_Nộp_ID", "Thời_Gian", "Mô_Tả", "Giai_Đoạn", "URL_File"]
CHAT_COLS  = ["Thời_Gian", "Người_Gửi_ID", "Group_Nhận_ID", "Nội_Dung"]
DM_COLS    = ["Thời_Gian", "Người_Gửi_ID", "Người_Nhận_ID", "Nội_Dung"]

# ═══════════════════════════════════════════════════════════
#  2. LỜI NHẮN VUI VẺ — RANDOM THEO TỪNG LOẠI SỰ KIỆN
# ═══════════════════════════════════════════════════════════

def msg_login_success(name):
    options = [
        f"⚔️ Chào chiến binh **{name}**! Deadline đang run rẩy trước sự hiện diện của bạn!",
        f"🔥 YO **{name}**! Sẵn sàng nghiền nát deadline chưa? Let's GOOO!",
        f"🛡️ **{name}** đã vào trận! Hôm nay chúng ta chinh phục deadline nào?",
        f"🎮 Player **{name}** đã online! Cả team đang chờ bạn flex não đây~",
        f"✨ Ơ kìa **{name}** đã xuất hiện rồi! Deadline thấy bạn là đã sợ rồi đó!",
    ]
    return random.choice(options)

def msg_login_fail():
    options = [
        "🤔 Hmm... ID hay mật khẩu có vẻ sai sai? Thử lại xem sao!",
        "🙈 Ồ ồ, thông tin không khớp rồi! Hay là bạn đang nhập pass của acc game? 😂",
        "❌ Không tìm thấy tài khoản này! Kiểm tra lại ID và mật khẩu nhé bro~",
        "🔐 Cửa không mở! Sai chìa khóa rồi, thử lại nhé!",
    ]
    return random.choice(options)

def msg_register_success(new_id):
    options = [
        f"🎉 WELCOME TO THE SQUAD! ID của bạn là **`{new_id}`** — nhớ kỹ nhé, mất là khóc đó!",
        f"🚀 Tài khoản **`{new_id}`** đã được khai sinh! Chiến binh mới đã gia nhập chiến trường!",
        f"🎊 Yayyy! **`{new_id}`** chào đời rồi! Đây là ID của bạn, đừng để mất nha~",
        f"🦾 Đăng ký thành công! ID **`{new_id}`** — lưu lại ngay đi, deadline không chờ đâu!",
    ]
    return random.choice(options)

def msg_task_assigned(task_name, assignee_name):
    options = [
        f"🚀 Lệnh đã ban! **{assignee_name}** vừa nhận nhiệm vụ **{task_name}** — cố lên nào!",
        f"📋 Xong xuôi! **{task_name}** đã được giao cho **{assignee_name}** rồi. Go go go!",
        f"⚡ Giao việc thành công! **{assignee_name}** ơi, **{task_name}** đang chờ bạn kìa~",
        f"🎯 Đã bắn lệnh! **{task_name}** → **{assignee_name}**. Chúc may mắn nhé!",
    ]
    return random.choice(options)

def msg_progress_saved(percent):
    if percent == 100:
        opts = [
            "🏆 BOOOM! 100%! Bạn vừa hạ gục deadline! Tuyệt vời quá điiiii!",
            "🎉 100% rồi! Chill thôi bro, task này chính thức về tay bạn rồi!",
            "✅ Xong sạch! Task đã được khắc tên vào bảng vàng chiến thắng!",
        ]
    elif percent >= 75:
        opts = [
            f"💪 {percent}%! Sắp về đích rồi! Một chút nữa thôi, đừng bỏ cuộc!",
            f"🔥 {percent}%! Gần xong rồi bro ơi! Cố thêm chút xíu nữa!",
            f"⚡ {percent}%! Đang bay nhanh lắm! Deadline chạy không kịp bạn đâu!",
        ]
    elif percent >= 50:
        opts = [
            f"🌗 {percent}%! Nửa đường rồi! Tiếp tục nào, không dừng ở đây!",
            f"💡 {percent}%! Đang đà tốt đấy! Keep the momentum!",
            f"🎮 {percent}%! Checkpoint đã lưu! Tiến về phía trước nào!",
        ]
    else:
        opts = [
            f"🌱 {percent}%! Bước đầu tiên luôn khó nhất — bạn đã bắt đầu rồi, tuyệt!",
            f"🚀 {percent}%! Đã lưu! Mỗi % đều là chiến thắng nhỏ nhé!",
            f"✏️ {percent}%! Oke! Hành trình vạn dặm bắt đầu từ đây!",
        ]
    return random.choice(opts)

def msg_friend_added(name):
    options = [
        f"🤝 **{name}** đã vào danh sách bạn bè! Cùng nhau chinh phục deadline nào~",
        f"👯 YAY! **{name}** và bạn giờ là đồng đội rồi! Welcome to the squad!",
        f"🎉 Kết bạn thành công với **{name}**! Cả team strong hơn rồi!",
        f"💫 **{name}** đã được thêm vào list bạn bè! Tương lai sẽ cùng nhau cày deadline!",
    ]
    return random.choice(options)

def msg_group_created(grp_name):
    options = [
        f"🏰 Nhóm **{grp_name}** đã được thành lập! Trưởng nhóm ơi, dẫn dắt team đến vinh quang nhé!",
        f"🎊 **{grp_name}** chính thức ra đời! Cùng nhau phá đảo môn học nào!",
        f"⚔️ Biệt đội **{grp_name}** đã tập hợp! Ready to slay some deadlines?!",
        f"🚀 LAUNCH! Nhóm **{grp_name}** đã cất cánh! Không deadline nào có thể cản bước!",
    ]
    return random.choice(options)

def msg_group_updated():
    options = [
        "💾 Nhóm đã được nâng cấp! Thay đổi đã lưu thành công rồi~",
        "✅ Xong! Thông tin nhóm đã được cập nhật. Fresh start nào!",
        "🔧 Đã tune nhóm xong! Giờ ngon hơn rồi đó!",
    ]
    return random.choice(options)

def msg_group_deleted():
    options = [
        "💥 Nhóm đã giải tán! Mỗi hành trình đều có hồi kết. Hẹn gặp lại ở chiến tuyến mới!",
        "👋 Nhóm đã bị xóa thành công! Chia tay nhé, hope to work together again!",
        "🌅 Nhóm đã kết thúc sứ mệnh! Đã xóa sạch rồi~",
    ]
    return random.choice(options)

def msg_proof_sent():
    options = [
        "📤 Bằng chứng đã bay lên Discord! Trưởng nhóm đã nhận được rồi đó~",
        "🚀 File minh chứng đã được phóng lên Discord thành công! Chill thôi!",
        "✅ Đã nộp! Minh chứng đã chạm đến Discord nhóm. Bạn đã hoàn thành bổn phận!",
        "🎯 Đã đẩy file lên Discord rồi! Xong việc, ngồi thở cái nào~",
    ]
    return random.choice(options)

def msg_chat_sent_group():
    options = [
        "💬 Tin nhắn đã gửi! Cả nhóm đang đọc rồi đó~",
        "📨 Bay đến nhóm rồi! Chờ mọi người reply nhé!",
        "⚡ Sent! Tin nhắn đã đến tay cả team!",
    ]
    return random.choice(options)

def msg_dm_sent():
    options = [
        "🔒 Tin nhắn bí mật đã được gửi đi! Chỉ có 2 người biết thôi nhé~",
        "📩 DM thành công! Hy vọng họ reply nhanh cho bạn!",
        "💌 Tin nhắn riêng đã bay đến nơi! Bạn thật tâm lý~",
        "🤫 Psst! Tin nhắn đã đến tay người nhận rồi!",
    ]
    return random.choice(options)

def msg_webhook_saved():
    options = [
        "🤖 Discord Webhook đã được kết nối! Bot của bạn đã sẵn sàng chiến đấu!",
        "🔔 Webhook lưu xong! Từ giờ Discord của bạn sẽ sôi động hơn nhiều~",
        "✅ Đã lưu Webhook! Mọi thông báo sẽ bay thẳng vào Discord rồi!",
    ]
    return random.choice(options)

def msg_account_deleted(uid):
    options = [
        f"💨 Tài khoản `{uid}` đã bay màu! Bye bye~",
        f"🗑️ `{uid}` đã được xóa sạch! Gone like the wind!",
        f"✂️ Tài khoản `{uid}` đã chính thức nghỉ hưu. Đã xóa thành công!",
    ]
    return random.choice(options)

def msg_discord_broadcast(leader_name):
    options = [
        f"📢 **[THÔNG BÁO ĐỎ TỪ TRƯỞNG NHÓM {leader_name.upper()}]** 🔴\n",
        f"🚨 **[{leader_name.upper()} CÓ LỆNH MỚI]** 📣\n",
        f"⚡ **[TIN NÓNG TỪ SẾP {leader_name.upper()}]** 👇\n",
        f"📡 **[PHÁT SÓNG KHẨN TỪ {leader_name.upper()}]** 🎙️\n",
    ]
    return random.choice(options)

# Discord messages
def discord_task_assigned(task_name, assignee_name, deadline, priority):
    emojis = ["🚨", "⚡", "🔥", "💥", "🎯"]
    e = random.choice(emojis)
    prio_map = {"Cao": "🔴 KHẨN CẤP", "Trung bình": "🟡 Bình thường", "Thấp": "🟢 Thư thả"}
    prio_label = prio_map.get(priority, priority)
    return (
        f"{e} **NHIỆM VỤ MỚI XUẤT HIỆN!** {e}\n"
        f"📌 **{task_name}**\n"
        f"👤 Chiến binh được chọn: **{assignee_name}**\n"
        f"⏰ Hạn chót: `{deadline}`\n"
        f"🏷️ Độ ưu tiên: {prio_label}\n"
        f"💪 *Cố lên nào! Cả team tin bạn!*"
    )

def discord_group_created(grp_name):
    return (
        f"🎊 **BIỆT ĐỘI MỚI ĐÃ THÀNH LẬP!**\n"
        f"🏰 Nhóm **{grp_name}** chính thức ra đời!\n"
        f"⚔️ *Không có deadline nào là không thể chinh phục!*\n"
        f"🚀 Let's GOOOOO!!!"
    )

def discord_proof_sent(assignee_name, task_name):
    emojis = ["✅", "🎯", "💪", "🏆", "🔥"]
    e = random.choice(emojis)
    return (
        f"{e} **MINH CHỨNG ĐÃ NỘP!**\n"
        f"👤 **{assignee_name}** vừa nộp bằng chứng cho:\n"
        f"📋 Task: **{task_name}**\n"
        f"👆 *Check file ở trên nhé trưởng nhóm ơi~*"
    )

def discord_dm(sender_name, content):
    return (
        f"📩 **Tin nhắn riêng từ {sender_name}:**\n"
        f"{content}\n"
        f"*(Trả lời trên Deadline Slayer nhé!)*"
    )

def discord_group_chat(sender_name, group_label, content):
    return f"💬 **{sender_name}** › [{group_label}]:\n{content}"

# ═══════════════════════════════════════════════════════════
#  3. GOOGLE SHEETS CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════

@st.cache_resource(ttl=15)
def get_sheets_client():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPES)
        return gspread.authorize(creds)
    except Exception:
        return None

def init_spreadsheet_structure(ss):
    existing = [ws.title for ws in ss.worksheets()]
    schemas = {
        WS_TASKS:  TASK_COLS,
        WS_USERS:  USER_COLS,
        WS_GROUPS: GROUP_COLS,
        WS_PROOFS: PROOF_COLS,
        WS_CHAT:   CHAT_COLS,
        WS_DM:     DM_COLS,
    }
    for name, cols in schemas.items():
        if name not in existing:
            ws = ss.add_worksheet(title=name, rows=1000, cols=len(cols))
            ws.append_row(cols)

@st.cache_data(ttl=1)
def fetch_all_data():
    client = get_sheets_client()
    empty_dict = {
        "tasks":  pd.DataFrame(columns=TASK_COLS),
        "users":  pd.DataFrame(columns=USER_COLS),
        "groups": pd.DataFrame(columns=GROUP_COLS),
        "proofs": pd.DataFrame(columns=PROOF_COLS),
        "chat":   pd.DataFrame(columns=CHAT_COLS),
        "dm":     pd.DataFrame(columns=DM_COLS),
    }
    if not client:
        return empty_dict
    try:
        ss = client.open(st.session_state["sheet_name"])
        init_spreadsheet_structure(ss)

        def get_df(name, cols):
            all_vals = ss.worksheet(name).get_all_values()
            if not all_vals or len(all_vals) <= 1:
                return pd.DataFrame(columns=cols)
            df = pd.DataFrame(all_vals[1:], columns=all_vals[0])
            df = df.loc[:, ~df.columns.duplicated()]
            if "" in df.columns:
                df = df.drop(columns=[""])
            return df.reindex(columns=cols).fillna("")

        return {
            "tasks":  get_df(WS_TASKS,  TASK_COLS),
            "users":  get_df(WS_USERS,  USER_COLS),
            "groups": get_df(WS_GROUPS, GROUP_COLS),
            "proofs": get_df(WS_PROOFS, PROOF_COLS),
            "chat":   get_df(WS_CHAT,   CHAT_COLS),
            "dm":     get_df(WS_DM,     DM_COLS),
        }
    except Exception:
        return empty_dict

def get_worksheet_target(name: str):
    client = get_sheets_client()
    if not client:
        return None
    try:
        return client.open(st.session_state["sheet_name"]).worksheet(name)
    except Exception:
        return None

def append_row_data(name: str, row: list):
    import time
    ws = get_worksheet_target(name)
    if ws:
        ws.append_row(row, value_input_option="USER_ENTERED")
        time.sleep(0.5)
        fetch_all_data.clear()

def update_cell_by_id(ws_name, id_col_name, item_id, update_col_name, new_val, schema_cols):
    ws = get_worksheet_target(ws_name)
    if not ws:
        return
    try:
        id_col_idx     = schema_cols.index(id_col_name) + 1
        update_col_idx = schema_cols.index(update_col_name) + 1
        cell = ws.find(str(item_id))
        if cell and cell.col == id_col_idx:
            ws.update_cell(cell.row, update_col_idx, new_val)
            fetch_all_data.clear()
    except Exception as e:
        st.error(f"💀 Ôi thôi, lỗi đồng bộ rồi: {e}")

def delete_row_by_id(ws_name, id_col_name, item_id, schema_cols):
    ws = get_worksheet_target(ws_name)
    if not ws:
        return False
    try:
        id_col_idx = schema_cols.index(id_col_name) + 1
        cell = ws.find(str(item_id))
        if cell and cell.col == id_col_idx:
            ws.delete_rows(cell.row)
            fetch_all_data.clear()
            return True
        return False
    except Exception as e:
        st.error(f"💀 Xóa thất bại rồi bro: {e}")
        return False

# ═══════════════════════════════════════════════════════════
#  4. DISCORD & HELPERS
# ═══════════════════════════════════════════════════════════

def push_to_discord(message: str, webhook_url: str = "", file_bytes=None, filename: str = None) -> bool:
    if not webhook_url or "discord.com/api/webhooks" not in webhook_url:
        return False
    try:
        if file_bytes and filename:
            resp = requests.post(webhook_url, data={"content": message},
                                 files={"file": (filename, file_bytes)}, timeout=15)
        else:
            resp = requests.post(webhook_url, json={"content": message}, timeout=5)
        return resp.status_code in (200, 204)
    except Exception as e:
        st.warning(f"🤖 Bot gặp sự cố khi gửi Discord: {str(e)}")
        return False

def get_group_webhook(group_id: str, groups_df: pd.DataFrame) -> str:
    match = groups_df[groups_df["Group_ID"] == group_id]
    if match.empty:
        return ""
    return str(match.iloc[0].get("Discord_Webhook", "")).strip()

def get_user_dm_webhook(user_id: str, users_df: pd.DataFrame) -> str:
    match = users_df[users_df["User_ID"] == user_id]
    if match.empty:
        return ""
    return str(match.iloc[0].get("Discord_Webhook_DM", "")).strip()

def clean_and_parse_progress(val):
    if pd.isna(val) or val == "":
        return 0.0
    try:
        return float(str(val).replace("%", "").strip())
    except ValueError:
        return 0.0

def parse_deadline_timezone(dl_str: str):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(str(dl_str).strip(), fmt).replace(tzinfo=TZ)
        except ValueError:
            continue
    return None

def calculate_task_status(row: pd.Series) -> str:
    if str(row.get("Trạng_Thái", "")) == "Đã xong" or clean_and_parse_progress(row.get("Tiến_Độ_%")) == 100.0:
        return "done"
    dl = parse_deadline_timezone(row.get("Deadline", ""))
    if dl is None:
        return "unknown"
    diff_hours = (dl - NOW()).total_seconds() / 3600
    if diff_hours < 0:   return "overdue"
    if diff_hours <= 24: return "urgent"
    if diff_hours <= 72: return "warning"
    return "safe"

def format_time_remaining(row: pd.Series) -> str:
    if str(row.get("Trạng_Thái", "")) == "Đã xong":
        return "Xong sạch rồi 🎉"
    dl = parse_deadline_timezone(row.get("Deadline", ""))
    if dl is None:
        return "—"
    total_seconds = int((dl - NOW()).total_seconds())
    if total_seconds < 0:
        return "ĐÃ QUÁ HẠN! Chạy ngay đi 🛑"
    days, rem  = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days > 3:   return f"⏳ Còn {days} ngày {hours} giờ — th余裕 lắm!"
    if days > 0:   return f"⚡ Còn {days} ngày {hours} giờ {minutes} phút — cố lên!"
    if hours > 3:  return f"🔥 Còn {hours} giờ {minutes} phút — nhanh lên nào!"
    if hours > 0:  return f"🚨 Chỉ còn {hours} giờ {minutes} phút — KHẨN CẤP!"
    return f"💀 Chỉ còn {minutes} phút!!! FULL SEND!!!"

def get_user_name(user_id, users_df):
    match = users_df[users_df["User_ID"] == user_id]
    return match.iloc[0]["Tên"] if not match.empty else f"Ẩn danh ({user_id})"

# ═══════════════════════════════════════════════════════════
#  5. AUTH SYSTEM
# ═══════════════════════════════════════════════════════════

def show_auth_page(data):
    users_df = data["users"]
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🛡️ DEADLINE SLAYER</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #888;'>Nền tảng quản lý học tập & Giao việc nhóm</p>", unsafe_allow_html=True)

        tab_login, tab_reg = st.tabs(["🔑 Đăng Nhập", "📝 Đăng Ký Tài Khoản"])

        with tab_login:
            st.subheader("Đăng nhập hệ thống")
            log_id   = st.text_input("User ID (VD: U001)", key="log_id").strip()
            log_pass = st.text_input("Mật khẩu", type="password", key="log_pass")
            if st.button("🚀 Đăng Nhập", use_container_width=True, type="primary"):
                fetch_all_data.clear()
                fresh_data  = fetch_all_data()
                fresh_users = fresh_data["users"]
                if fresh_users.empty:
                    st.error("👻 Chưa có ai ở đây cả! Hãy đăng ký tài khoản đầu tiên đi!")
                else:
                    user_match = fresh_users[
                        (fresh_users["User_ID"] == log_id) &
                        (fresh_users["Password"] == log_pass)
                    ]
                    if not user_match.empty:
                        name = user_match.iloc[0]["Tên"]
                        st.session_state['logged_in']    = True
                        st.session_state['current_user'] = user_match.iloc[0].to_dict()
                        st.success(msg_login_success(name))
                        st.rerun()
                    else:
                        st.error(msg_login_fail())

        with tab_reg:
            st.subheader("Tạo tài khoản mới")
            reg_name  = st.text_input("Họ và Tên",  key="reg_name").strip()
            reg_email = st.text_input("Email",       key="reg_email").strip()
            reg_pass  = st.text_input("Mật khẩu",   type="password", key="reg_pass")
            reg_wh_dm = st.text_input(
                "🤖 Discord Webhook cá nhân (tuỳ chọn):",
                placeholder="https://discord.com/api/webhooks/...",
                help="Bot sẽ gửi tin nhắn riêng (DM) từ bạn bè vào kênh Discord cá nhân của bạn.",
                key="reg_wh_dm"
            ).strip()

            if st.button("✨ Tạo Tài Khoản", use_container_width=True):
                if not reg_name or not reg_email or not reg_pass:
                    st.error("🙏 Điền đủ thông tin giúp mình với nha! Bỏ trống là không được đâu~")
                else:
                    fetch_all_data.clear()
                    fresh_users = fetch_all_data()["users"]
                    if not fresh_users.empty and reg_email in fresh_users["Email"].values:
                        st.error("📧 Email này đã có người dùng rồi! Thử email khác xem nào~")
                    else:
                        if fresh_users.empty:
                            new_id = "U001"
                        else:
                            ids  = fresh_users["User_ID"].dropna().astype(str).tolist()
                            nums = [int(i[1:]) for i in ids if i.startswith("U") and i[1:].isdigit()]
                            new_id = f"U{(max(nums) + 1 if nums else 1):03d}"

                        append_row_data(WS_USERS, [
                            new_id, reg_pass, reg_name, reg_email, "",
                            reg_wh_dm,
                            NOW().strftime("%Y-%m-%d %H:%M:%S")
                        ])
                        fetch_all_data.clear()
                        st.success(msg_register_success(new_id))

# ═══════════════════════════════════════════════════════════
#  6. MAIN APP
# ═══════════════════════════════════════════════════════════

def main_app(data):
    users_df  = data["users"]
    groups_df = data["groups"]
    tasks_df  = data["tasks"]
    current_user = st.session_state['current_user']
    my_id = current_user["User_ID"]

    is_leader = not groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id].empty

    with st.sidebar:
        st.markdown("## ⚔️ DEADLINE SLAYER")
        st.markdown("---")
        st.success(f"👤 **{current_user['Tên']}**\n\n🆔 ID: `{my_id}`")
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state['logged_in']    = False
            st.session_state['current_user'] = None
            st.rerun()

        st.markdown("---")
        st.subheader("⚙️ Cấu hình")
        s_name = st.text_input("Tên Google Sheets", value=st.session_state["sheet_name"])
        if s_name != st.session_state["sheet_name"]:
            st.session_state["sheet_name"] = s_name
            fetch_all_data.clear()
            st.rerun()

        st.markdown("---")
        st.markdown("### 🔔 Discord Webhook Cá Nhân")
        my_row    = users_df[users_df["User_ID"] == my_id]
        cur_wh_dm = str(my_row.iloc[0].get("Discord_Webhook_DM", "")).strip() if not my_row.empty else ""
        new_wh_dm = st.text_input(
            "Webhook nhận DM của bạn:",
            value=cur_wh_dm,
            placeholder="https://discord.com/api/webhooks/...",
            help="Tin nhắn riêng gửi đến bạn sẽ được đẩy về đây.",
            key="sidebar_wh_dm"
        ).strip()
        if st.button("💾 Lưu Webhook DM", use_container_width=True):
            update_cell_by_id(WS_USERS, "User_ID", my_id, "Discord_Webhook_DM", new_wh_dm, USER_COLS)
            fetch_all_data.clear()
            st.toast(msg_webhook_saved())

        if is_leader:
            st.markdown("---")
            st.markdown("### 🤖 Bảng Điều Khiển Bot Nhóm")
            my_groups = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
            grp_opts  = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in my_groups.iterrows()}
            sel_grp   = st.selectbox("Chọn nhóm:", options=list(grp_opts.keys()), format_func=lambda x: grp_opts[x])
            msg_text  = st.text_area("Nội dung thông báo:")
            admin_file = st.file_uploader("📎 Đính kèm file (Tuỳ chọn)")
            if st.button("🚀 Bắn Lệnh Lên Discord", use_container_width=True, type="primary"):
                wh  = get_group_webhook(sel_grp, groups_df)
                msg = discord_msg_broadcast = msg_discord_broadcast(current_user['Tên']) + msg_text
                if admin_file:
                    success = push_to_discord(msg, webhook_url=wh, file_bytes=admin_file.getvalue(), filename=admin_file.name)
                else:
                    success = push_to_discord(msg, webhook_url=wh)
                if success:
                    st.toast("🚀 Thông báo đã được bắn thành công lên Discord!")
                else:
                    st.toast("😥 Gửi thất bại! Kiểm tra lại Discord Webhook nhé~")

        st.markdown("---")
        if st.button("🔄 Làm mới dữ liệu", use_container_width=True):
            fetch_all_data.clear()
            st.rerun()

    t1, t2, t3, t4, t5, t6 = st.tabs([
        "📊 Dashboard Công Việc",
        "👥 Kết Bạn & Tạo Nhóm",
        "📋 Giao Việc Mới",
        "💬 Chat",
        "🏆 Xếp Hạng",
        "🗑️ Quản Lý Tài Khoản",
    ])

    me_in_db        = users_df[users_df["User_ID"] == my_id].iloc[0]
    my_friends_list = [f.strip() for f in str(me_in_db["Bạn_Bè"]).split(",") if f.strip()]

    with t1: render_dashboard(tasks_df, groups_df, users_df, my_id, is_leader)
    with t2: render_network(users_df, groups_df, my_id, my_friends_list)
    with t3: render_assign_task(users_df, groups_df, tasks_df, my_id, my_friends_list)
    with t4: render_chat(data["chat"], data["dm"], groups_df, users_df, my_id, my_friends_list)
    with t5: render_leaderboard(tasks_df, users_df)
    with t6: render_account_management(users_df, my_id)


# ═══════════════════════════════════════════════════════════
#  7. TAB 1: DASHBOARD
# ═══════════════════════════════════════════════════════════

def render_dashboard(tasks_df, groups_df, users_df, my_id, is_leader):
    st.subheader("📊 Bảng Tiến Độ Cá Nhân & Nhóm")

    my_groups    = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
    subordinates = []
    for _, grp in my_groups.iterrows():
        subordinates.extend([m.strip() for m in str(grp["Thành_Viên_IDs"]).split(",") if m.strip()])

    visible_tasks = tasks_df[
        (tasks_df["Người_Phụ_Trách_ID"] == my_id) |
        (tasks_df["Người_Phụ_Trách_ID"].isin(subordinates))
    ].copy()

    if visible_tasks.empty:
        st.info("🎉 Trống trơn! Chưa có nhiệm vụ nào cả — hãy tận hưởng khoảnh khắc này đi!")
        return

    visible_tasks["Tiến_Độ_%"]  = visible_tasks["Tiến_Độ_%"].apply(clean_and_parse_progress)
    visible_tasks["_status"]     = visible_tasks.apply(calculate_task_status, axis=1)
    visible_tasks["_remaining"]  = visible_tasks.apply(format_time_remaining, axis=1)

    status_labels = {
        "done":    "✅ XONG RỒI",
        "overdue": "💀 QUÁ HẠN",
        "urgent":  "🔥 KHẨN CẤP",
        "warning": "⚠️ SẮP ĐẾN HẠN",
        "safe":    "😎 CÒN TH余裕",
        "unknown": "❓ KHÔNG RÕ",
    }

    for _, row in visible_tasks.iterrows():
        b_color = {
            "done": "#2e7d32", "overdue": "#d32f2f",
            "urgent": "#f57c00", "warning": "#fbc02d", "safe": "#1976d2"
        }.get(row["_status"], "#cccccc")
        assignee_name = get_user_name(row['Người_Phụ_Trách_ID'], users_df)
        status_label  = status_labels.get(row["_status"], row["_status"].upper())

        st.markdown(f"""
        <div style="border:1px solid {b_color}; border-left:5px solid {b_color}; background:#111112;
             border-radius:10px; padding:12px 16px; margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between;">
                <b>📌 {row['Tên_Công_Việc']}</b>
                <span style="color:{b_color}; font-weight:bold;">{status_label}</span>
            </div>
            <div style="font-size:13px; color:#aaa; margin-top:5px;">
                👤 Phụ trách: <b>{assignee_name}</b> | ⏰ Hạn: {row['Deadline']}
            </div>
            <div style="font-size:14px; color:{b_color}; font-weight:500; margin-top:3px;">
                {row['_remaining']} | Tiến độ: {row['Tiến_Độ_%']}%
            </div>
        </div>
        """, unsafe_allow_html=True)

        if row['Người_Phụ_Trách_ID'] == my_id:
            with st.expander("🛠 Cập nhật & Nộp Minh Chứng"):
                c1, c2 = st.columns(2)
                with c1:
                    np_ = st.slider("Tiến độ %", 0, 100, int(row["Tiến_Độ_%"]), key=f"sld_{row['ID']}")
                    if st.button("💾 Lưu Tiến Độ", key=f"btn_{row['ID']}"):
                        update_cell_by_id(WS_TASKS, "ID", row["ID"], "Tiến_Độ_%", np_, TASK_COLS)
                        if np_ == 100:
                            update_cell_by_id(WS_TASKS, "ID", row["ID"], "Trạng_Thái", "Đã xong", TASK_COLS)
                        st.success(msg_progress_saved(np_))
                        st.rerun()
                with c2:
                    st.markdown("**📤 Nộp minh chứng lên Discord**")
                    proof_file = st.file_uploader("Chọn file để gửi~", key=f"file_{row['ID']}")
                    if st.button("🚀 Nộp lên Discord", key=f"proof_btn_{row['ID']}"):
                        if proof_file:
                            assignee_groups = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False)]
                            sent_count = 0
                            for _, grp in assignee_groups.iterrows():
                                wh = str(grp.get("Discord_Webhook", "")).strip()
                                if wh:
                                    msg = discord_proof_sent(assignee_name, row['Tên_Công_Việc'])
                                    if push_to_discord(msg, webhook_url=wh,
                                                       file_bytes=proof_file.getvalue(),
                                                       filename=proof_file.name):
                                        sent_count += 1
                            if sent_count > 0:
                                st.success(msg_proof_sent())
                            else:
                                st.warning("😅 Gửi thất bại! Có vẻ nhóm của bạn chưa cài Discord Webhook — nhờ trưởng nhóm setup giúp nhé~")
                        else:
                            st.error("🙈 Ủa bạn chưa đính kèm file nào hết! Chọn file rồi mới nộp được nha~")

# ═══════════════════════════════════════════════════════════
#  8. TAB 2: KẾT BẠN & TẠO NHÓM
# ═══════════════════════════════════════════════════════════

def render_network(users_df, groups_df, my_id, my_friends_list):
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("🔍 Tìm & Kết Bạn")
        search_id = st.text_input("Nhập User ID của người bạn muốn kết bạn:").strip()
        if st.button("🤝 Kết bạn nào!"):
            if search_id == my_id:
                st.warning("🪞 Ủa bạn đang cố kết bạn với chính mình? Self-love là tốt nhưng không làm vậy được đâu nhé 😂")
            elif search_id in my_friends_list:
                st.info("👯 Người này đã là bạn bè của bạn rồi! Chơi thân hơn nữa đi~")
            else:
                target_user = users_df[users_df["User_ID"] == search_id]
                if target_user.empty:
                    st.error("🔍 Tìm mãi không thấy! Kiểm tra lại ID xem có nhập nhầm không nhé~")
                else:
                    new_friends = my_friends_list + [search_id]
                    update_cell_by_id(WS_USERS, "User_ID", my_id, "Bạn_Bè", ",".join(new_friends), USER_COLS)
                    st.success(msg_friend_added(target_user.iloc[0]['Tên']))
                    st.rerun()

        st.markdown("---")
        st.markdown("**👥 Danh sách bạn bè của bạn:**")
        if not my_friends_list:
            st.caption("🦗 Chưa có bạn nào... Đi kết bạn thêm đi! Deadline một mình buồn lắm~")
        for f_id in my_friends_list:
            st.markdown(f"- 👤 {get_user_name(f_id, users_df)} (`{f_id}`)")

    with c2:
        st.subheader("🏢 Tạo Nhóm Học Tập Mới")
        st.markdown("🎖️ Người tạo nhóm sẽ tự động trở thành Trưởng Nhóm — quyền lực đấy!")
        grp_name    = st.text_input("Đặt tên nhóm ngầu ngầu vào:")
        grp_webhook = st.text_input(
            "🤖 Discord Webhook URL của nhóm (tuỳ chọn):",
            placeholder="https://discord.com/api/webhooks/...",
            help="Bot sẽ gửi thông báo vào kênh Discord của nhóm này."
        ).strip()

        friend_options   = {f_id: f"{get_user_name(f_id, users_df)} ({f_id})" for f_id in my_friends_list}
        selected_friends = st.multiselect(
            "Chọn đồng đội cho nhóm:",
            options=list(friend_options.keys()),
            format_func=lambda x: friend_options[x]
        )

        if st.button("🚀 Thành lập nhóm!", type="primary"):
            if not grp_name:
                st.error("✏️ Đặt tên nhóm đi bạn ơi! Tên gì cũng được, miễn là ngầu~")
            elif not selected_friends:
                st.error("👀 Nhóm phải có ít nhất 1 người nữa ngoài bạn chứ! Mời bạn bè vào đi~")
            else:
                if groups_df.empty:
                    new_gid = "G001"
                else:
                    ids  = groups_df["Group_ID"].dropna().astype(str).tolist()
                    nums = [int(i[1:]) for i in ids if i.startswith("G") and i[1:].isdigit()]
                    new_gid = f"G{(max(nums) + 1 if nums else 1):03d}"

                all_members = [my_id] + selected_friends
                append_row_data(WS_GROUPS, [
                    new_gid, grp_name, my_id, ",".join(all_members),
                    grp_webhook, NOW().strftime("%Y-%m-%d")
                ])
                if grp_webhook:
                    push_to_discord(discord_group_created(grp_name), webhook_url=grp_webhook)
                st.success(msg_group_created(grp_name))
                st.rerun()

        st.markdown("---")
        st.markdown("**🏅 Các nhóm bạn đang tham gia:**")
        my_joined_groups = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False)]
        if my_joined_groups.empty:
            st.caption("🏜️ Chưa có nhóm nào... Tạo nhóm mới hoặc nhờ bạn bè thêm vào nhé!")
        for _, g in my_joined_groups.iterrows():
            role    = "👑 Trưởng nhóm" if g["Trưởng_Nhóm_ID"] == my_id else "👤 Thành viên"
            has_bot = "🤖 Bot ON" if str(g.get("Discord_Webhook", "")).strip() else "🔕 Bot OFF"
            st.markdown(f"- **{g['Tên_Nhóm']}** — {role} | {has_bot}")

    st.markdown("---")
    st.subheader("⚙️ Quản Lý Nhóm (Dành cho Trưởng Nhóm)")
    my_led_groups = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]

    if my_led_groups.empty:
        st.info("👀 Bạn chưa làm trưởng nhóm nào! Tạo nhóm đi rồi trải nghiệm cảm giác làm sếp nào~")
    else:
        edit_grp_id = st.selectbox(
            "Chọn nhóm để chỉnh sửa:",
            options=my_led_groups["Group_ID"].tolist(),
            format_func=lambda x: my_led_groups[my_led_groups["Group_ID"] == x]["Tên_Nhóm"].iloc[0]
        )
        grp_data = my_led_groups[my_led_groups["Group_ID"] == edit_grp_id].iloc[0]

        with st.expander(f"🛠 Chỉnh sửa nhóm: {grp_data['Tên_Nhóm']}", expanded=True):
            new_grp_name = st.text_input("Đổi tên nhóm:", value=grp_data["Tên_Nhóm"], key=f"name_{edit_grp_id}")
            new_webhook  = st.text_input("Đổi Discord Webhook:", value=grp_data.get("Discord_Webhook", ""), key=f"wh_{edit_grp_id}")

            current_members   = [m.strip() for m in str(grp_data["Thành_Viên_IDs"]).split(",") if m.strip() and m.strip() != my_id]
            valid_cur_members = [m for m in current_members if m in friend_options]
            new_members = st.multiselect(
                "Thêm/Bớt thành viên:",
                options=list(friend_options.keys()),
                default=valid_cur_members,
                format_func=lambda x: friend_options[x],
                key=f"mem_{edit_grp_id}"
            )

            col_save, col_del = st.columns(2)
            with col_save:
                if st.button("💾 Lưu thay đổi", type="primary", use_container_width=True):
                    final_members = [my_id] + new_members
                    update_cell_by_id(WS_GROUPS, "Group_ID", edit_grp_id, "Tên_Nhóm", new_grp_name, GROUP_COLS)
                    update_cell_by_id(WS_GROUPS, "Group_ID", edit_grp_id, "Thành_Viên_IDs", ",".join(final_members), GROUP_COLS)
                    update_cell_by_id(WS_GROUPS, "Group_ID", edit_grp_id, "Discord_Webhook", new_webhook, GROUP_COLS)
                    st.success(msg_group_updated())
                    st.rerun()
            with col_del:
                if st.button("💥 Giải tán nhóm", use_container_width=True):
                    delete_row_by_id(WS_GROUPS, "Group_ID", edit_grp_id, GROUP_COLS)
                    st.success(msg_group_deleted())
                    st.rerun()

# ═══════════════════════════════════════════════════════════
#  9. TAB 3: GIAO VIỆC
# ═══════════════════════════════════════════════════════════

def render_assign_task(users_df, groups_df, tasks_df, my_id, my_friends_list):
    st.subheader("📋 Giao Việc — Chỉ giao được cho Bạn Bè hoặc Bản thân")

    assignee_options = {my_id: f"🙋 Tự mình chiến ({get_user_name(my_id, users_df)})"}
    for f_id in my_friends_list:
        assignee_options[f_id] = f"👤 {get_user_name(f_id, users_df)} (Đồng đội)"

    with st.form("assign_form"):
        t_name      = st.text_input("Tên Nhiệm Vụ *")
        subj        = st.text_input("Thuộc môn học nào?")
        assignee_id = st.selectbox(
            "Ai sẽ gánh task này? *",
            options=list(assignee_options.keys()),
            format_func=lambda x: assignee_options[x]
        )
        col1, col2 = st.columns(2)
        with col1: d_date = st.date_input("Ngày chốt deadline", min_value=NOW().date())
        with col2: d_time = st.time_input("Giờ chốt")
        pri   = st.selectbox("Mức độ quan trọng", ["Cao", "Trung bình", "Thấp"])
        notes = st.text_area("Ghi chú thêm (nếu có)")

        if st.form_submit_button("⚡ Phát Lệnh!"):
            if not t_name:
                st.error("✏️ Đặt tên cho nhiệm vụ đi nào! Không có tên thì biết chiến cái gì~")
            else:
                new_id  = f"T{len(tasks_df)+1:03d}" if not tasks_df.empty else "T001"
                full_dl = f"{d_date} {d_time.strftime('%H:%M:%S')}"
                append_row_data(WS_TASKS, [
                    new_id, t_name, subj, assignee_id, full_dl, pri,
                    "Chưa xong", 0, "Bắt đầu", notes, 5, "",
                    NOW().strftime("%Y-%m-%d %H:%M:%S"), ""
                ])
                assignee_name = get_user_name(assignee_id, users_df)
                assignee_groups = groups_df[groups_df["Thành_Viên_IDs"].str.contains(assignee_id, na=False)]
                notified = set()
                for _, grp in assignee_groups.iterrows():
                    wh = str(grp.get("Discord_Webhook", "")).strip()
                    if wh and wh not in notified:
                        push_to_discord(
                            discord_task_assigned(t_name, assignee_name, full_dl, pri),
                            webhook_url=wh
                        )
                        notified.add(wh)
                st.success(msg_task_assigned(t_name, assignee_name))
                st.rerun()

# ═══════════════════════════════════════════════════════════
#  10. TAB 4: CHAT (NHÓM + CÁ NHÂN)
# ═══════════════════════════════════════════════════════════

def render_chat(chat_df, dm_df, groups_df, users_df, my_id, my_friends_list):
    st.subheader("💬 Chat")
    sub_group, sub_dm = st.tabs(["🏢 Chat Nhóm", "🔒 Tin Nhắn Riêng (DM)"])

    with sub_group:
        my_joined_groups = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False)]
        if my_joined_groups.empty:
            st.warning("🏜️ Bạn chưa có nhóm nào để chat! Qua tab 'Kết Bạn & Tạo Nhóm' lập nhóm đi nào~")
        else:
            group_options = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in my_joined_groups.iterrows()}
            selected_gid  = st.selectbox(
                "Chọn nhóm để chat:",
                options=list(group_options.keys()),
                format_func=lambda x: group_options[x],
                key="chat_grp_select"
            )

            st.markdown("---")
            chat_container = st.container(height=350)
            with chat_container:
                group_chats = chat_df[chat_df["Group_Nhận_ID"] == selected_gid]
                if group_chats.empty:
                    st.caption("🦗 Chưa có ai nhắn gì cả... Phá băng đi nào! Gửi tin nhắn đầu tiên đây~")
                for _, row in group_chats.iterrows():
                    sender_name = get_user_name(row["Người_Gửi_ID"], users_df)
                    is_me       = row["Người_Gửi_ID"] == my_id
                    css_class   = "chat-me" if is_me else "chat-card"
                    label_color = "#4CAF50" if is_me else "#5865F2"
                    st.markdown(f"""
                    <div class="{css_class}">
                        <small style='color:{label_color};'><b>{sender_name}</b> • {row['Thời_Gian']}</small><br>
                        <span>{row['Nội_Dung']}</span>
                    </div>""", unsafe_allow_html=True)

            with st.form("chat_grp_form", clear_on_submit=True):
                msg_grp    = st.text_input("Nhập tin nhắn vào đây...", key="grp_msg_input")
                upload_grp = st.file_uploader(
                    "📎 Đính kèm tài liệu (Gửi thẳng lên Discord nhóm)",
                    help="Discord Webhook hỗ trợ file tối đa 8MB–25MB.",
                    key="grp_file_input"
                )
                if st.form_submit_button("📨 Gửi vào Nhóm"):
                    if msg_grp.strip() or upload_grp:
                        sheet_msg = msg_grp.strip()
                        if upload_grp:
                            sheet_msg += f" [📎 {upload_grp.name}]"
                        if sheet_msg:
                            append_row_data(WS_CHAT, [
                                NOW().strftime("%Y-%m-%d %H:%M:%S"),
                                my_id, selected_gid, sheet_msg
                            ])
                        wh = get_group_webhook(selected_gid, groups_df)
                        if wh:
                            sender      = get_user_name(my_id, users_df)
                            group_label = group_options[selected_gid]
                            if msg_grp.strip():
                                d_msg = discord_group_chat(sender, group_label, msg_grp.strip())
                            else:
                                d_msg = f"📎 **{sender}** vừa thả tài liệu vào nhóm **{group_label}** — check ngay nào!"
                            if upload_grp:
                                push_to_discord(d_msg, webhook_url=wh,
                                                file_bytes=upload_grp.getvalue(), filename=upload_grp.name)
                            else:
                                push_to_discord(d_msg, webhook_url=wh)
                        st.rerun()
                    else:
                        st.warning("💭 Nhắn gì đi chứ! Hoặc đính kèm file cũng được~")

    with sub_dm:
        if not my_friends_list:
            st.warning("👀 Chưa có bạn bè nào để nhắn tin riêng! Kết bạn thêm đi rồi DM nhau nào~")
        else:
            friend_opts = {f_id: f"{get_user_name(f_id, users_df)} ({f_id})" for f_id in my_friends_list}
            selected_friend = st.selectbox(
                "Nhắn tin riêng với ai?",
                options=list(friend_opts.keys()),
                format_func=lambda x: friend_opts[x],
                key="dm_friend_select"
            )

            receiver_wh = get_user_dm_webhook(selected_friend, users_df)
            if receiver_wh:
                st.caption(f"🤖 Người này đã cài Discord Webhook — tin nhắn sẽ tự động ping họ trên Discord!")
            else:
                st.caption(f"🔕 Người này chưa cài Discord Webhook cá nhân — tin nhắn chỉ hiển thị trên web thôi nhé.")

            st.markdown("---")
            dm_container = st.container(height=350)
            with dm_container:
                convo = dm_df[
                    ((dm_df["Người_Gửi_ID"] == my_id)          & (dm_df["Người_Nhận_ID"] == selected_friend)) |
                    ((dm_df["Người_Gửi_ID"] == selected_friend) & (dm_df["Người_Nhận_ID"] == my_id))
                ].copy() if not dm_df.empty else pd.DataFrame(columns=DM_COLS)

                if convo.empty:
                    st.caption(f"🌸 Chưa có tin nhắn nào với {get_user_name(selected_friend, users_df)}. Bắt đầu cuộc trò chuyện đi nào~")
                for _, row in convo.iterrows():
                    sender_name = get_user_name(row["Người_Gửi_ID"], users_df)
                    is_me       = row["Người_Gửi_ID"] == my_id
                    css_class   = "chat-me" if is_me else "chat-private"
                    label_color = "#4CAF50" if is_me else "#7289DA"
                    st.markdown(f"""
                    <div class="{css_class}">
                        <small style='color:{label_color};'><b>{sender_name}</b> • {row['Thời_Gian']}</small><br>
                        <span>{row['Nội_Dung']}</span>
                    </div>""", unsafe_allow_html=True)

            with st.form("chat_dm_form", clear_on_submit=True):
                msg_dm    = st.text_input("Nhập tin nhắn bí mật...", key="dm_msg_input")
                upload_dm = st.file_uploader(
                    "📎 Đính kèm file (Gửi lên Discord cá nhân người nhận)",
                    help="Cần người nhận đã cài Discord Webhook DM.",
                    key="dm_file_input"
                )
                if st.form_submit_button("🔒 Gửi Tin Nhắn Riêng"):
                    if msg_dm.strip() or upload_dm:
                        sheet_msg = msg_dm.strip()
                        if upload_dm:
                            sheet_msg += f" [📎 {upload_dm.name}]"
                        if sheet_msg:
                            append_row_data(WS_DM, [
                                NOW().strftime("%Y-%m-%d %H:%M:%S"),
                                my_id, selected_friend, sheet_msg
                            ])
                        if receiver_wh:
                            sender_name = get_user_name(my_id, users_df)
                            if msg_dm.strip():
                                d_msg = discord_dm(sender_name, msg_dm.strip())
                            else:
                                d_msg = f"📎 **{sender_name}** vừa gửi cho bạn một tệp đính kèm đặc biệt~ Check ngay nhé!"
                            if upload_dm:
                                push_to_discord(d_msg, webhook_url=receiver_wh,
                                                file_bytes=upload_dm.getvalue(), filename=upload_dm.name)
                            else:
                                push_to_discord(d_msg, webhook_url=receiver_wh)
                        st.rerun()
                    else:
                        st.warning("💭 Nhắn gì đi! Gửi tin nhắn trống thì người ta không hiểu gì hết~")

# ═══════════════════════════════════════════════════════════
#  11. TAB 5: LEADERBOARD
# ═══════════════════════════════════════════════════════════

def render_leaderboard(tasks_df, users_df):
    st.subheader("🏆 Bảng Xếp Hạng — Ai là Deadline Slayer số 1?")
    if tasks_df.empty:
        st.info("🎲 Chưa có task nào để xếp hạng! Giao việc đi rồi xem ai cày task nhất nhé~")
        return

    tasks = tasks_df.copy()
    tasks["Tiến_Độ_%"] = tasks["Tiến_Độ_%"].apply(clean_and_parse_progress)
    tasks["_status"]   = tasks.apply(calculate_task_status, axis=1)

    grouped = tasks.groupby("Người_Phụ_Trách_ID").apply(lambda g: pd.Series({
        "Tổng Task": len(g),
        "Đã Xong":   (g["_status"] == "done").sum(),
        "Tiến độ TB": f"{int(g['Tiến_Độ_%'].mean())}%",
    })).reset_index()

    grouped["🏅 Chiến Binh"] = grouped["Người_Phụ_Trách_ID"].apply(lambda x: get_user_name(x, users_df))
    grouped = grouped[["🏅 Chiến Binh", "Tổng Task", "Đã Xong", "Tiến độ TB"]]
    grouped = grouped.sort_values(by="Đã Xong", ascending=False).reset_index(drop=True)
    grouped.index = grouped.index + 1  # bắt đầu từ 1

    # Thêm huy chương
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    grouped["🏅 Chiến Binh"] = grouped.apply(
        lambda r: f"{medals.get(r.name, '  ')} {r['🏅 Chiến Binh']}", axis=1
    )
    st.dataframe(grouped, use_container_width=True)

# ═══════════════════════════════════════════════════════════
#  12. TAB 6: QUẢN LÝ TÀI KHOẢN
# ═══════════════════════════════════════════════════════════

def render_account_management(users_df, my_id):
    st.subheader("🗑️ Quản Lý Tài Khoản")
    st.markdown("### 👥 Danh sách tất cả chiến binh trong hệ thống")
    if users_df.empty:
        st.info("👻 Không có ai cả! Hệ thống trống rỗng như sa mạc~")
        return

    display_cols = ["User_ID", "Tên", "Email", "Ngày_Tạo"]
    st.dataframe(users_df[display_cols], use_container_width=True)

    st.markdown("---")
    st.markdown("### 🗑️ Xóa Tài Khoản")
    st.warning("⚠️ Không thể xóa tài khoản đang đăng nhập. Muốn xóa chính mình thì... đừng nhé 😅")

    other_users = users_df[users_df["User_ID"] != my_id]
    if other_users.empty:
        st.info("😎 Chỉ có mình bạn thôi! Không có ai để xóa cả~")
        return

    user_opts = {
        row["User_ID"]: f"{row['Tên']} ({row['User_ID']}) — {row['Email']}"
        for _, row in other_users.iterrows()
    }
    del_id  = st.selectbox("Chọn tài khoản cần xóa:", options=list(user_opts.keys()), format_func=lambda x: user_opts[x])
    confirm = st.checkbox(f"✅ Tôi xác nhận muốn xóa `{del_id}` — không hối hận đâu nhé!")
    if st.button("💥 Xóa Tài Khoản", type="primary", disabled=not confirm):
        ok = delete_row_by_id(WS_USERS, "User_ID", del_id, USER_COLS)
        if ok:
            st.success(msg_account_deleted(del_id))
            fetch_all_data.clear()
            st.rerun()
        else:
            st.error("😵 Ủa xóa không được! Có thể tài khoản này đã tự biến mất rồi? Thử refresh lại nhé~")

# ═══════════════════════════════════════════════════════════
#  MAIN EXECUTION
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    data = fetch_all_data()
    if not st.session_state['logged_in']:
        show_auth_page(data)
    else:
        main_app(data)
