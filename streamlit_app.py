import streamlit as st
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection
from streamlit_calendar import calendar
import pandas as pd
import re
import random
from datetime import datetime

st.set_page_config(page_title="114混排盃賽事網", layout="wide")

# 💡 專屬日曆 CSS：強制允許文字自動折行多行顯示
CALENDAR_CSS = """
.fc-event-main {
    padding: 3px !important;
}
.fc-event-title {
    white-space: pre-wrap !important; /* 💡 允許文字換行 */
    word-wrap: break-word !important;
    line-height: 1.4 !important;      /* 增加行距，確保文字不會擁擠 */
    font-size: 0.95em !important;
}
"""

# --- 1. 基礎設定與可用日期 ---
GROUPS = {
    "第 1 組": ["土木B", "園藝系", "化工", "工海"],
    "第 2 組": ["生工/農經聯隊", "化學系+化學所", "會計", "藥學系"],
    "第 3 組": ["土木", "機械系", "森林系", "法律系"]
}

CONSTRAINTS = {
    "森林系": [4, 2], "土木B": [4, 2], "土木": [2, 4],
    "生工/農經聯隊": [1, 4], "園藝系": [3, 4], "藥學系": [4, 2],
    "工海": [4, 5], "化學系+化學所": [3, 1], "機械系": [4, 1],
    "會計": [2, 5], "化工": [3, 2], "法律系": [4, 2]
}

def get_avail(t1, t2):
    all_days = [1, 2, 3, 4, 5]
    forbidden = set(CONSTRAINTS.get(t1, []) + CONSTRAINTS.get(t2, []))
    avail = [f"週{['0','一','二','三','四','五'][d]}" for d in all_days if d not in forbidden]
    return "、".join(avail) if avail else "需協調"

# --- 2. 讀取資料 ---
conn = st.connection("gsheets", type=GSheetsConnection)
try:
    df = conn.read(ttl=5)
    df = df.fillna('')
    df = df.astype(str).replace(['nan', 'NaN', 'None'], '')
    if not df.empty and 'ID' in df.columns:
        df['ID'] = df['ID'].apply(lambda x: str(int(float(x))) if x.replace('.','',1).isdigit() else x)
except Exception:
    df = pd.DataFrame()

# --- 3. 自動初始化 ---
if df is None or df.empty or len(df) == 0:
    st.warning("正在初始化 114混排盃賽程...")
    matches = []
    idx = 0
    for gn, teams in GROUPS.items():
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                t1, t2 = teams[i], teams[j]
                matches.append({
                    "ID": str(idx), "組別": gn, "對戰": f"{t1} vs {t2}",
                    "T1": t1, "T2": t2, "可用日期": get_avail(t1, t2),
                    "安排日期": "未定", "裁判": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""
                })
                idx += 1
    df = pd.DataFrame(matches)
    conn.update(data=df)
    st.cache_data.clear()
    st.success("初始化成功！請重新整理。")
    st.stop()

if '裁判' not in df.columns:
    df['裁判'] = "未定"

# --- 4. 側邊欄與動態隱藏選單 ---
st.sidebar.title("🏐 114混排盃")

# 💡 密碼移到最上面，用來控制選單顯示
admin_pw = st.sidebar.text_input("🔒 管理員登入", type="password", placeholder="一般球員請忽略")
is_admin = (admin_pw == st.secrets["manage"]["password"])
st.sidebar.divider()

# 💡 動態產生選單選項
menu_options = ["📅 賽程大日曆", "📊 積分排名", "🏆 決賽專區", "📝 更新/安排比賽"]
if is_admin:
    menu_options.insert(1, "🧑‍⚖️ 裁判班表") # 💡 只有管理員才看得到

menu = st.sidebar.radio("功能選單", menu_options)

# --- 共用邏輯函數 ---
def sort_match_ids(ids, data_df, reverse_past=False):
    today = datetime.now().strftime('%Y/%m/%d')
    future, unset, past = [], [], []
    for mid in ids:
        date_val = data_df[data_df['ID'] == str(mid)]['安排日期'].values[0]
        if date_val == "未定":
            unset.append(mid)
        else:
            clean_date = date_val.split('(')[0]
            if clean_date < today:
                past.append(mid)
            else:
                future.append(mid)
    future.sort(key=lambda x: data_df[data_df['ID'] == str(x)]['安排日期'].values[0])
    past.sort(key=lambda x: data_df[data_df['ID'] == str(x)]['安排日期'].values[0], reverse=reverse_past)
    return future + unset + past

