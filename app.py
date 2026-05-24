from datetime import datetime
import pandas as pd
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from zoneinfo import ZoneInfo
import json
import os
import random
import streamlit as st

if not os.path.exists("credentials.json"):
    if "gcp_service_account" in st.secrets:
        with open("credentials.json", "w") as f:
            json.dump(dict(st.secrets["gcp_service_account"]), f)

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
def NOW():
    return datetime.now(TZ)

st.set_page_config(page_title="Deadline Slayer ⚔️", page_icon="⚔️",
                   layout="wide", initial_sidebar_state="expanded")

for k, v in [("sheet_name","DeadlineSlayer_DB"),("logged_in",False),("current_user",None)]:
    if k not in st.session_state:
        st.session_state[k] = v

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif;}
[data-testid="metric-container"]{
    background:#16161a;border:1px solid rgba(255,255,255,0.08);
    border-radius:12px;padding:16px !important;box-shadow:0 4px 6px rgba(0,0,0,.2);}
.stButton>button[kind="primary"]{background:#5865F2;border:none;border-radius:8px;font-weight:700;color:white;}
.stButton>button[kind="primary"]:hover{background:#404EED;}
.chat-wrap{display:flex;flex-direction:column;gap:8px;padding:6px 2px;}
.msg-bubble{display:flex;align-items:flex-end;gap:8px;max-width:86%;}
.msg-avatar{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;
    justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;letter-spacing:.5px;}
.msg-body{display:flex;flex-direction:column;gap:2px;}
.msg-meta{font-size:11px;padding:0 6px;}
.msg-text{padding:9px 14px;border-radius:16px;font-size:14px;line-height:1.55;
    word-break:break-word;border:1px solid transparent;}
.msg-file{display:inline-flex;align-items:center;gap:8px;margin-top:5px;
    padding:7px 12px;border-radius:10px;font-size:13px;text-decoration:none;border:1px solid;}
.msg-file-icon{font-size:18px;flex-shrink:0;}
.msg-other{align-self:flex-start;}
.msg-other .msg-meta{color:#666;}
.msg-other .msg-text{background:#f0f1f3;color:#1a1a1a;border-color:#e0e2e5;border-radius:4px 16px 16px 16px;}
.msg-other .msg-avatar{background:#dde2ff;color:#3d47cc;}
.msg-other .msg-file{background:#e8eaed;color:#333;border-color:#d0d3d8;}
.msg-me{align-self:flex-end;flex-direction:row-reverse;}
.msg-me .msg-meta{color:#aaa;text-align:right;}
.msg-me .msg-text{background:#5865F2;color:#fff;border-color:#4752c4;border-radius:16px 4px 16px 16px;}
.msg-me .msg-avatar{background:#5865F2;color:#fff;}
.msg-me .msg-file{background:#4752c4;color:#fff;border-color:#3a41b0;}
.msg-dm{align-self:flex-start;}
.msg-dm .msg-meta{color:#666;}
.msg-dm .msg-text{background:#f0f4ff;color:#1a1a1a;border-color:#c5d0ff;border-radius:4px 16px 16px 16px;}
.msg-dm .msg-avatar{background:#c5d0ff;color:#2e3ab4;}
.msg-dm .msg-file{background:#e0e8ff;color:#2e3ab4;border-color:#b0c0ff;}
@media(prefers-color-scheme:dark){
    .msg-other .msg-text{background:#2b2d31;color:#e8e9eb;border-color:#3f4147;}
    .msg-other .msg-avatar{background:#3d4270;color:#9ba4f5;}
    .msg-other .msg-meta{color:#888;}
    .msg-other .msg-file{background:#2b2d31;color:#ccc;border-color:#444;}
    .msg-dm .msg-text{background:#1e2340;color:#e2e6ff;border-color:#3b4680;}
    .msg-dm .msg-avatar{background:#2a3370;color:#9ba8ff;}
    .msg-dm .msg-meta{color:#888;}
    .msg-dm .msg-file{background:#1e2340;color:#9ba8ff;border-color:#3b4680;}
    .msg-me .msg-meta{color:#aaa;}
}
.date-sep{text-align:center;font-size:11px;color:#aaa;margin:6px 0;
    display:flex;align-items:center;gap:8px;}
.date-sep::before,.date-sep::after{content:'';flex:1;height:1px;background:currentColor;opacity:.3;}
.chat-empty{text-align:center;padding:36px 20px;color:#999;font-size:14px;}
.chat-empty-icon{font-size:34px;margin-bottom:8px;}
.disc-badge{display:inline-flex;align-items:center;gap:5px;font-size:12px;
    padding:3px 10px;border-radius:20px;font-weight:600;margin-bottom:4px;}
.disc-on{background:#e8f5e9;color:#2e7d32;}
.disc-off{background:#f0f0f0;color:#888;}
@media(prefers-color-scheme:dark){
    .disc-on{background:#1b3a1d;color:#81c784;}
    .disc-off{background:#2a2a2a;color:#777;}
}
.friend-card{display:flex;align-items:center;justify-content:space-between;
    padding:10px 14px;border-radius:10px;margin-bottom:6px;
    background:#f5f6f8;border:1px solid #e4e6ea;}
@media(prefers-color-scheme:dark){.friend-card{background:#1e1f22;border-color:#2b2d31;}}
.friend-info{display:flex;align-items:center;gap:10px;}
.friend-avatar{width:36px;height:36px;border-radius:50%;background:#dde2ff;
    color:#3d47cc;display:flex;align-items:center;justify-content:center;
    font-size:13px;font-weight:700;}
@media(prefers-color-scheme:dark){.friend-avatar{background:#3d4270;color:#9ba4f5;}}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
#  1. SCHEMA
# ═══════════════════════════════════════════════════════════
SCOPES = ["https://spreadsheets.google.com/feeds",
          "https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

WS_TASKS="Tasks"; WS_USERS="Users"; WS_GROUPS="Groups"
WS_PROOFS="Proofs"; WS_CHAT="ChatRoom"; WS_DM="DirectMessages"

TASK_COLS  = ["ID","Tên_Công_Việc","Môn_Học","Người_Phụ_Trách_ID","Deadline",
              "Độ_Ưu_Tiên","Trạng_Thái","Tiến_Độ_%","Giai_Đoạn_Hiện_Tại",
              "Ghi_Chú","Nhắc_Mỗi_Phút","Nhắc_Lần_Cuối","Ngày_Tạo","Ngày_Cập_Nhật"]
USER_COLS  = ["User_ID","Password","Tên","Email","Bạn_Bè","Discord_Webhook_DM","Ngày_Tạo"]
GROUP_COLS = ["Group_ID","Tên_Nhóm","Trưởng_Nhóm_ID","Thành_Viên_IDs","Discord_Webhook","Ngày_Tạo"]
PROOF_COLS = ["Task_ID","Người_Nộp_ID","Thời_Gian","Mô_Tả","Giai_Đoạn","URL_File"]
CHAT_COLS  = ["Thời_Gian","Người_Gửi_ID","Group_Nhận_ID","Nội_Dung","Loại","File_Tên","File_URL"]
DM_COLS    = ["Thời_Gian","Người_Gửi_ID","Người_Nhận_ID","Nội_Dung","Loại","File_Tên","File_URL"]

COLUMN_ALIAS = {
    "Người_Phụ_Trác":       "Người_Phụ_Trách_ID",
    "Người_Phụ_Trách":      "Người_Phụ_Trách_ID",
    "Tên_Công_Viêc":        "Tên_Công_Việc",
    "Tiến_Độ":              "Tiến_Độ_%",
    "Tiến_Đô_%":            "Tiến_Độ_%",
    "Đô_Uu_Tiên":           "Độ_Ưu_Tiên",
    "Đô_Ưu_Tiên":           "Độ_Ưu_Tiên",
    "Trạng_Thai":           "Trạng_Thái",
    "Môn_Hoc":              "Môn_Học",
    "Người_Gửi":            "Người_Gửi_ID",
    "Người_Nhận":           "Người_Nhận_ID",
    "Group_Nhận":           "Group_Nhận_ID",
    "Nôi_Dung":             "Nội_Dung",
    "Bạn_Be":               "Bạn_Bè",
    "Ngay_Tạo":             "Ngày_Tạo",
    "Ngay_Cập_Nhật":        "Ngày_Cập_Nhật",
}

# ═══════════════════════════════════════════════════════════
#  2. MESSAGES
# ═══════════════════════════════════════════════════════════
def msg_login_success(name):
    return random.choice([
        f"⚔️ Chào chiến binh **{name}**! Deadline đang run rẩy trước sự hiện diện của bạn!",
        f"🔥 YO **{name}**! Sẵn sàng nghiền nát deadline chưa? Let's GOOO!",
        f"🛡️ **{name}** đã vào trận! Hôm nay chúng ta chinh phục deadline nào?",
        f"🎮 Player **{name}** đã online! Cả team đang chờ bạn flex não đây~",
    ])
def msg_login_fail():
    return random.choice([
        "🤔 Hmm... ID hay mật khẩu sai sai? Thử lại xem sao!",
        "🙈 Thông tin không khớp! Hay nhập nhầm pass game rồi? 😂",
        "❌ Không tìm thấy tài khoản! Kiểm tra lại ID và mật khẩu nhé~",
    ])
def msg_register_success(new_id):
    return random.choice([
        f"🎉 WELCOME! ID của bạn là **`{new_id}`** — nhớ kỹ nhé, mất là khóc đó!",
        f"🚀 Tài khoản **`{new_id}`** đã khai sinh! Chiến binh mới gia nhập chiến trường!",
    ])
def msg_task_assigned(task_name, assignee_name):
    return random.choice([
        f"🚀 Lệnh đã ban! **{assignee_name}** vừa nhận nhiệm vụ **{task_name}** — cố lên!",
        f"🎯 Đã bắn lệnh! **{task_name}** → **{assignee_name}**. Chúc may mắn!",
    ])
def msg_progress_saved(percent):
    if percent==100: return random.choice(["🏆 BOOM! 100%! Hạ gục deadline!","🎉 100%! Task về tay rồi!"])
    if percent>=75:  return random.choice([f"💪 {percent}%! Sắp về đích rồi!",f"🔥 {percent}%! Gần xong!"])
    if percent>=50:  return random.choice([f"🌗 {percent}%! Nửa đường rồi!",f"💡 {percent}%! Keep going!"])
    return random.choice([f"🌱 {percent}%! Bước đầu tiên luôn khó nhất!",f"🚀 {percent}%! Mỗi % là một chiến thắng!"])
def msg_friend_added(name):
    return random.choice([f"🤝 **{name}** đã vào danh sách bạn bè!",f"👯 YAY! **{name}** giờ là đồng đội rồi!"])
def msg_friend_removed(name):
    return random.choice([f"👋 Đã xóa **{name}** khỏi danh sách bạn bè.",f"💔 **{name}** đã rời danh sách bạn bè."])
def msg_group_created(n): return f"🏰 Nhóm **{n}** đã được thành lập! Dẫn dắt team đến vinh quang nhé!"
def msg_group_updated(): return "💾 Nhóm đã được nâng cấp! Thay đổi đã lưu thành công~"
def msg_group_deleted(): return "💥 Nhóm đã giải tán! Mỗi hành trình đều có hồi kết."
def msg_proof_sent(): return random.choice(["📤 Bằng chứng đã bay lên Discord!","✅ Đã nộp! Minh chứng đã chạm đến Discord nhóm."])
def msg_webhook_saved(): return "🤖 Discord Webhook đã được lưu!"
def msg_discord_broadcast(leader_name):
    return random.choice([f"📢 **[THÔNG BÁO TỪ {leader_name.upper()}]** 🔴\n",
                          f"🚨 **[{leader_name.upper()} CÓ LỆNH MỚI]** 📣\n"])

def discord_task_assigned(task_name, assignee_name, deadline, priority):
    e=random.choice(["🚨","⚡","🔥","💥","🎯"])
    prio={"Cao":"🔴 KHẨN CẤP","Trung bình":"🟡 Bình thường","Thấp":"🟢 Thư thả"}.get(priority,priority)
    return f"{e} **NHIỆM VỤ MỚI!** {e}\n📌 **{task_name}**\n👤 **{assignee_name}**\n⏰ `{deadline}`\n🏷️ {prio}\n💪 *Cả team tin bạn!*"
def discord_group_created(n): return f"🎊 **NHÓM MỚI: {n}**\n⚔️ *Không deadline nào là không thể!*\n🚀 Let's GO!!!"
def discord_proof_sent(name, task): return f"{random.choice(['✅','🎯','💪','🏆'])} **MINH CHỨNG NỘP!**\n👤 **{name}** → 📋 **{task}**\n👆 *Check file nhé trưởng nhóm!*"
def discord_dm(sender, content): return f"📩 **Tin nhắn riêng từ {sender}:**\n{content}\n*(Reply trên Deadline Slayer nhé!)*"
def discord_group_chat(sender, group, content): return f"💬 **{sender}** › [{group}]:\n{content}"

# ═══════════════════════════════════════════════════════════
#  3. GOOGLE SHEETS  — migrate + init
# ═══════════════════════════════════════════════════════════
@st.cache_resource(ttl=15)
def get_sheets_client():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPES)
        return gspread.authorize(creds)
    except: return None

def migrate_sheet(ws, expected_cols):
    try:
        current = ws.row_values(1)
        if not current:
            ws.append_row(expected_cols)
            return
        updated = [COLUMN_ALIAS.get(c, c) for c in current]
        missing = [c for c in expected_cols if c not in updated]
        if missing:
            updated += missing
        if updated != current:
            ws.update("1:1", [updated])
    except Exception:
        pass

def init_spreadsheet_structure(ss):
    existing = {ws.title: ws for ws in ss.worksheets()}
    schema = {
        WS_TASKS:  TASK_COLS,
        WS_USERS:  USER_COLS,
        WS_GROUPS: GROUP_COLS,
        WS_PROOFS: PROOF_COLS,
        WS_CHAT:   CHAT_COLS,
        WS_DM:     DM_COLS,
    }
    for name, cols in schema.items():
        if name not in existing:
            ws = ss.add_worksheet(title=name, rows=1000, cols=max(len(cols), 10))
            ws.append_row(cols)
        else:
            migrate_sheet(existing[name], cols)

@st.cache_data(ttl=1)
def fetch_all_data():
    client = get_sheets_client()
    empty = {
        "tasks":  pd.DataFrame(columns=TASK_COLS),
        "users":  pd.DataFrame(columns=USER_COLS),
        "groups": pd.DataFrame(columns=GROUP_COLS),
        "proofs": pd.DataFrame(columns=PROOF_COLS),
        "chat":   pd.DataFrame(columns=CHAT_COLS),
        "dm":     pd.DataFrame(columns=DM_COLS),
    }
    if not client: return empty
    try:
        ss = client.open(st.session_state["sheet_name"])
        init_spreadsheet_structure(ss)

        def get_df(name, cols):
            vals = ss.worksheet(name).get_all_values()
            if not vals or len(vals) <= 1:
                return pd.DataFrame(columns=cols)
            header = [COLUMN_ALIAS.get(h, h) for h in vals[0]]
            rows   = vals[1:]
            n = len(header)
            rows = [r[:n] + [""] * max(0, n - len(r)) for r in rows]
            df = pd.DataFrame(rows, columns=header)
            df = df.loc[:, ~df.columns.duplicated()]
            if "" in df.columns: df = df.drop(columns=[""])
            for col in cols:
                if col not in df.columns:
                    df[col] = ""
            return df.reindex(columns=cols).fillna("")

        return {k: get_df(n, c) for k, n, c in [
            ("tasks",  WS_TASKS,  TASK_COLS),
            ("users",  WS_USERS,  USER_COLS),
            ("groups", WS_GROUPS, GROUP_COLS),
            ("proofs", WS_PROOFS, PROOF_COLS),
            ("chat",   WS_CHAT,   CHAT_COLS),
            ("dm",     WS_DM,     DM_COLS),
        ]}
    except:
        return empty

def get_ws(name):
    c = get_sheets_client()
    if not c: return None
    try: return c.open(st.session_state["sheet_name"]).worksheet(name)
    except: return None

def append_row_data(name, row):
    import time
    ws = get_ws(name)
    if not ws:
        st.error(f"❌ Không kết nối được sheet '{name}'! Kiểm tra credentials.")
        return False
    try:
        schema_len = {
            WS_TASKS: len(TASK_COLS), WS_USERS: len(USER_COLS),
            WS_GROUPS: len(GROUP_COLS), WS_PROOFS: len(PROOF_COLS),
            WS_CHAT: len(CHAT_COLS), WS_DM: len(DM_COLS),
        }
        expected = schema_len.get(name, len(row))
        row = list(row) + [""] * max(0, expected - len(row))
        row = row[:expected]
        ws.append_row(row, value_input_option="USER_ENTERED")
        time.sleep(0.5)
        fetch_all_data.clear()
        return True
    except Exception as e:
        st.error(f"❌ Lỗi lưu dữ liệu vào '{name}': {e}")
        return False

def update_cell_by_id(ws_name, id_col, item_id, upd_col, new_val, schema):
    ws = get_ws(ws_name)
    if not ws: return
    try:
        actual_header = ws.row_values(1)
        actual_header = [COLUMN_ALIAS.get(h, h) for h in actual_header]
        if id_col not in actual_header:
            st.error(f"💀 Không tìm thấy cột '{id_col}' trong sheet '{ws_name}'.")
            return
        id_col_idx  = actual_header.index(id_col) + 1
        upd_col_idx = actual_header.index(upd_col) + 1 if upd_col in actual_header else schema.index(upd_col) + 1
        cell = ws.find(str(item_id))
        if cell and cell.col == id_col_idx:
            ws.update_cell(cell.row, upd_col_idx, new_val)
            fetch_all_data.clear()
    except Exception as e:
        st.error(f"💀 Lỗi đồng bộ: {e}")

def delete_row_by_id(ws_name, id_col, item_id, schema):
    ws = get_ws(ws_name)
    if not ws: return False
    try:
        cell = ws.find(str(item_id))
        if cell and cell.col == schema.index(id_col) + 1:
            ws.delete_rows(cell.row)
            fetch_all_data.clear()
            return True
        return False
    except Exception as e:
        st.error(f"💀 Xóa thất bại: {e}")
        return False

# ═══════════════════════════════════════════════════════════
#  4. DISCORD & HELPERS
# ═══════════════════════════════════════════════════════════
def push_to_discord(message, webhook_url="", file_bytes=None, filename=None):
    if not webhook_url or "discord.com/api/webhooks" not in webhook_url: return False
    try:
        if file_bytes and filename:
            r = requests.post(webhook_url, data={"content": message},
                              files={"file": (filename, file_bytes)}, timeout=15)
        else:
            r = requests.post(webhook_url, json={"content": message}, timeout=5)
        return r.status_code in (200, 204)
    except Exception as e:
        st.warning(f"🤖 Bot lỗi: {e}")
        return False

def get_group_webhook(gid, groups_df):
    m = groups_df[groups_df["Group_ID"] == gid]
    return str(m.iloc[0].get("Discord_Webhook", "")).strip() if not m.empty else ""

def get_user_dm_webhook(uid, users_df):
    m = users_df[users_df["User_ID"] == uid]
    return str(m.iloc[0].get("Discord_Webhook_DM", "")).strip() if not m.empty else ""

def clean_progress(val):
    if pd.isna(val) or val == "": return 0.0
    try: return float(str(val).replace("%", "").strip())
    except: return 0.0

def parse_dl(dl_str):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M"):
        try: return datetime.strptime(str(dl_str).strip(), fmt).replace(tzinfo=TZ)
        except: continue
    return None

def calc_status(row):
    if str(row.get("Trạng_Thái", "")) == "Đã xong" or clean_progress(row.get("Tiến_Độ_%")) == 100:
        return "done"
    dl = parse_dl(row.get("Deadline", ""))
    if dl is None: return "unknown"
    h = (dl - NOW()).total_seconds() / 3600
    if h < 0:   return "overdue"
    if h <= 24: return "urgent"
    if h <= 72: return "warning"
    return "safe"

def fmt_remaining(row):
    if str(row.get("Trạng_Thái", "")) == "Đã xong": return "Xong sạch rồi 🎉"
    dl = parse_dl(row.get("Deadline", ""))
    if dl is None: return "—"
    s = int((dl - NOW()).total_seconds())
    if s < 0: return "ĐÃ QUÁ HẠN! 🛑"
    d, r = divmod(s, 86400); h, r = divmod(r, 3600); m, _ = divmod(r, 60)
    if d > 3:  return f"⏳ Còn {d}n {h}g"
    if d > 0:  return f"⚡ Còn {d}n {h}g {m}p"
    if h > 3:  return f"🔥 Còn {h}g {m}p"
    if h > 0:  return f"🚨 Còn {h}g {m}p — KHẨN!"
    return f"💀 Còn {m}p!!! FULL SEND!!!"

def get_user_name(uid, users_df):
    m = users_df[users_df["User_ID"] == uid]
    return m.iloc[0]["Tên"] if not m.empty else f"Ẩn danh ({uid})"

def get_initials(name):
    p = name.strip().split()
    if len(p) >= 2: return (p[0][0] + p[-1][0]).upper()
    return name[:2].upper() if len(name) >= 2 else name.upper()

def file_icon(fname):
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    return {"pdf":"📄","doc":"📝","docx":"📝","xls":"📊","xlsx":"📊",
            "ppt":"📋","pptx":"📋","zip":"🗜","rar":"🗜",
            "png":"🖼","jpg":"🖼","jpeg":"🖼","gif":"🖼","mp4":"🎬",
            "mp3":"🎵","wav":"🎵"}.get(ext, "📎")

def render_bubble(sender_name, content, time_str, is_me, variant="group",
                  file_name="", file_url="", msg_type="text"):
    initials = get_initials(sender_name)
    cls  = "msg-me" if is_me else ("msg-dm" if variant == "dm" else "msg-other")
    meta = time_str if is_me else f"{sender_name} · {time_str}"
    body = ""
    if msg_type in ("text", "both") and str(content).strip():
        body += f'<div class="msg-text">{content}</div>'
    if msg_type in ("file", "both") and file_name:
        icon = file_icon(file_name)
        if file_url and file_url.startswith("http"):
            body += (f'<a class="msg-file" href="{file_url}" target="_blank" rel="noopener">'
                     f'<span class="msg-file-icon">{icon}</span>{file_name}'
                     f' <small style="opacity:.7;">↗ Mở</small></a>')
        else:
            body += (f'<div class="msg-file"><span class="msg-file-icon">{icon}</span>'
                     f'<span>{file_name}</span>'
                     f'<small style="opacity:.6;margin-left:4px;">(chưa có link)</small></div>')
    return f"""
<div class="msg-bubble {cls}">
  <div class="msg-avatar">{initials}</div>
  <div class="msg-body">
    <div class="msg-meta">{meta}</div>
    {body}
  </div>
</div>"""

def render_messages_html(rows_iter, my_id, users_df, variant="group"):
    html = '<div class="chat-wrap">'
    prev_date = None
    for _, row in rows_iter:
        sender   = get_user_name(row["Người_Gửi_ID"], users_df)
        is_me    = row["Người_Gửi_ID"] == my_id
        ts       = str(row["Thời_Gian"])
        cur_date = ts[:10] if len(ts) >= 10 else ts
        if cur_date != prev_date:
            html += f'<div class="date-sep">{cur_date}</div>'
            prev_date = cur_date
        short    = ts[11:16] if len(ts) >= 16 else ts
        msg_type = str(row.get("Loại", "text")) or "text"
        html += render_bubble(sender, str(row["Nội_Dung"]), short, is_me, variant,
                              str(row.get("File_Tên", "")), str(row.get("File_URL", "")), msg_type)
    html += '</div>'
    return html

# ═══════════════════════════════════════════════════════════
#  5. AUTH
# ═══════════════════════════════════════════════════════════
def show_auth_page(data):
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align:center'>🛡️ DEADLINE SLAYER</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#888'>Nền tảng quản lý học tập & Giao việc nhóm</p>",
                    unsafe_allow_html=True)
        t1, t2 = st.tabs(["🔑 Đăng Nhập", "📝 Đăng Ký"])
        with t1:
            log_id   = st.text_input("User ID (VD: U001)", key="log_id").strip()
            log_pass = st.text_input("Mật khẩu", type="password", key="log_pass")
            if st.button("🚀 Đăng Nhập", use_container_width=True, type="primary"):
                fetch_all_data.clear()
                fu = fetch_all_data()["users"]
                if fu.empty:
                    st.error("👻 Chưa có ai! Đăng ký tài khoản đầu tiên đi!")
                else:
                    m = fu[(fu["User_ID"] == log_id) & (fu["Password"] == log_pass)]
                    if not m.empty:
                        st.session_state.update({"logged_in": True,
                                                 "current_user": m.iloc[0].to_dict()})
                        st.success(msg_login_success(m.iloc[0]["Tên"]))
                        st.rerun()
                    else:
                        st.error(msg_login_fail())
        with t2:
            rn = st.text_input("Họ và Tên", key="rn").strip()
            re = st.text_input("Email", key="re").strip()
            rp = st.text_input("Mật khẩu", type="password", key="rp")
            rw = st.text_input("🤖 Discord Webhook cá nhân (tuỳ chọn)",
                               placeholder="https://discord.com/api/webhooks/...", key="rw").strip()
            if st.button("✨ Tạo Tài Khoản", use_container_width=True):
                if not rn or not re or not rp:
                    st.error("🙏 Điền đủ thông tin nhé!")
                else:
                    fetch_all_data.clear()
                    fu = fetch_all_data()["users"]
                    if not fu.empty and re in fu["Email"].values:
                        st.error("📧 Email đã tồn tại!")
                    else:
                        nums = [int(i[1:]) for i in fu["User_ID"].dropna().astype(str).tolist()
                                if i.startswith("U") and i[1:].isdigit()] if not fu.empty else []
                        new_id = f"U{(max(nums) + 1 if nums else 1):03d}"
                        append_row_data(WS_USERS,
                                        [new_id, rp, rn, re, "", rw,
                                         NOW().strftime("%Y-%m-%d %H:%M:%S")])
                        fetch_all_data.clear()
                        st.success(msg_register_success(new_id))

# ═══════════════════════════════════════════════════════════
#  6. MAIN APP
# ═══════════════════════════════════════════════════════════
def main_app(data):
    users_df  = data["users"]
    groups_df = data["groups"]
    tasks_df  = data["tasks"]
    cu        = st.session_state["current_user"]
    my_id     = cu["User_ID"]

    fresh_user = users_df[users_df["User_ID"] == my_id]
    if fresh_user.empty:
        st.warning("⚠️ Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.")
        st.session_state.update({"logged_in": False, "current_user": None})
        st.rerun()
        return
    cu = fresh_user.iloc[0].to_dict()
    st.session_state["current_user"] = cu
    me = fresh_user.iloc[0]
    my_friends = [f.strip() for f in str(me["Bạn_Bè"]).split(",") if f.strip()]
    is_leader  = not groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id].empty

    with st.sidebar:
        st.markdown("## ⚔️ DEADLINE SLAYER")
        st.markdown("---")
        st.success(f"👤 **{cu['Tên']}**\n\n🆔 ID: `{my_id}`")
        if st.button("🚪 Đăng xuất", use_container_width=True, key="sidebar_logout"):
            st.session_state.update({"logged_in": False, "current_user": None})
            st.rerun()
        st.markdown("---")
        st.subheader("⚙️ Cấu hình")
        sn = st.text_input("Tên Google Sheets", value=st.session_state["sheet_name"])
        if sn != st.session_state["sheet_name"]:
            st.session_state["sheet_name"] = sn
            fetch_all_data.clear()
            st.rerun()
        st.markdown("---")
        st.markdown("### 🔔 Webhook Cá Nhân")
        cur_wh = str(me.get("Discord_Webhook_DM", "")).strip()
        new_wh = st.text_input("Webhook nhận DM:", value=cur_wh,
                               placeholder="https://discord.com/api/webhooks/...",
                               key="sidebar_wh").strip()
        if st.button("💾 Lưu Webhook", use_container_width=True, key="sidebar_save_wh"):
            update_cell_by_id(WS_USERS, "User_ID", my_id, "Discord_Webhook_DM", new_wh, USER_COLS)
            fetch_all_data.clear()
            st.toast(msg_webhook_saved())
        if is_leader:
            st.markdown("---")
            st.markdown("### 🤖 Bot Nhóm")
            mg = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
            go = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in mg.iterrows()}
            sg = st.selectbox("Chọn nhóm:", list(go.keys()), format_func=lambda x: go[x])
            mt = st.text_area("Nội dung thông báo:")
            af = st.file_uploader("📎 Đính kèm file")
            if st.button("🚀 Bắn Lên Discord", use_container_width=True, type="primary", key="sidebar_discord_blast"):
                wh  = get_group_webhook(sg, groups_df)
                msg = msg_discord_broadcast(cu["Tên"]) + mt
                ok  = push_to_discord(msg, wh, af.getvalue(), af.name) if af else push_to_discord(msg, wh)
                st.toast("🚀 Đã bắn!" if ok else "😥 Thất bại!")
        st.markdown("---")
        if st.button("🔄 Làm mới", use_container_width=True, key="sidebar_refresh"):
            fetch_all_data.clear()
            st.rerun()

    t1, t2, t3, t4, t5, t6 = st.tabs([
        "📊 Dashboard", "👥 Nhóm & Giao Việc", "💬 Chat",
        "👫 Quản Lý Bạn Bè", "🏆 Xếp Hạng", "🗑️ Tài Khoản"])

    with t1: render_dashboard(tasks_df, groups_df, users_df, my_id, is_leader)
    with t2: render_network_and_tasks(users_df, groups_df, tasks_df, my_id, my_friends)
    with t3: render_chat(data["chat"], data["dm"], groups_df, users_df, my_id, my_friends)
    with t4: render_friends_management(users_df, my_id, my_friends)
    with t5: render_leaderboard(tasks_df, users_df)
    with t6: render_account_tab(users_df, my_id)

# ═══════════════════════════════════════════════════════════
#  7. DASHBOARD
# ═══════════════════════════════════════════════════════════
def render_dashboard(tasks_df, groups_df, users_df, my_id, is_leader):
    st.subheader("📊 Bảng Tiến Độ")
    my_groups = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
    subs = []
    for _, g in my_groups.iterrows():
        subs.extend([m.strip() for m in str(g["Thành_Viên_IDs"]).split(",") if m.strip()])
    vt = tasks_df[
        (tasks_df["Người_Phụ_Trách_ID"] == my_id) |
        (tasks_df["Người_Phụ_Trách_ID"].isin(subs))
    ].copy()
    if vt.empty:
        st.info("🎉 Chưa có nhiệm vụ nào — tận hưởng khoảnh khắc này đi!")
        return
    vt["Tiến_Độ_%"] = vt["Tiến_Độ_%"].apply(clean_progress)
    vt["_st"]  = vt.apply(calc_status,   axis=1)
    vt["_rem"] = vt.apply(fmt_remaining, axis=1)
    slabels = {"done":"✅ XONG","overdue":"💀 QUÁ HẠN","urgent":"🔥 KHẨN",
               "warning":"⚠️ SẮP ĐẾN","safe":"😎 CÒN THỜI GIAN","unknown":"❓"}
    for idx, row in vt.iterrows():
        bc = {"done":"#2e7d32","overdue":"#d32f2f","urgent":"#f57c00",
              "warning":"#fbc02d","safe":"#1976d2"}.get(row["_st"], "#ccc")
        an = get_user_name(row["Người_Phụ_Trách_ID"], users_df)
        st.markdown(f"""<div style="border:1px solid {bc};border-left:5px solid {bc};
            background:#111112;border-radius:10px;padding:12px 16px;margin-bottom:8px;">
            <div style="display:flex;justify-content:space-between;">
                <b>📌 {row['Tên_Công_Việc']}</b>
                <span style="color:{bc};font-weight:bold;">{slabels.get(row['_st'],'')}</span>
            </div>
            <div style="font-size:13px;color:#aaa;margin-top:5px;">
                👤 <b>{an}</b> | ⏰ {row['Deadline']}
            </div>
            <div style="font-size:14px;color:{bc};font-weight:500;margin-top:3px;">
                {row['_rem']} | {row['Tiến_Độ_%']}%
            </div>
        </div>""", unsafe_allow_html=True)
        if row["Người_Phụ_Trách_ID"] == my_id:
            with st.expander(f"🛠 Cập nhật & Nộp Minh Chứng — {row['Tên_Công_Việc']}"):
                c1, c2 = st.columns(2)
                with c1:
                    np_ = st.slider("Tiến độ %", 0, 100, int(row["Tiến_Độ_%"]),
                                    key=f"sld_{row['ID']}")
                    if st.button("💾 Lưu", key=f"btn_{row['ID']}"):
                        update_cell_by_id(WS_TASKS, "ID", row["ID"], "Tiến_Độ_%", np_, TASK_COLS)
                        if np_ == 100:
                            update_cell_by_id(WS_TASKS, "ID", row["ID"], "Trạng_Thái", "Đã xong", TASK_COLS)
                        st.success(msg_progress_saved(np_))
                        st.rerun()
                with c2:
                    st.markdown("**📤 Nộp minh chứng lên Discord**")
                    pf = st.file_uploader("Chọn file~", key=f"file_{row['ID']}")
                    if st.button("🚀 Nộp lên Discord", key=f"pb_{row['ID']}"):
                        if pf:
                            ag  = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False)]
                            cnt = sum(1 for _, g in ag.iterrows()
                                      if push_to_discord(
                                          discord_proof_sent(an, row["Tên_Công_Việc"]),
                                          str(g.get("Discord_Webhook", "")).strip(),
                                          pf.getvalue(), pf.name))
                            st.success(msg_proof_sent()) if cnt > 0 else st.warning("😅 Nhóm chưa cài Webhook!")
                        else:
                            st.error("🙈 Chọn file trước đã!")

# ═══════════════════════════════════════════════════════════
#  8. NHÓM & GIAO VIỆC
# ═══════════════════════════════════════════════════════════
def render_network_and_tasks(users_df, groups_df, tasks_df, my_id, my_friends):
    sub1, sub2 = st.tabs(["🏢 Tạo & Quản Lý Nhóm", "📋 Giao Việc Mới"])

    with sub1:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🏢 Tạo Nhóm Mới")
            grp_name = st.text_input("Tên nhóm:", key="new_grp_name")
            grp_wh   = st.text_input("🤖 Discord Webhook (tuỳ chọn):",
                                     placeholder="https://discord.com/api/webhooks/...",
                                     key="new_grp_wh").strip()
            fo = {f: f"{get_user_name(f, users_df)} ({f})" for f in my_friends}
            sel_f = st.multiselect("Chọn đồng đội:", list(fo.keys()),
                                   format_func=lambda x: fo[x], key="new_grp_members")
            if st.button("🏰 Tạo Nhóm", use_container_width=True, key="btn_create_grp"):
                if not grp_name:
                    st.error("🙏 Vui lòng nhập tên nhóm!")
                else:
                    fetch_all_data.clear()
                    fg = fetch_all_data()["groups"]
                    nums = [int(i[1:]) for i in fg["Group_ID"].dropna().astype(str).tolist()
                            if i.startswith("G") and i[1:].isdigit()] if not fg.empty else []
                    new_gid = f"G{(max(nums) + 1 if nums else 1):03d}"
                    m_ids = ",".join([my_id] + sel_f)
                    if append_row_data(WS_GROUPS, [new_gid, grp_name, my_id, m_ids, grp_wh, NOW().strftime("%Y-%m-%d %H:%M:%S")]):
                        if grp_wh:
                            push_to_discord(discord_group_created(grp_name), grp_wh)
                        st.success(msg_group_created(grp_name))
                        st.rerun()
        with c2:
            st.subheader("🏰 Nhóm Bạn Đang Quản Lý")
            my_own_grps = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
            if my_own_grps.empty:
                st.info("🌱 Bạn chưa làm trưởng nhóm nào.")
            else:
                for _, g in my_own_grps.iterrows():
                    with st.expander(f"⚙️ {g['Tên_Nhóm']} ({g['Group_ID']})"):
                        u_wh = st.text_input("Sửa Webhook:", value=str(g["Discord_Webhook"]), key=f"wh_{g['Group_ID']}").strip()
                        if st.button("💾 Cập nhật", key=f"upd_{g['Group_ID']}"):
                            update_cell_by_id(WS_GROUPS, "Group_ID", g["Group_ID"], "Discord_Webhook", u_wh, GROUP_COLS)
                            st.success(msg_group_updated())
                            st.rerun()
                        if st.button("💥 Giải tán nhóm", key=f"del_{g['Group_ID']}"):
                            if delete_row_by_id(WS_GROUPS, "Group_ID", g["Group_ID"], GROUP_COLS):
                                st.success(msg_group_deleted())
                                st.rerun()

    with sub2:
        st.subheader("📋 Giao Nhiệm Vụ Mới")
        all_candidates = set(my_friends + [my_id])
        my_grps = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
        for _, g in my_grps.iterrows():
            for m in str(g["Thành_Viên_IDs"]).split(","):
                if m.strip(): all_candidates.add(m.strip())
        
        cand_opts = {c: f"{get_user_name(c, users_df)} ({c})" for c in all_candidates}
        
        cc1, cc2 = st.columns(2)
        with cc1:
            t_name = st.text_input("Tên công việc:")
            t_sub  = st.text_input("Môn học / Dự án:")
            t_assignee = st.selectbox("Người phụ trách:", list(cand_opts.keys()), format_func=lambda x: cand_opts[x])
        with cc2:
            t_dl_date = st.date_input("Ngày hạn chót:")
            t_dl_time = st.time_input("Giờ hạn chót:", value=datetime.strptime("23:59", "%H:%M").time())
            t_prio = st.selectbox("Độ ưu tiên:", ["Thấp", "Trung bình", "Cao"], index=1)
        t_note = st.text_area("Ghi chú công việc:")
        
        if st.button("⚔️ Phát Lệnh Giao Việc", type="primary", use_container_width=True):
            if not t_name:
                st.error("🙏 Vui lòng nhập tên công việc!")
            else:
                fetch_all_data.clear()
                ft = fetch_all_data()["tasks"]
                nums = [int(i[1:]) for i in ft["ID"].dropna().astype(str).tolist()
                        if i.startswith("T") and i[1:].isdigit()] if not ft.empty else []
                new_tid = f"T{(max(nums) + 1 if nums else 1):03d}"
                dl_combined = datetime.combine(t_dl_date, t_dl_time).strftime("%Y-%m-%d %H:%M:%S")
                
                row = [new_tid, t_name, t_sub, t_assignee, dl_combined, t_prio, "Chưa làm", "0", "", t_note, "Không", "", NOW().strftime("%Y-%m-%d %H:%M:%S"), NOW().strftime("%Y-%m-%d %H:%M:%S")]
                if append_row_data(WS_TASKS, row):
                    assignee_name = get_user_name(t_assignee, users_df)
                    st.success(msg_task_assigned(t_name, assignee_name))
                    wh = get_user_dm_webhook(t_assignee, users_df)
                    if wh:
                        push_to_discord(discord_task_assigned(t_name, assignee_name, dl_combined, t_prio), wh)
                    st.rerun()

# ═══════════════════════════════════════════════════════════
#  9. CHAT
# ═══════════════════════════════════════════════════════════
def render_chat(chat_df, dm_df, groups_df, users_df, my_id, my_friends):
    ch_tab, dm_tab = st.tabs(["💬 Phòng Chat Nhóm", "📩 Tin Nhắn Riêng (DM)"])
    
    with ch_tab:
        in_grps = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False) | (groups_df["Trưởng_Nhóm_ID"] == my_id)]
        if in_grps.empty:
            st.info("🏰 Bạn chưa tham gia nhóm nào để chat.")
        else:
            g_opts = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in in_grps.iterrows()}
            sel_gid = st.selectbox("Chọn phòng chat nhóm:", list(g_opts.keys()), format_func=lambda x: g_opts[x], key="chat_sel_gid")
            g_msgs = chat_df[chat_df["Group_Nhận_ID"] == sel_gid].sort_values("Thời_Gian")
            
            st.markdown("---")
            if g_msgs.empty:
                st.markdown('<div class="chat-empty"><div class="chat-empty-icon">💬</div>Chưa có tin nhắn nào. Gõ gì đó bên dưới để phá băng!</div>', unsafe_allow_html=True)
            else:
                st.markdown(render_messages_html(g_msgs.iterrows(), my_id, users_df, variant="group"), unsafe_allow_html=True)
            
            st.markdown("---")
            with st.form("grp_msg_form", clear_on_submit=True):
                c1, c2 = st.columns([4, 1])
                txt = c1.text_input("Nhập tin nhắn...", placeholder="Gõ gì đó vui vẻ nào~")
                f_up = c2.file_uploader("Đính kèm", label_visibility="collapsed")
                submit = st.form_submit_button("Gửi 🚀", use_container_width=True)
                if submit:
                    if txt.strip() or f_up:
                        f_name = f_up.name if f_up else ""
                        m_type = "both" if (txt.strip() and f_up) else ("file" if f_up else "text")
                        ts_now = NOW().strftime("%Y-%m-%d %H:%M:%S")
                        append_row_data(WS_CHAT, [ts_now, my_id, sel_gid, txt.strip(), m_type, f_name, ""])
                        g_wh = get_group_webhook(sel_gid, groups_df)
                        if g_wh:
                            me_name = get_user_name(my_id, users_df)
                            disc_msg = discord_group_chat(me_name, g_opts[sel_gid], txt.strip() if txt.strip() else f"📎 Đã gửi file: {f_name}")
                            if f_up:
                                push_to_discord(disc_msg, g_wh, f_up.getvalue(), f_up.name)
                            else:
                                push_to_discord(disc_msg, g_wh)
                        st.rerun()
    
    with dm_tab:
        if not my_friends:
            st.info("👫 Tìm thêm bạn bè ở tab 'Quản Lý Bạn Bè' để bắt đầu trò chuyện riêng tư nhé!")
        else:
            f_opts = {f: f"{get_user_name(f, users_df)} ({f})" for f in my_friends}
            sel_fid = st.selectbox("Chọn bạn bè:", list(f_opts.keys()), format_func=lambda x: f_opts[x], key="chat_sel_fid")
            d_msgs = dm_df[
                ((dm_df["Người_Gửi_ID"] == my_id) & (dm_df["Người_Nhận_ID"] == sel_fid)) |
                ((dm_df["Người_Gửi_ID"] == sel_fid) & (dm_df["Người_Nhận_ID"] == my_id))
            ].sort_values("Thời_Gian")
            
            st.markdown("---")
            if d_msgs.empty:
                st.markdown('<div class="chat-empty"><div class="chat-empty-icon">📩</div>Chưa có hội thoại. Gửi lời chào mật ngọt thôi!</div>', unsafe_allow_html=True)
            else:
                st.markdown(render_messages_html(d_msgs.iterrows(), my_id, users_df, variant="dm"), unsafe_allow_html=True)
            
            st.markdown("---")
            with st.form("dm_msg_form", clear_on_submit=True):
                c1, c2 = st.columns([4, 1])
                txt = c1.text_input("Nhập tin nhắn mật...", placeholder="Thì thầm mùa xuân với đồng đội...")
                f_up = c2.file_uploader("Đính kèm", key="dm_file", label_visibility="collapsed")
                submit = st.form_submit_button("Gửi 🤫", use_container_width=True)
                if submit:
                    if txt.strip() or f_up:
                        f_name = f_up.name if f_up else ""
                        m_type = "both" if (txt.strip() and f_up) else ("file" if f_up else "text")
                        ts_now = NOW().strftime("%Y-%m-%d %H:%M:%S")
                        append_row_data(WS_DM, [ts_now, my_id, sel_fid, txt.strip(), m_type, f_name, ""])
                        dm_wh = get_user_dm_webhook(sel_fid, users_df)
                        if dm_wh:
                            me_name = get_user_name(my_id, users_df)
                            disc_msg = discord_dm(me_name, txt.strip() if txt.strip() else f"📎 Gửi file: {f_name}")
                            if f_up:
                                push_to_discord(disc_msg, dm_wh, f_up.getvalue(), f_up.name)
                            else:
                                push_to_discord(disc_msg, dm_wh)
                        st.rerun()

# ═══════════════════════════════════════════════════════════
#  10. QUẢN LÝ BẠN BÈ
# ═══════════════════════════════════════════════════════════
def render_friends_management(users_df, my_id, my_friends):
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("👫 Danh Sách Bạn Bè")
        if not my_friends:
            st.info("🥀 Độc hành hiệp khách! Chưa có bạn bè nào.")
        else:
            for f in my_friends:
                fname = get_user_name(f, users_df)
                wh_stat = "disc-on" if get_user_dm_webhook(f, users_df) else "disc-off"
                wh_lbl = "Discord Kết Nối" if wh_stat == "disc-on" else "Không Discord"
                st.markdown(f"""
                <div class="friend-card">
                    <div class="friend-info">
                        <div class="friend-avatar">{get_initials(fname)}</div>
                        <div>
                            <div style="font-weight:700;">{fname}</div>
                            <div style="font-size:12px;color:#888;">ID: {f}</div>
                            <div class="disc-badge {wh_stat}">{wh_lbl}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"❌ Xóa {fname}", key=f"del_f_{f}"):
                    updated_friends = [x for x in my_friends if x != f]
                    update_cell_by_id(WS_USERS, "User_ID", my_id, "Bạn_Bè", ",".join(updated_friends), USER_COLS)
                    st.toast(msg_friend_removed(fname))
                    st.rerun()
    with c2:
        st.subheader("➕ Thêm Bạn Bằng ID")
        f_id_add = st.text_input("Nhập User ID đối phương:", placeholder="VD: U002").strip()
        if st.button("🤝 Kết Bạn Ngay", type="primary", use_container_width=True):
            if f_id_add == my_id:
                st.error("😂 Tự kết bạn với chính mình làm gì nè?")
            elif f_id_add in my_friends:
                st.warning("👀 Hai người đã là đồng đội từ trước rồi!")
            else:
                matched = users_df[users_df["User_ID"] == f_id_add]
                if matched.empty:
                    st.error("❌ Không tìm thấy chiến binh nào có ID này!")
                else:
                    f_name_matched = matched.iloc[0]["Tên"]
                    updated_friends = my_friends + [f_id_add]
                    update_cell_by_id(WS_USERS, "User_ID", my_id, "Bạn_Bè", ",".join(updated_friends), USER_COLS)
                    st.success(msg_friend_added(f_name_matched))
                    st.rerun()

# ═══════════════════════════════════════════════════════════
#  11. XẾP HẠNG
# ═══════════════════════════════════════════════════════════
def render_leaderboard(tasks_df, users_df):
    st.subheader("🏆 Bảng Vàng Chinh Phục Deadline")
    st.markdown("Xếp hạng dựa trên số lượng công việc đã hoàn thành xuất sắc (`Đã xong` hoặc `100%`)")
    
    if tasks_df.empty:
        st.info("Chưa có dữ liệu nhiệm vụ để xếp hạng.")
        return
        
    tasks_df["Tiến_Độ_%"] = tasks_df["Tiến_Độ_%"].apply(clean_progress)
    done_tasks = tasks_df[(tasks_df["Trạng_Thái"] == "Đã xong") | (tasks_df["Tiến_Độ_%"] == 100)]
    counts = done_tasks["Người_Phụ_Trách_ID"].value_counts().to_dict()
    
    records = []
    for _, u in users_df.iterrows():
        uid = u["User_ID"]
        score = counts.get(uid, 0)
        records.append({"Hạng": 0, "Chiến Binh": u["Tên"], "User ID": uid, "Nhiệm Vụ Đã Diệt ⚔️": score})
        
    ld_df = pd.DataFrame(records).sort_values(by="Nhiệm Vụ Đã Diệt ⚔️", ascending=False).reset_index(drop=True)
    for idx in range(len(ld_df)):
        ld_df.at[idx, "Hạng"] = idx + 1
        
    def medal(rank):
        if rank == 1: return "🥇 Bá Chủ"
        if rank == 2: return "🥈 Đại Tướng"
        if rank == 3: return "🥉 Hiệp Sĩ"
        return f"🎖️ Hạng {rank}"
        
    ld_df["Danh Hiệu"] = ld_df["Hạng"].apply(medal)
    st.table(ld_df[["Danh Hiệu", "Chiến Binh", "User ID", "Nhiệm Vụ Đã Diệt ⚔️"]])

# ═══════════════════════════════════════════════════════════
#  12. TÀI KHOẢN
# ═══════════════════════════════════════════════════════════
def render_account_tab(users_df, my_id):
    st.subheader("🗑️ Cập Nhật Tài Khoản")
    me = users_df[users_df["User_ID"] == my_id].iloc[0]
    
    new_name = st.text_input("Đổi họ và tên:", value=str(me["Tên"]))
    new_pass = st.text_input("Đổi mật khẩu mới:", value=str(me["Password"]), type="password")
    
    if st.button("💾 Lưu Thay Đổi Tài Khoản", use_container_width=True):
        if not new_name.strip() or not new_pass.strip():
            st.error("Không được để trống Tên hoặc Mật khẩu!")
        else:
            update_cell_by_id(WS_USERS, "User_ID", my_id, "Tên", new_name.strip(), USER_COLS)
            update_cell_by_id(WS_USERS, "User_ID", my_id, "Password", new_pass.strip(), USER_COLS)
            st.success("🎉 Đã cập nhật hồ sơ cá nhân thành công! Hãy làm mới ứng dụng.")
            fetch_all_data.clear()
            st.rerun()

# ═══════════════════════════════════════════════════════════
#  13. RUNTIME INITIALIZATION
# ═══════════════════════════════════════════════════════════
data = fetch_all_data()
if not st.session_state["logged_in"]:
    show_auth_page(data)
else:
    main_app(data)