import pandas as pd
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from zoneinfo import ZoneInfo
from datetime import datetime
import json
import os
import random
import streamlit as st
import time

if not os.path.exists("credentials.json"):
    if "gcp_service_account" in st.secrets:
        with open("credentials.json", "w") as f:
            json.dump(dict(st.secrets["gcp_service_account"]), f)

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
def NOW():
    return datetime.now(TZ)

st.set_page_config(page_title="Deadline Slayer ⚔️", page_icon="⚔️",
                   layout="wide", initial_sidebar_state="expanded")

for k, v in [("sheet_name", "DeadlineSlayer_DB"), ("logged_in", False), ("current_user", None), ("_last_fetch", 0)]:
    if k not in st.session_state:
        st.session_state[k] = v

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif;}
[data-testid="metric-container"]{background:#16161a;border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:16px !important;box-shadow:0 4px 6px rgba(0,0,0,.2);}
.stButton>button[kind="primary"]{background:#5865F2;border:none;border-radius:8px;font-weight:700;color:white;}
.stButton>button[kind="primary"]:hover{background:#404EED;}
.chat-wrap{display:flex;flex-direction:column;gap:8px;padding:6px 2px;}
.msg-bubble{display:flex;align-items:flex-end;gap:8px;max-width:86%;}
.msg-avatar{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;letter-spacing:.5px;}
.msg-body{display:flex;flex-direction:column;gap:2px;}
.msg-meta{font-size:11px;padding:0 6px;}
.msg-text{padding:9px 14px;border-radius:16px;font-size:14px;line-height:1.55;word-break:break-word;border:1px solid transparent;}
.msg-file{display:inline-flex;align-items:center;gap:8px;margin-top:5px;padding:7px 12px;border-radius:10px;font-size:13px;text-decoration:none;border:1px solid;}
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
@media(prefers-color-scheme:dark){.msg-other .msg-text{background:#2b2d31;color:#e8e9eb;border-color:#3f4147;}.msg-other .msg-avatar{background:#3d4270;color:#9ba4f5;}.msg-other .msg-meta{color:#888;}.msg-other .msg-file{background:#2b2d31;color:#ccc;border-color:#444;}.msg-dm .msg-text{background:#1e2340;color:#e2e6ff;border-color:#3b4680;}.msg-dm .msg-avatar{background:#2a3370;color:#9ba8ff;}.msg-dm .msg-meta{color:#888;}.msg-dm .msg-file{background:#1e2340;color:#9ba8ff;border-color:#3b4680;}.msg-me .msg-meta{color:#aaa;}}
.date-sep{text-align:center;font-size:11px;color:#aaa;margin:6px 0;display:flex;align-items:center;gap:8px;}.date-sep::before,.date-sep::after{content:'';flex:1;height:1px;background:currentColor;opacity:.3;}
.chat-empty{text-align:center;padding:36px 20px;color:#999;font-size:14px;}.chat-empty-icon{font-size:34px;margin-bottom:8px;}
.disc-badge{display:inline-flex;align-items:center;gap:5px;font-size:12px;padding:3px 10px;border-radius:20px;font-weight:600;margin-bottom:4px;}.disc-on{background:#e8f5e9;color:#2e7d32;}.disc-off{background:#f0f0f0;color:#888;}
@media(prefers-color-scheme:dark){.disc-on{background:#1b3a1d;color:#81c784;}.disc-off{background:#2a2a2a;color:#777;}}
.friend-card{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-radius:10px;margin-bottom:6px;background:#f5f6f8;border:1px solid #e4e6ea;}
@media(prefers-color-scheme:dark){.friend-card{background:#1e1f22;border-color:#2b2d31;}}
.friend-info{display:flex;align-items:center;gap:10px;}.friend-avatar{width:36px;height:36px;border-radius:50%;background:#dde2ff;color:#3d47cc;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;}
@media(prefers-color-scheme:dark){.friend-avatar{background:#3d4270;color:#9ba4f5;}}
.group-card{background:#f5f6f8;border:1px solid #e4e6ea;border-radius:10px;padding:12px;margin-bottom:10px;}
@media(prefers-color-scheme:dark){.group-card{background:#1e1f22;border-color:#2b2d31;}}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════
#  ULTRA AGGRESSIVE CACHE - 10 PHÚT = 1 REQUEST
# ═══════════════════════════════════════════════════════════
CACHE_TTL = 600  # 10 phút

@st.cache_data(ttl=CACHE_TTL)
def fetch_all_data_cached():
    """Chỉ gọi API nếu cache hết hạn"""
    client = get_sheets_client()
    empty = {
        "tasks":  pd.DataFrame(columns=TASK_COLS),
        "users":  pd.DataFrame(columns=USER_COLS),
        "groups": pd.DataFrame(columns=GROUP_COLS),
        "proofs": pd.DataFrame(columns=PROOF_COLS),
        "chat":   pd.DataFrame(columns=CHAT_COLS),
        "dm":     pd.DataFrame(columns=DM_COLS),
    }
    if not client:
        return empty
    try:
        ss = client.open(st.session_state["sheet_name"])
        init_spreadsheet_structure(ss)
        def get_df(name, cols):
            vals = ss.worksheet(name).get_all_values()
            if not vals or len(vals) <= 1:
                return pd.DataFrame(columns=cols)
            header = [COLUMN_ALIAS.get(h, h) for h in vals[0]]
            rows = vals[1:]
            n = len(header)
            rows = [r[:n] + [""] * max(0, n - len(r)) for r in rows]
            df = pd.DataFrame(rows, columns=header)
            df = df.loc[:, ~df.columns.duplicated()]
            if "" in df.columns:
                df = df.drop(columns=[""])
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
    except Exception as e:
        st.error(f"❌ Lỗi: {e}")
        return empty

def fetch_all_data():
    """Wrapper - luôn dùng cache nếu còn hạn"""
    return fetch_all_data_cached()

def invalidate_cache():
    """Xoá cache khi cần update"""
    fetch_all_data_cached.clear()

# ═══════════════════════════════════════════════════════════
#  1. SCHEMA
# ═══════════════════════════════════════════════════════════
SCOPES = ["https://spreadsheets.google.com/feeds",
          "https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

WS_TASKS = "Tasks"; WS_USERS = "Users"; WS_GROUPS = "Groups"
WS_PROOFS = "Proofs"; WS_CHAT = "ChatRoom"; WS_DM = "DirectMessages"

TASK_COLS  = ["ID","Tên_Công_Việc","Môn_Học","Người_Phụ_Trách_ID","Deadline",
              "Độ_Ưu_Tiên","Trạng_Thái","Tiến_Độ_%","Giai_Đoạn_Hiện_Tại",
              "Ghi_Chú","Nhắc_Mỗi_Phút","Nhắc_Lần_Cuối","Ngày_Tạo","Ngày_Cập_Nhật"]
USER_COLS  = ["User_ID","Password","Tên","Email","Bạn_Bè","Discord_Webhook_DM","Ngày_Tạo"]
GROUP_COLS = ["Group_ID","Tên_Nhóm","Trưởng_Nhóm_ID","Thành_Viên_IDs","Discord_Webhook","Ngày_Tạo"]
PROOF_COLS = ["Task_ID","Người_Nộp_ID","Thời_Gian","Mô_Tả","Giai_Đoạn","URL_File"]
CHAT_COLS  = ["Thời_Gian","Người_Gửi_ID","Group_Nhận_ID","Nội_Dung","Loại","File_Tên","File_URL"]
DM_COLS    = ["Thời_Gian","Người_Gửi_ID","Người_Nhận_ID","Nội_Dung","Loại","File_Tên","File_URL"]

COLUMN_ALIAS = {
    "Người_Phụ_Trác":  "Người_Phụ_Trách_ID",
    "Người_Phụ_Trách": "Người_Phụ_Trách_ID",
    "Tên_Công_Viêc":   "Tên_Công_Việc",
    "Tiến_Độ":         "Tiến_Độ_%",
    "Tiến_Đô_%":       "Tiến_Độ_%",
    "Đô_Uu_Tiên":      "Độ_Ưu_Tiên",
    "Đô_Ưu_Tiên":      "Độ_Ưu_Tiên",
    "Trạng_Thai":      "Trạng_Thái",
    "Môn_Hoc":         "Môn_Học",
    "Người_Gửi":       "Người_Gửi_ID",
    "Người_Nhận":      "Người_Nhận_ID",
    "Group_Nhận":      "Group_Nhận_ID",
    "Nôi_Dung":        "Nội_Dung",
    "Bạn_Be":          "Bạn_Bè",
    "Ngay_Tạo":        "Ngày_Tạo",
    "Ngay_Cập_Nhật":   "Ngày_Cập_Nhật",
}

# ═══════════════════════════════════════════════════════════
#  2. MESSAGES
# ═══════════════════════════════════════════════════════════
def msg_login_success(name):
    return random.choice([
        f"⚔️ Chào **{name}**! Deadline đang run!",
        f"🔥 YO **{name}**! Sẵn sàng chưa?",
    ])
def msg_login_fail():
    return "❌ Thông tin không đúng!"
def msg_register_success(new_id):
    return f"🎉 Tài khoản **`{new_id}`** đã tạo!"
def msg_task_assigned(task_name, assignee_name):
    return f"🚀 **{assignee_name}** → **{task_name}**"
def msg_progress_saved(percent):
    if percent == 100: return "🏆 100%!"
    return f"💾 {percent}%!"
def msg_friend_added(name):
    return f"🤝 **{name}** là bạn!"
def msg_friend_removed(name):
    return f"👋 Xóa **{name}**"
def msg_group_created(n): return f"🏰 Nhóm **{n}** tạo!"
def msg_group_updated(): return "💾 Cập nhật!"
def msg_group_deleted(): return "💥 Xóa!"
def msg_proof_sent(): return "📤 Nộp!"
def msg_webhook_saved(): return "🤖 Lưu!"
def msg_discord_broadcast(leader_name):
    return f"📢 **[{leader_name}]**\n"
def discord_task_assigned(task_name, assignee_name, deadline, priority):
    prio = {"Cao": "🔴", "Trung bình": "🟡", "Thấp": "🟢"}.get(priority, "")
    return f"🚨 **{task_name}**\n👤 {assignee_name}\n⏰ {deadline}\n{prio}"
def discord_group_created(n): return f"🎊 **{n}**"
def discord_proof_sent(name, task): return f"✅ **{name}** → **{task}**"
def discord_dm(sender, content): return f"📩 **{sender}**: {content}"
def discord_group_chat(sender, group, content): return f"💬 **{sender}** [{group}]: {content}"

# ═══════════════════════════════════════════════════════════
#  3. GOOGLE SHEETS - OPTIMIZED
# ═══════════════════════════════════════════════════════════
@st.cache_resource(ttl=600)
def get_sheets_client():
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"❌ {e}")
        return None

@st.cache_resource(ttl=600)
def get_spreadsheet():
    """Cache toàn bộ spreadsheet object"""
    client = get_sheets_client()
    if not client:
        return None
    try:
        return client.open(st.session_state["sheet_name"])
    except:
        return None

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
    except:
        pass

def init_spreadsheet_structure(ss):
    existing = {ws.title: ws for ws in ss.worksheets()}
    schema = {
        WS_TASKS: TASK_COLS, WS_USERS: USER_COLS, WS_GROUPS: GROUP_COLS,
        WS_PROOFS: PROOF_COLS, WS_CHAT: CHAT_COLS, WS_DM: DM_COLS,
    }
    for name, cols in schema.items():
        if name not in existing:
            ws = ss.add_worksheet(title=name, rows=1000, cols=max(len(cols), 10))
            ws.append_row(cols)
        else:
            migrate_sheet(existing[name], cols)

def get_ws(name):
    ss = get_spreadsheet()
    if not ss:
        return None
    try:
        return ss.worksheet(name)
    except:
        return None

def append_row_data(name, row, schema):
    """Thêm dữ liệu + xoá cache"""
    ws = get_ws(name)
    if not ws:
        st.error(f"❌ Lỗi kết nối!")
        return False
    try:
        expected_len = len(schema)
        row = list(row) + [""] * max(0, expected_len - len(row))
        row = row[:expected_len]
        ws.append_row(row, value_input_option="USER_ENTERED")
        time.sleep(0.3)
        invalidate_cache()
        return True
    except Exception as e:
        st.error(f"❌ {e}")
        return False

def batch_update_cells(ws_name, updates_dict, schema):
    """
    Cập nhật nhiều ô trong một lần gọi API
    updates_dict: {id_value: {col_name: new_value, ...}, ...}
    """
    ws = get_ws(ws_name)
    if not ws:
        return False
    try:
        actual_header = ws.row_values(1)
        actual_header = [COLUMN_ALIAS.get(h, h) for h in actual_header]
        
        id_col = schema[0]  # Cột ID luôn ở vị trí đầu
        if id_col not in actual_header:
            return False
        
        id_col_idx = actual_header.index(id_col)
        all_values = ws.get_all_values()
        
        updates = []
        for row_idx, row in enumerate(all_values[1:], start=2):  # Bỏ header
            if len(row) > id_col_idx and row[id_col_idx] in updates_dict:
                for col_name, new_val in updates_dict[row[id_col_idx]].items():
                    if col_name in actual_header:
                        col_idx = actual_header.index(col_name)
                        updates.append({
                            "range": f"{chr(65 + col_idx)}{row_idx}",
                            "values": [[new_val]]
                        })
        
        if updates:
            for update in updates:
                ws.update(update["range"], update["values"])
            time.sleep(0.3)
            invalidate_cache()
        return True
    except Exception as e:
        st.error(f"❌ {e}")
        return False

def update_cell_by_id(ws_name, id_col, item_id, upd_col, new_val, schema):
    """Cập nhật + xoá cache (tương thích với code cũ)"""
    batch_update_cells(ws_name, {item_id: {upd_col: new_val}}, schema)

def delete_row_by_id(ws_name, id_col, item_id, schema):
    """Xoá + xoá cache"""
    ws = get_ws(ws_name)
    if not ws:
        return False
    try:
        all_values = ws.get_all_values()
        id_col_idx = schema.index(id_col)
        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) > id_col_idx and row[id_col_idx] == str(item_id):
                ws.delete_rows(idx)
                time.sleep(0.3)
                invalidate_cache()
                return True
        return False
    except:
        return False

# ═══════════════════════════════════════════════════════════
#  4. DISCORD & HELPERS
# ═══════════════════════════════════════════════════════════
def push_to_discord(message, webhook_url="", file_bytes=None, filename=None):
    if not webhook_url or "discord.com/api/webhooks" not in webhook_url:
        return False
    try:
        if file_bytes and filename:
            r = requests.post(webhook_url, data={"content": message},
                              files={"file": (filename, file_bytes)}, timeout=15)
        else:
            r = requests.post(webhook_url, json={"content": message}, timeout=5)
        return r.status_code in (200, 204)
    except:
        return False

def get_group_webhook(gid, groups_df):
    m = groups_df[groups_df["Group_ID"] == gid]
    return str(m.iloc[0].get("Discord_Webhook", "")).strip() if not m.empty else ""

def get_user_dm_webhook(uid, users_df):
    m = users_df[users_df["User_ID"] == uid]
    return str(m.iloc[0].get("Discord_Webhook_DM", "")).strip() if not m.empty else ""

def clean_progress(val):
    if pd.isna(val) or val == "":
        return 0.0
    try:
        return float(str(val).replace("%", "").strip())
    except:
        return 0.0

def parse_dl(dl_str):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(dl_str).strip(), fmt).replace(tzinfo=TZ)
        except:
            continue
    return None

def calc_status(row):
    if str(row.get("Trạng_Thái", "")) == "Đã xong" or clean_progress(row.get("Tiến_Độ_%")) == 100:
        return "done"
    dl = parse_dl(row.get("Deadline", ""))
    if dl is None:
        return "unknown"
    h = (dl - NOW()).total_seconds() / 3600
    if h < 0:    return "overdue"
    if h <= 24:  return "urgent"
    if h <= 72:  return "warning"
    return "safe"

def fmt_remaining(row):
    if str(row.get("Trạng_Thái", "")) == "Đã xong":
        return "✅ Xong"
    dl = parse_dl(row.get("Deadline", ""))
    if dl is None:
        return "—"
    s = int((dl - NOW()).total_seconds())
    if s < 0:
        return "🛑 QUÁ HẠN"
    d, r = divmod(s, 86400); h, r = divmod(r, 3600)
    if d > 0:  return f"{d}n {h}h"
    return f"{h}h"

def get_user_name(uid, users_df):
    m = users_df[users_df["User_ID"] == uid]
    return m.iloc[0]["Tên"] if not m.empty else f"({uid})"

def get_initials(name):
    p = name.strip().split()
    if len(p) >= 2:
        return (p[0][0] + p[-1][0]).upper()
    return name[:2].upper() if len(name) >= 2 else name.upper()

def file_icon(fname):
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    return {"pdf": "📄", "doc": "📝", "docx": "📝", "xls": "📊", "xlsx": "📊",
            "ppt": "📋", "pptx": "📋", "zip": "🗜", "rar": "🗜",
            "png": "🖼", "jpg": "🖼", "jpeg": "🖼", "gif": "🖼"}.get(ext, "📎")

def render_bubble(sender_name, content, time_str, is_me, variant="group", file_name="", file_url="", msg_type="text"):
    initials = get_initials(sender_name)
    cls  = "msg-me" if is_me else ("msg-dm" if variant == "dm" else "msg-other")
    meta = time_str if is_me else f"{sender_name} · {time_str}"
    body = ""
    if msg_type in ("text", "both") and str(content).strip():
        body += f'<div class="msg-text">{content}</div>'
    if msg_type in ("file", "both") and file_name:
        icon = file_icon(file_name)
        body += f'<div class="msg-file">📎 {file_name}</div>'
    return f'<div class="msg-bubble {cls}"><div class="msg-avatar">{initials}</div><div class="msg-body"><div class="msg-meta">{meta}</div>{body}</div></div>'

def render_messages_html(rows_iter, my_id, users_df, variant="group"):
    html = '<div class="chat-wrap">'
    for _, row in rows_iter:
        sender = get_user_name(row["Người_Gửi_ID"], users_df)
        is_me = row["Người_Gửi_ID"] == my_id
        ts = str(row["Thời_Gian"])
        short = ts[11:16] if len(ts) >= 16 else ts
        msg_type = str(row.get("Loại", "text")) or "text"
        html += render_bubble(sender, str(row["Nội_Dung"]), short, is_me, variant,
                              str(row.get("File_Tên", "")), str(row.get("File_URL", "")), msg_type)
    html += '</div>'
    return html

# ═══════════════════════════════════════════════════════════
#  5. AUTH
# ═══════════════════════════════════════════════════════════
def show_auth_page():
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align:center'>🛡️ DEADLINE SLAYER</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#888'>Quản lý Deadline & Giao Việc</p>", unsafe_allow_html=True)

        client = get_sheets_client()
        if client is None:
            st.error("❌ Lỗi Google Sheets!")
        else:
            st.success(f"✅ {st.session_state['sheet_name']}")

        t1, t2 = st.tabs(["🔑 Đăng Nhập", "📝 Đăng Ký"])

        with t1:
            st.subheader("Đăng nhập bằng ID hoặc Email")
            login_input = st.text_input("User ID / Email:", key="login_input").strip()
            login_pass = st.text_input("Mật khẩu:", type="password", key="login_pass")
            if st.button("🚀 Đăng Nhập", use_container_width=True, type="primary", key="btn_login"):
                if not login_input or not login_pass:
                    st.error("⚠️ Nhập đủ thông tin!")
                else:
                    fu = fetch_all_data()["users"]
                    if fu.empty:
                        st.error("👻 Chưa có tài khoản!")
                    else:
                        fu["User_ID"]  = fu["User_ID"].astype(str).str.strip()
                        fu["Email"] = fu["Email"].astype(str).str.strip()
                        fu["Password"] = fu["Password"].astype(str).str.strip()
                        m = fu[((fu["User_ID"] == login_input) | (fu["Email"] == login_input)) & (fu["Password"] == login_pass)]
                        if not m.empty:
                            st.session_state.update({
                                "logged_in":    True,
                                "current_user": m.iloc[0].to_dict()
                            })
                            st.success(msg_login_success(m.iloc[0]["Tên"]))
                            st.rerun()
                        else:
                            st.error(msg_login_fail())

        with t2:
            rn = st.text_input("Họ tên:", key="rn").strip()
            re = st.text_input("Email:", key="re").strip()
            rp = st.text_input("Mật khẩu:", type="password", key="rp")
            rw = st.text_input("Discord (tuỳ):", placeholder="https://...", key="rw").strip()
            if st.button("✨ Tạo", use_container_width=True, key="btn_register"):
                if not rn or not re or not rp:
                    st.error("⚠️ Điền đủ!")
                else:
                    fu = fetch_all_data()["users"]
                    if not fu.empty and re in fu["Email"].astype(str).str.strip().values:
                        st.error("📧 Email tồn tại!")
                    else:
                        nums = [int(i[1:]) for i in fu["User_ID"].dropna().astype(str).tolist()
                                if i.startswith("U") and i[1:].isdigit()] if not fu.empty else []
                        new_id = f"U{(max(nums) + 1 if nums else 1):03d}"
                        if append_row_data(WS_USERS, [new_id, rp, rn, re, "", rw, NOW().strftime("%Y-%m-%d %H:%M:%S")], USER_COLS):
                            st.success(msg_register_success(new_id))
                        else:
                            st.error("❌ Lỗi!")

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
        st.warning("⚠️ Hết hạn!")
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
        st.success(f"👤 **{cu['Tên']}**\n\n🆔 {my_id}")
        if st.button("🚪 Đăng xuất", use_container_width=True, key="sidebar_logout"):
            st.session_state.update({"logged_in": False, "current_user": None})
            st.rerun()
        st.markdown("---")
        st.markdown("### 🔔 Webhook")
        cur_wh = str(me.get("Discord_Webhook_DM", "")).strip()
        new_wh = st.text_input("Webhook:", value=cur_wh, key="sidebar_wh").strip()
        if st.button("💾 Lưu", use_container_width=True, key="sidebar_save_wh"):
            batch_update_cells(WS_USERS, {my_id: {"Discord_Webhook_DM": new_wh}}, USER_COLS)
            st.toast(msg_webhook_saved())
        if is_leader:
            st.markdown("---")
            st.markdown("### 🤖 Bot")
            mg = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
            go = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in mg.iterrows()}
            if go:
                sg = st.selectbox("Nhóm:", list(go.keys()), format_func=lambda x: go[x], key="sidebar_grp_sel")
                mt = st.text_area("Nội dung:", key="sidebar_broadcast_txt", height=60)
                af = st.file_uploader("📎", key="sidebar_broadcast_file")
                if st.button("🚀 Gửi", use_container_width=True, type="primary", key="sidebar_discord_blast"):
                    wh  = get_group_webhook(sg, groups_df)
                    msg = msg_discord_broadcast(cu["Tên"]) + mt
                    ok  = push_to_discord(msg, wh, af.getvalue(), af.name) if af else push_to_discord(msg, wh)
                    st.toast("✅" if ok else "❌")
        st.markdown("---")
        if st.button("🔄 Làm mới", use_container_width=True, key="sidebar_refresh"):
            get_spreadsheet.clear()
            invalidate_cache()
            st.rerun()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard", "👥 Nhóm", "💬 Chat",
        "👫 Bạn", "🏆 Xếp", "⚙️ Tài"])

    with tab1: render_dashboard(tasks_df, groups_df, users_df, my_id)
    with tab2: render_network_and_tasks(users_df, groups_df, tasks_df, my_id, my_friends)
    with tab3: render_chat(data["chat"], data["dm"], groups_df, users_df, my_id, my_friends)
    with tab4: render_friends_management(users_df, my_id, my_friends)
    with tab5: render_leaderboard(tasks_df, users_df, my_id, my_friends)
    with tab6: render_account_tab(users_df, my_id)

# ═══════════════════════════════════════════════════════════
#  7-12. RENDER FUNCTIONS
# ═══════════════════════════════════════════════════════════
def render_dashboard(tasks_df, groups_df, users_df, my_id):
    st.subheader("📊 Dashboard")
    my_groups = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False) | (groups_df["Trưởng_Nhóm_ID"] == my_id)]
    all_group_members = set()
    for _, g in my_groups.iterrows():
        for m in str(g["Thành_Viên_IDs"]).split(","):
            if m.strip():
                all_group_members.add(m.strip())
    if all_group_members:
        vt = tasks_df[(tasks_df["Người_Phụ_Trách_ID"] == my_id) | (tasks_df["Người_Phụ_Trách_ID"].isin(all_group_members))].copy()
    else:
        vt = tasks_df[tasks_df["Người_Phụ_Trách_ID"] == my_id].copy()
    if vt.empty:
        st.info("🎉 Chưa có task!")
        return
    vt["Tiến_Độ_%"] = vt["Tiến_Độ_%"].apply(clean_progress)
    vt["_st"]  = vt.apply(calc_status, axis=1)
    vt["_rem"] = vt.apply(fmt_remaining, axis=1)
    slabels = {"done": "✅", "overdue": "💀", "urgent": "🔥", "warning": "⚠️", "safe": "😎", "unknown": "❓"}
    for idx, row in vt.iterrows():
        bc = {"done": "#2e7d32", "overdue": "#d32f2f", "urgent": "#f57c00", "warning": "#fbc02d", "safe": "#1976d2"}.get(row["_st"], "#ccc")
        an = get_user_name(row["Người_Phụ_Trách_ID"], users_df)
        st.markdown(f"<div style='border-left:5px solid {bc};background:#111112;border-radius:8px;padding:12px;margin-bottom:8px;'><b>{row['Tên_Công_Việc']}</b> <span style='float:right;color:{bc};'>{slabels.get(row['_st'], '')}</span><div style='font-size:11px;color:#aaa;'>👤 {an} | 📚 {row['Môn_Học']} | ⏰ {row['Deadline']}</div><div style='color:{bc};'>{row['_rem']} | {int(row['Tiến_Độ_%'])}%</div></div>", unsafe_allow_html=True)
        if row["Người_Phụ_Trách_ID"] == my_id:
            with st.expander("🛠"):
                c1, c2 = st.columns(2)
                with c1:
                    np_ = st.slider("Tiến độ:", 0, 100, int(row["Tiến_Độ_%"]), key=f"sld_{row['ID']}")
                    if st.button("💾", key=f"btn_{row['ID']}"):
                        updates = {"Tiến_Độ_%": np_}
                        if np_ == 100:
                            updates["Trạng_Thái"] = "Đã xong"
                        batch_update_cells(WS_TASKS, {row["ID"]: updates}, TASK_COLS)
                        st.success(msg_progress_saved(np_))
                        st.rerun()
                with c2:
                    pf = st.file_uploader("📤", key=f"file_{row['ID']}")
                    if st.button("🚀", key=f"pb_{row['ID']}"):
                        if pf:
                            an = get_user_name(row["Người_Phụ_Trách_ID"], users_df)
                            ag = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False)]
                            for _, g in ag.iterrows():
                                push_to_discord(discord_proof_sent(an, row["Tên_Công_Việc"]), str(g.get("Discord_Webhook", "")).strip(), pf.getvalue(), pf.name)
                            st.success(msg_proof_sent())

def render_network_and_tasks(users_df, groups_df, tasks_df, my_id, my_friends):
    st.subheader("👥 Nhóm & Giao Việc")
    sub1, sub2, sub3 = st.tabs(["📍 Tạo", "⚙️ Quản Lý", "📋 Giao"])
    with sub1:
        grp_name = st.text_input("Tên:", key="new_grp_name")
        grp_wh = st.text_input("Webhook:", key="new_grp_wh").strip()
        fo = {f: get_user_name(f, users_df) for f in my_friends if f}
        sel_f = st.multiselect("TV:", list(fo.keys()), format_func=lambda x: fo[x], key="members")
        if st.button("🏰", use_container_width=True, type="primary", key="create_grp"):
            if grp_name:
                fg = fetch_all_data()["groups"]
                nums = [int(i[1:]) for i in fg["Group_ID"].dropna().astype(str) if i.startswith("G") and i[1:].isdigit()] if not fg.empty else []
                gid = f"G{(max(nums)+1 if nums else 1):03d}"
                if append_row_data(WS_GROUPS, [gid, grp_name, my_id, ",".join([my_id]+sel_f), grp_wh, NOW().strftime("%Y-%m-%d")], GROUP_COLS):
                    st.success("✅")
                    st.rerun()
    with sub2:
        mld = groups_df[groups_df["Trưởng_Nhóm_ID"] == my_id]
        if mld.empty:
            st.info("Chưa có")
        else:
            for _, gd in mld.iterrows():
                with st.expander(f"📍 {gd['Tên_Nhóm']}"):
                    new_name = st.text_input("Tên:", value=gd["Tên_Nhóm"], key=f"n_{gd['Group_ID']}")
                    new_wh = st.text_input("Webhook:", value=str(gd.get("Discord_Webhook", "")), key=f"w_{gd['Group_ID']}")
                    fo2 = {f: get_user_name(f, users_df) for f in my_friends if f}
                    new_members = st.multiselect("TV:", list(fo2.keys()), key=f"m_{gd['Group_ID']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("💾", key=f"s_{gd['Group_ID']}"):
                            batch_update_cells(WS_GROUPS, {gd["Group_ID"]: {
                                "Tên_Nhóm": new_name,
                                "Thành_Viên_IDs": ",".join([my_id]+new_members),
                                "Discord_Webhook": new_wh
                            }}, GROUP_COLS)
                            st.success("✅")
                            st.rerun()
                    with c2:
                        if st.button("🗑️", key=f"d_{gd['Group_ID']}"):
                            if delete_row_by_id(WS_GROUPS, "Group_ID", gd["Group_ID"], GROUP_COLS):
                                st.rerun()
    with sub3:
        assignable = {my_id: "Tự"}
        for f in my_friends:
            if f:
                assignable[f] = get_user_name(f, users_df)
        t_name = st.text_input("Tên:", key="task_name")
        t_sub = st.text_input("Môn:", key="task_sub")
        t_assignee = st.selectbox("Giao:", list(assignable.keys()), format_func=lambda x: assignable[x], key="task_assignee")
        t_dl_date = st.date_input("Deadline:", key="task_date")
        t_prio = st.selectbox("Độ ưu:", ["Thấp", "Trung bình", "Cao"], index=1, key="task_prio")
        if st.button("⚔️", type="primary", use_container_width=True, key="assign"):
            if t_name.strip():
                ft = fetch_all_data()["tasks"]
                nums = [int(i[1:]) for i in ft["ID"].dropna().astype(str) if i.startswith("T") and i[1:].isdigit()] if not ft.empty else []
                tid = f"T{(max(nums)+1 if nums else 1):03d}"
                dl = datetime.combine(t_dl_date, datetime.strptime("23:59", "%H:%M").time()).strftime("%Y-%m-%d %H:%M:%S")
                if append_row_data(WS_TASKS, [tid, t_name.strip(), t_sub, t_assignee, dl, t_prio, "Chưa làm", "0", "", "", "", "", NOW().strftime("%Y-%m-%d"), ""], TASK_COLS):
                    st.success("✅")
                    st.rerun()

def render_chat(chat_df, dm_df, groups_df, users_df, my_id, my_friends):
    t1, t2 = st.tabs(["💬", "📩"])
    with t1:
        in_grps = groups_df[groups_df["Thành_Viên_IDs"].str.contains(my_id, na=False) | (groups_df["Trưởng_Nhóm_ID"] == my_id)]
        if not in_grps.empty:
            g_opts = {g["Group_ID"]: g["Tên_Nhóm"] for _, g in in_grps.iterrows()}
            sel_gid = st.selectbox("Nhóm:", list(g_opts.keys()), format_func=lambda x: g_opts[x], key="chat_gid")
            g_msgs = chat_df[chat_df["Group_Nhận_ID"]==sel_gid].sort_values("Thời_Gian") if not chat_df.empty else pd.DataFrame(columns=CHAT_COLS)
            
            grp_info = groups_df[groups_df["Group_ID"] == sel_gid]
            grp_webhook = str(grp_info.iloc[0].get("Discord_Webhook", "")).strip() if not grp_info.empty else ""
            
            with st.container(height=300):
                if g_msgs.empty:
                    st.caption("Chưa có")
                else:
                    st.markdown(render_messages_html(g_msgs.iterrows(), my_id, users_df, "group"), unsafe_allow_html=True)
            with st.form("grp"):
                txt = st.text_input("Tin:", key="grp_txt")
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    if st.form_submit_button("Gửi", use_container_width=True):
                        if txt.strip():
                            append_row_data(WS_CHAT, [NOW().strftime("%Y-%m-%d %H:%M:%S"), my_id, sel_gid, txt.strip(), "text", "", ""], CHAT_COLS)
                            st.rerun()
                with col2:
                    if st.form_submit_button("🤖", use_container_width=True):
                        if txt.strip() and grp_webhook:
                            sender_name = get_user_name(my_id, users_df)
                            grp_name = grp_info.iloc[0]["Tên_Nhóm"] if not grp_info.empty else "Unknown"
                            msg = discord_group_chat(sender_name, grp_name, txt.strip())
                            push_to_discord(msg, grp_webhook)
                            st.toast("✅ Đã gửi Discord!")
                        elif not grp_webhook:
                            st.warning("⚠️ Chưa cấu hình Webhook!")
    with t2:
        valid_friends = [f for f in my_friends if f]
        if valid_friends:
            f_opts = {f: get_user_name(f, users_df) for f in valid_friends}
            sel_fid = st.selectbox("Bạn:", list(f_opts.keys()), format_func=lambda x: f_opts[x], key="dm_fid")
            d_msgs = dm_df[((dm_df["Người_Gửi_ID"]==my_id) & (dm_df["Người_Nhận_ID"]==sel_fid)) | ((dm_df["Người_Gửi_ID"]==sel_fid) & (dm_df["Người_Nhận_ID"]==my_id))].sort_values("Thời_Gian") if not dm_df.empty else pd.DataFrame(columns=DM_COLS)
            
            friend_webhook = get_user_dm_webhook(sel_fid, users_df)
            
            with st.container(height=300):
                if d_msgs.empty:
                    st.caption("Chưa có")
                else:
                    st.markdown(render_messages_html(d_msgs.iterrows(), my_id, users_df, "dm"), unsafe_allow_html=True)
            with st.form("dm"):
                txt = st.text_input("Tin:", key="dm_txt")
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    if st.form_submit_button("Gửi", use_container_width=True):
                        if txt.strip():
                            append_row_data(WS_DM, [NOW().strftime("%Y-%m-%d %H:%M:%S"), my_id, sel_fid, txt.strip(), "text", "", ""], DM_COLS)
                            st.rerun()
                with col2:
                    if st.form_submit_button("🤖", use_container_width=True):
                        if txt.strip() and friend_webhook:
                            sender_name = get_user_name(my_id, users_df)
                            msg = discord_dm(sender_name, txt.strip())
                            push_to_discord(msg, friend_webhook)
                            st.toast("✅ Đã gửi Discord!")
                        elif not friend_webhook:
                            st.warning("⚠️ Bạn chưa cấu hình Webhook!")

def render_friends_management(users_df, my_id, my_friends):
    st.subheader("👫 Bạn Bè")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### ➕")
        f_id = st.text_input("ID:", key="add_f").strip()
        if st.button("Thêm", type="primary", use_container_width=True, key="add_btn"):
            if f_id and f_id != my_id:
                if not users_df[users_df["User_ID"]==f_id].empty:
                    batch_update_cells(WS_USERS, {my_id: {"Bạn_Bè": ",".join(my_friends+[f_id])}}, USER_COLS)
                    st.rerun()
    with c2:
        st.markdown("### 👥")
        for fid in my_friends:
            if fid and st.button(f"❌ {get_user_name(fid, users_df)}", key=f"del_{fid}", use_container_width=True):
                batch_update_cells(WS_USERS, {my_id: {"Bạn_Bè": ",".join([f for f in my_friends if f!=fid])}}, USER_COLS)
                st.rerun()

def render_leaderboard(tasks_df, users_df, my_id, my_friends):
    st.subheader("🏆 Xếp Hạng")
    if tasks_df.empty:
        st.info("Chưa có")
        return
    
    valid_users = [my_id] + [f for f in my_friends if f]
    
    t = tasks_df[tasks_df["Người_Phụ_Trách_ID"].isin(valid_users)].copy()
    
    if t.empty:
        st.info("Chưa có dữ liệu")
        return
    
    t["Tiến_Độ_%"] = t["Tiến_Độ_%"].apply(clean_progress)
    done = t[(t["Trạng_Thái"]=="Đã xong") | (t["Tiến_Độ_%"]>=100)]
    counts = done["Người_Phụ_Trách_ID"].value_counts().to_dict()
    
    records = [{"👤 Chiến Binh": u["Tên"], "⚔️ Hoàn": counts.get(u["User_ID"], 0)} 
               for _, u in users_df[users_df["User_ID"].isin(valid_users)].iterrows()]
    
    df = pd.DataFrame(records).sort_values("⚔️ Hoàn", ascending=False).reset_index(drop=True)
    df.index = df.index + 1
    st.dataframe(df, use_container_width=True)

def render_account_tab(users_df, my_id):
    st.subheader("⚙️ Tài Khoản")
    me = users_df[users_df["User_ID"]==my_id]
    if not me.empty:
        me = me.iloc[0]
        st.markdown(f"**ID:** {my_id} | **Email:** {me['Email']}")
        new_name = st.text_input("Tên:", value=str(me["Tên"]), key="acc_name")
        new_pass = st.text_input("Pass:", value=str(me["Password"]), type="password", key="acc_pass")
        if st.button("💾", use_container_width=True, key="save_acc"):
            if new_name.strip() and new_pass.strip():
                batch_update_cells(WS_USERS, {my_id: {
                    "Tên": new_name.strip(),
                    "Password": new_pass.strip()
                }}, USER_COLS)
                st.success("✅")
                st.rerun()

# ═══════════════════════════════════════════════════════════
#  LAUNCH
# ═══════════════════════════════════════════════════════════
_data = fetch_all_data()
if not st.session_state["logged_in"]:
    show_auth_page()
else:
    main_app(_data)