def get_rankings(data):
    rank_list = []
    for gn, teams in GROUPS.items():
        for team in teams:
            t_m = data[(data['T1'] == team) | (data['T2'] == team)]
            wins, losses, pts = 0, 0, 0
            sets_w, sets_l = 0, 0
            pts_w, pts_l = 0, 0
            
            for _, row in t_m.iterrows():
                if row['勝隊'] == "尚未比賽" or str(row['勝隊']).strip() == "":
                    continue
                
                if row['勝隊'] == team:
                    wins += 1; pts += 2
                else:
                    losses += 1; pts += 1
                
                res = re.findall(r'\d+', str(row['局數比']))
                if len(res) == 2:
                    s1, s2 = int(res[0]), int(res[1])
                    if row['T1'] == team:
                        sets_w += s1; sets_l += s2
                    else:
                        sets_w += s2; sets_l += s1
                
                scores = str(row['詳細比分']).split('/')
                for s in scores:
                    p_res = re.findall(r'\d+', s)
                    if len(p_res) == 2:
                        p1, p2 = int(p_res[0]), int(p_res[1])
                        if row['T1'] == team:
                            pts_w += p1; pts_l += p2
                        else:
                            pts_w += p2; pts_l += p1
            
            set_ratio = sets_w / sets_l if sets_l > 0 else (float('inf') if sets_w > 0 else 0)
            pt_ratio = pts_w / pts_l if pts_l > 0 else (float('inf') if pts_w > 0 else 0)
            
            rank_list.append({
                "組別": gn, "隊伍": team, "積分": pts, "勝場": wins, "敗場": losses,
                "局數商": round(set_ratio, 3), "得分商": round(pt_ratio, 3),
                "得局": sets_w, "失局": sets_l, "得分": pts_w, "失分": pts_l
            })
            
    return pd.DataFrame(rank_list).sort_values(["組別", "積分", "局數商", "得分商"], ascending=[True, False, False, False])

def generate_calendar_events(data_df, mode="match"):
    events = []
    df_sched = data_df[data_df['安排日期'].str.contains(r'\d{4}/\d{2}/\d{2}', na=False)]
    for _, row in df_sched.iterrows():
        try:
            date_part = row['安排日期'].split('(')[0]
            date_iso = datetime.strptime(date_part, '%Y/%m/%d').strftime('%Y-%m-%d')
            if mode == "ref":
                ref = str(row.get('裁判', '未定'))
                assigned = (ref != "未定" and ref.strip() != "")
                events.append({
                    "title": f"👨‍⚖️ {ref if assigned else '缺裁判'}\n🏐 {row['對戰']}",
                    "start": date_iso, "end": date_iso,
                    "backgroundColor": "#8E24AA" if assigned else "#D32F2F"
                })
            else:
                events.append({
                    "title": f"{row['對戰']}", "start": date_iso, "end": date_iso,
                    "backgroundColor": "#1E88E5" if row['勝隊'] == "尚未比賽" else "#43A047"
                })
        except: continue
    return events

def auto_advance_finals(data):
    if not any(data['ID'] == "18"): return data 
    
    def get_res(m_id):
        idx = data[data['ID'] == str(m_id)].index
        if not idx.empty:
            row = data.loc[idx[0]]
            if row['勝隊'] not in ["尚未比賽", ""]:
                winner = row['勝隊']
                loser = row['T1'] if row['T2'] == winner else row['T2']
                return winner, loser
        return "尚未產生", "尚未產生"

    qf1_w, _ = get_res(18)
    qf2_w, _ = get_res(19)
    sf1_w, sf1_l = get_res(20)
    sf2_w, sf2_l = get_res(21)

    pairs = [("20", "T2", qf1_w, "QF1勝隊"), ("21", "T2", qf2_w, "QF2勝隊"),
             ("22", "T1", sf1_l, "SF1敗者"), ("22", "T2", sf2_l, "SF2敗者"),
             ("23", "T1", sf1_w, "SF1勝者"), ("23", "T2", sf2_w, "SF2勝者")]

    for m_id, field, val, placeholder in pairs:
        idx = data[data['ID'] == m_id].index
        if not idx.empty:
            final_val = val if val != "尚未產生" else placeholder
            data.at[idx[0], field] = final_val
            t1, t2 = data.at[idx[0], 'T1'], data.at[idx[0], 'T2']
            data.at[idx[0], '對戰'] = f"{t1} vs {t2}"
            data.at[idx[0], '可用日期'] = get_avail(t1, t2)
    return data

# --- 5. 頁面內容 ---

if menu == "📅 賽程大日曆":
    st.header("📅 賽程大日曆")
    cal_events = generate_calendar_events(df)
    calendar_options = {
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,dayGridWeek"},
        "initialView": "dayGridMonth",
        "locale": "zh-tw",
    }
    # 💡 加上 key="main_cal"
    calendar(events=cal_events, options=calendar_options, custom_css=CALENDAR_CSS, key="main_cal")
    
    st.divider()
    st.subheader("📋 詳細賽程與比分清單")
    df_sched = df[df['安排日期'] != "未定"].sort_values("安排日期")
    st.dataframe(df_sched[["安排日期", "組別", "對戰", "裁判", "局數比", "詳細比分", "勝隊"]], use_container_width=True, hide_index=True)

elif menu == "🧑‍⚖️ 裁判班表":
    st.header("🧑‍⚖️ 裁判排班日曆")
    st.info("💡 管理員截圖區：未指派裁判的場次會以紅色標示。對戰事件已強制自動折行！")
    
    if st.toggle("顯示裁判排班大日曆", value=True):
        # 💡 加上 key="ref_cal"
        calendar(events=generate_calendar_events(df, mode="ref"), options={"headerToolbar": {"left": "prev,next", "center": "title", "right": "dayGridMonth"}, "locale": "zh-tw", "height": 750, "eventDisplay": "block"}, custom_css=CALENDAR_CSS, key="ref_cal")
        
    st.divider()
    st.subheader("📋 裁判班表明細")
    st.dataframe(df[df['安排日期'] != "未定"][["安排日期", "對戰", "裁判"]].sort_values("安排日期"), use_container_width=True, hide_index=True)

elif menu == "📊 積分排名":
    st.header("📊 預賽戰績排名")
    
    rank_df = get_rankings(df)
    cols = st.columns(3)
    for idx, gn in enumerate(GROUPS.keys()):
        with cols[idx]:
            st.markdown(f"#### 🏆 {gn}")
            group_df = rank_df[rank_df['組別'] == gn][["隊伍", "積分", "勝場", "敗場", "局數商", "得分商"]].reset_index(drop=True)
            group_df.index = group_df.index + 1
            st.dataframe(group_df, use_container_width=True)
    st.divider()
    with st.expander("🔍 查看所有隊伍完整排行與細部數據 (得失局/得分)"):
        st.dataframe(rank_df, use_container_width=True, hide_index=True)

elif menu == "🏆 決賽專區":
    st.header("🏆 決賽專區")
    rank_df = get_rankings(df)
    prelims = df[pd.to_numeric(df['ID'], errors='coerce') < 18]
    prelim_done = ("尚未比賽" not in prelims['勝隊'].values) and (len(prelims) == 18)
    
    finals_df = df[pd.to_numeric(df['ID'], errors='coerce') >= 18]

    if finals_df.empty:
        if not prelim_done:
            st.info("ℹ️ 預賽尚未全部打完，晉級名單將依照以下預賽分組產生：")
            cols = st.columns(3)
            for idx, gn in enumerate(GROUPS.keys()):
                with cols[idx]:
                    top2 = rank_df[rank_df['組別'] == gn]['隊伍'].head(2).tolist()
                    st.write(f"**{gn} 領先**：\n1. {top2[0] if len(top2)>0 else ''}\n2. {top2[1] if len(top2)>1 else ''}")
        else:
            st.success("🎉 預賽已全數完賽！請管理員進行決賽抽籤並生成賽程。")
            if is_admin:
                if st.button("🎲 進行決賽抽籤並生成賽程 (各組第一名優先抽種子)", use_container_width=True):
                    first_places = [rank_df[rank_df['組別'] == gn]['隊伍'].iloc[0] for gn in GROUPS.keys()]
                    second_places = [rank_df[rank_df['組別'] == gn]['隊伍'].iloc[1] for gn in GROUPS.keys()]
                    random.shuffle(first_places)
                    seed1, seed2 = first_places[0], first_places[1]
                    qf_pool = [first_places[2]] + second_places
                    random.shuffle(qf_pool)
                    qf_team1, qf_team2, qf_team3, qf_team4 = qf_pool
                    
                    new_matches = [
                        {"ID": "18", "組別": "六強賽 (QF1)", "對戰": f"{qf_team1} vs {qf_team4}", "T1": qf_team1, "T2": qf_team4, "可用日期": get_avail(qf_team1, qf_team4), "安排日期": "未定", "裁判": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                        {"ID": "19", "組別": "六強賽 (QF2)", "對戰": f"{qf_team2} vs {qf_team3}", "T1": qf_team2, "T2": qf_team3, "可用日期": get_avail(qf_team2, qf_team3), "安排日期": "未定", "裁判": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                        {"ID": "20", "組別": "四強賽 (SF1)", "對戰": f"{seed1} vs QF1勝隊", "T1": seed1, "T2": "QF1勝隊", "可用日期": get_avail(seed1, "QF1勝隊"), "安排日期": "未定", "裁判": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                        {"ID": "21", "組別": "四強賽 (SF2)", "對戰": f"{seed2} vs QF2勝隊", "T1": seed2, "T2": "QF2勝隊", "可用日期": get_avail(seed2, "QF2勝隊"), "安排日期": "未定", "裁判": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                        {"ID": "22", "組別": "季軍戰", "對戰": "SF1敗者 vs SF2敗者", "T1": "SF1敗者", "T2": "SF2敗者", "可用日期": "需協調", "安排日期": "未定", "裁判": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                        {"ID": "23", "組別": "冠軍戰", "對戰": "SF1勝者 vs SF2勝者", "T1": "SF1勝者", "T2": "SF2勝者", "可用日期": "需協調", "安排日期": "未定", "裁判": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""}
                    ]
                    df = pd.concat([df, pd.DataFrame(new_matches)], ignore_index=True)
                    conn.update(data=df)
                    st.cache_data.clear()
                    st.rerun()

        st.divider()
        st.subheader("🔥 決賽預覽結構圖 (未抽籤)")
        placeholder_mermaid = """
        graph LR
        classDef default fill:#2b2b2b,stroke:#555,stroke-width:1px,color:#fff,rx:5px,ry:5px;
        S1["分組第一名<br>(抽籤決定種子)"] --> SF1["四強賽 (SF1)"]
        Q1["分組晉級隊伍<br>(依抽籤決定)"] --> QF1["六強賽 (QF1)"]
        Q2["分組晉級隊伍<br>(依抽籤決定)"] --> QF1
        QF1 --> SF1
        Q3["分組晉級隊伍<br>(依抽籤決定)"] --> QF2["六強賽 (QF2)"]
        Q4["分組晉級隊伍<br>(依抽籤決定)"] --> QF2
        QF2 --> SF2["四強賽 (SF2)"]
        S2["分組第一名<br>(抽籤決定種子)"] --> SF2
        SF1 --> F["🏆 冠軍賽"]
        SF2 --> F
        """
        html_ph = f"""
        <style>body {{ background-color: #0e1117; color: white; margin: 0; }}</style>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true, theme: 'dark', flowchart: {{ curve: 'stepAfter' }} }});
        </script>
        <div class="mermaid" style="display: flex; justify-content: center; align-items: center;">{placeholder_mermaid}</div>
        """
        components.html(html_ph, height=600)

    else:
        st.subheader("🔥 淘汰賽對戰圖")
        def get_node(m_id):
            m = finals_df[finals_df['ID'] == str(m_id)]
            if m.empty: return "尚未產生"
            r = m.iloc[0]
            match_name = str(r['對戰']).replace('"', "'")
            date_str = str(r['安排日期']).split('(')[0] if r['安排日期'] != "未定" else "To Be Played"
            ref_text = f"Ref: {r['裁判']}" if str(r.get('裁判', '未定')) != "未定" else ""
            winner = str(r['勝隊'])
            win_text = f"Winner: {winner}" if winner not in ["尚未比賽", ""] else ""
            info_parts = [match_name, date_str]
            if ref_text: info_parts.append(ref_text)
            if win_text: info_parts.append(win_text)
            return "<br/>".join(info_parts)

        qf1_node = get_node(18); qf2_node = get_node(19)
        sf1_node = get_node(20); sf2_node = get_node(21)
        f_node = get_node(23)

        sf1_match = finals_df[finals_df['ID'] == "20"]
        seed1 = sf1_match.iloc[0]['T1'].replace('"', "'") if not sf1_match.empty else "Seed 1"
        sf2_match = finals_df[finals_df['ID'] == "21"]
        seed2 = sf2_match.iloc[0]['T1'].replace('"', "'") if not sf2_match.empty else "Seed 2"

        mermaid_code = f"""
        graph LR
        classDef default fill:#2b2b2b,stroke:#555,stroke-width:1px,color:#fff,rx:5px,ry:5px;
        S1["{seed1}"] --> SF1["{sf1_node}"]
        QF1["{qf1_node}"] --> SF1
        QF2["{qf2_node}"] --> SF2["{sf2_node}"]
        S2["{seed2}"] --> SF2
        SF1 --> F["{f_node}"]
        SF2 --> F
        """

        html_code = f"""
        <style>body {{ background-color: #0e1117; color: white; font-family: sans-serif; margin: 0; }}</style>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true, theme: 'dark', flowchart: {{ curve: 'stepAfter' }} }});
        </script>
        <div class="mermaid" style="display: flex; justify-content: center; align-items: center;">{mermaid_code}</div>
        """
        components.html(html_code, height=600)
        
        st.divider()
        st.markdown("#### 🥉 季軍戰")
        th_m = finals_df[finals_df['ID'] == "22"]
        if not th_m.empty:
            r = th_m.iloc[0]
            th_date = str(r['安排日期']) if r['安排日期'] != "未定" else "To Be Played"
            th_ref = f"| 裁判: {r['裁判']}" if str(r.get('裁判', '未定')) != "未定" else ""
            th_win = f"| Winner: {r['勝隊']}" if r['勝隊'] not in ["尚未比賽", ""] else ""
            st.info(f"**{r['對戰']}** | 日期: {th_date} {th_ref} {th_win}")

elif menu == "📝 更新/安排比賽":
    if is_admin:
        st.header("🛠 管理員編輯面板")
        id_to_match = dict(zip(df['ID'], df['對戰']))
        tab_schedule, tab_referee, tab_score = st.tabs(["🗓️ 安排比賽日期", "👤 指派裁判", "🔢 登錄成績"])
        
        # --- 標籤 1：安排時間 ---
        with tab_schedule:
            st.markdown("#### 修改或設定比賽日期")
            if st.toggle("📅 開啟防衝堂日曆"):
                # 💡 加上 key="edit_sch_cal"
                calendar(events=generate_calendar_events(df), options={"headerToolbar": {"left": "prev,next", "center": "title", "right": "dayGridMonth"}, "locale": "zh-tw", "height": 400}, custom_css=CALENDAR_CSS, key="edit_sch_cal")
            
            mode = st.radio("賽事篩選", ["未排定", "已排定"], horizontal=True, key="sch_mode")
            ids = df[df['安排日期'] == "未定"]['ID'].tolist() if mode == "未排定" else df[df['安排日期'] != "未定"]['ID'].tolist()
            ids.sort(key=int)
            
            if ids:
                mid = st.selectbox("選擇比賽", options=ids, format_func=lambda x: f"[{df[df['ID']==str(x)]['組別'].values[0]}] {id_to_match[str(x)]}")
                idx = df[df['ID'] == mid].index[0]; row = df.iloc[idx]
                st.info(f"建議可用：{row['可用日期']}")
                
                t1, t2 = row['T1'], row['T2']
                other_matches = df[(df['安排日期'] != "未定") & (df['ID'] != mid)]
                conflict_matches = other_matches[(other_matches['T1'] == t1) | (other_matches['T2'] == t1) | 
                                                 (other_matches['T1'] == t2) | (other_matches['T2'] == t2)]
                occupied_dates_clean = []
                if not conflict_matches.empty:
                    conflict_msgs = []
                    for _, r in conflict_matches.iterrows():
                        date_clean = r['安排日期'].split('(')[0]
                        occupied_dates_clean.append(date_clean)
                        conflict_msgs.append(f"- **{r['安排日期']}** ({r['對戰']})")
                    st.error("🚨 **防衝堂警報：這兩支隊伍在以下日期已有比賽！**\n" + "\n".join(conflict_msgs))

                with st.form("f_sch"):
                    d = st.date_input("選擇新日期", value=None)
                    if st.form_submit_button("💾 儲存日期"):
                        if d:
                            date_str_iso = d.strftime('%Y/%m/%d')
                            if date_str_iso in occupied_dates_clean:
                                st.error(f"❌ 儲存失敗：{date_str_iso} 當天兩隊中已有隊伍要出賽，請選擇其他日期！")
                            else:
                                w_day = ["週一","週二","週三","週四","週五","週六","週日"][d.weekday()]
                                df.at[idx, '安排日期'] = f"{date_str_iso}({w_day})"
                                conn.update(data=df); st.cache_data.clear(); st.rerun()

        # --- 標籤 2：指派裁判 ---
        with tab_referee:
            st.markdown("#### 指派比賽裁判")
            st.write("📅 **當前裁判排班狀況：**")
            if st.toggle("顯示裁判排班小日曆", value=True):
                # 💡 加上 key="edit_ref_cal"
                calendar(events=generate_calendar_events(df, mode="ref"), options={"headerToolbar": {"left": "prev,next", "center": "title", "right": "dayGridMonth"}, "locale": "zh-tw", "height": 400}, custom_css=CALENDAR_CSS, key="edit_ref_cal")
            st.divider()
            
            ref_ids = df[df['安排日期'] != "未定"]['ID'].tolist()
            ref_ids = sort_match_ids(ref_ids, df) 
            
            if not ref_ids:
                st.warning("⚠️ 請先在左側標籤安排好比賽日期。")
            else:
                mid = st.selectbox("選擇要指派裁判的比賽 (按時間排序)", options=ref_ids, 
                                   format_func=lambda x: f"[{df[df['ID']==str(x)]['安排日期'].values[0]}] {id_to_match[str(x)]} (目前: {df[df['ID']==str(x)]['裁判'].values[0]})")
                idx = df[df['ID'] == mid].index[0]
                with st.form("f_ref"):
                    new_ref = st.text_input("👤 裁判姓名", value="" if df.at[idx, '裁判'] == "未定" else df.at[idx, '裁判'])
                    if st.form_submit_button("💾 儲存裁判"):
                        df.at[idx, '裁判'] = new_ref if new_ref.strip() else "未定"
                        conn.update(data=df); st.cache_data.clear(); st.rerun()

        # --- 標籤 3：登錄成績 ---
        with tab_score:
            st.markdown("#### 登錄或修改比分")
            score_status = st.radio("篩選狀態", ["尚未完賽", "已完賽"], horizontal=True, key="scr_status")
            s_ids = df[df['勝隊'] == "尚未比賽"]['ID'].tolist() if score_status == "尚未完賽" else df[df['勝隊'] != "尚未比賽"]['ID'].tolist()
            
            s_ids = sort_match_ids(s_ids, df, reverse_past=(score_status == "已完賽"))
            
            if s_ids:
                mid = st.selectbox("選擇比賽 (按時間排序)", options=s_ids, 
                                   format_func=lambda x: f"[{df[df['ID']==str(x)]['安排日期'].values[0]}] {id_to_match[str(x)]}")
                idx = df[df['ID'] == mid].index[0]; row = df.iloc[idx]
                with st.form("f_score"):
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        sc = st.text_input("局數比", value=row['局數比'])
                        ov = st.selectbox("勝負判定", ["🤖 自動", "尚未比賽", row['T1'], row['T2']])
                    with col2:
                        st.write("詳細比分")
                        c1, c2, c3 = st.columns(3)
                        det = row['詳細比分'].split(" / ") if row['詳細比分'] else ["","",""]
                        while len(det) < 3: det.append("")
                        s1, s2, s3 = c1.text_input("1", value=det[0]), c2.text_input("2", value=det[1]), c3.text_input("3", value=det[2])
                    if st.form_submit_button("💾 儲存成績"):
                        df.at[idx, '局數比'] = sc
                        df.at[idx, '詳細比分'] = " / ".join([s for s in [s1, s2, s3] if s.strip()])
                        if ov == "🤖 自動":
                            nums = re.findall(r'\d+', sc)
                            if len(nums) == 2 and int(nums[0])+int(nums[1]) > 0: df.at[idx, '勝隊'] = row['T1'] if int(nums[0]) > int(nums[1]) else row['T2']
                        else: df.at[idx, '勝隊'] = ov
                        df = auto_advance_finals(df); conn.update(data=df); st.cache_data.clear(); st.rerun()

    else:
        st.error("🔒 這是專屬管理員的功能，一般球員請看其他頁面喔！")