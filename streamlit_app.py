import streamlit as st
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection
from streamlit_calendar import calendar
import pandas as pd
import re
import random
from datetime import datetime

st.set_page_config(page_title="12隊混排盃賽事網", layout="wide")

# --- 1. 基礎設定與可用日期 (已更新法律系限制) ---
GROUPS = {
    "第 1 組": ["土木B", "園藝系", "化工", "工海"],
    "第 2 組": ["生工/農經聯隊", "化學系+化學所", "會計", "藥學系"],
    "第 3 組": ["土木", "機械系", "森林系", "法律系"]
}

CONSTRAINTS = {
    "森林系": [4, 2], "土木B": [4, 2], "土木": [2, 4],
    "生工/農經聯隊": [1, 4], "園藝系": [3, 4], "藥學系": [4, 2],
    "工海": [4, 5], "化學系+化學所": [3, 1], "機械系": [4, 1],
    "會計": [2, 5], "化工": [3, 2],
    "法律系": [4, 2]  # 💡 已更新：週四、週二不便
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

# --- 3. 自動初始化 (18場預賽) ---
if df is None or df.empty or len(df) == 0:
    st.warning("正在初始化 12 隊賽程...")
    matches = []
    idx = 0
    for gn, teams in GROUPS.items():
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                t1, t2 = teams[i], teams[j]
                matches.append({
                    "ID": str(idx), "組別": gn, "對戰": f"{t1} vs {t2}",
                    "T1": t1, "T2": t2, "可用日期": get_avail(t1, t2),
                    "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""
                })
                idx += 1
    df = pd.DataFrame(matches)
    conn.update(data=df)
    st.cache_data.clear()
    st.rerun()

# --- 4. 側邊欄 ---
st.sidebar.title("🏐 12隊混排盃")
menu = st.sidebar.radio("功能選單", ["📅 賽程大日曆", "📊 積分排名", "🏆 決賽專區", "📝 更新/安排比賽"])
st.sidebar.divider()
admin_pw = st.sidebar.text_input("🔒 管理員登入", type="password")
is_admin = (admin_pw == st.secrets["manage"]["password"])

# --- 邏輯函數 ---
def get_rankings(data):
    rank_list = []
    for gn, teams in GROUPS.items():
        for team in teams:
            t_m = data[(data['T1'] == team) | (data['T2'] == team)]
            wins = len(t_m[t_m['勝隊'] == team])
            pts = 0
            for _, row in t_m.iterrows():
                if row['勝隊'] == "尚未比賽": continue
                res = re.findall(r'\d+', str(row['局數比']))
                if len(res) == 2:
                    s1, s2 = int(res[0]), int(res[1])
                    if row['T1'] == team:
                        if s1==2 and s2==0: pts+=3
                        elif s1==2 and s2==1: pts+=2
                        elif s1==1 and s2==2: pts+=1
                    else:
                        if s2==2 and s1==0: pts+=3
                        elif s2==2 and s1==1: pts+=2
                        elif s2==1 and s1==2: pts+=1
            rank_list.append({"組別": gn, "隊伍": team, "勝場": wins, "積分": pts})
    return pd.DataFrame(rank_list).sort_values(["組別", "積分"], ascending=[True, False])

def generate_calendar_events(data_df):
    events = []
    df_sched = data_df[data_df['安排日期'].str.contains(r'\d{4}/\d{2}/\d{2}', na=False)]
    for _, row in df_sched.iterrows():
        try:
            d_part = row['安排日期'].split('(')[0]
            d_iso = datetime.strptime(d_part, '%Y/%m/%d').strftime('%Y-%m-%d')
            events.append({"title": f"{row['對戰']}", "start": d_iso, "end": d_iso, "backgroundColor": "#1E88E5" if row['勝隊'] == "尚未比賽" else "#43A047"})
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
    
    q1w, _ = get_res(18); q2w, _ = get_res(19)
    s1w, s1l = get_res(20); s2w, s2l = get_res(21)
    
    mapping = [("20", "T2", q1w, "QF1勝隊"), ("21", "T2", q2w, "QF2勝隊"),
               ("22", "T1", s1l, "SF1敗者"), ("22", "T2", s2l, "SF2敗者"),
               ("23", "T1", s1w, "SF1勝者"), ("23", "T2", s2w, "SF2勝者")]
    
    for mid, field, val, ph in mapping:
        idx = data[data['ID'] == mid].index
        if not idx.empty:
            final_v = val if val != "尚未產生" else ph
            data.at[idx[0], field] = final_v
            t1, t2 = data.at[idx[0], 'T1'], data.at[idx[0], 'T2']
            data.at[idx[0], '對戰'] = f"{t1} vs {t2}"
            data.at[idx[0], '可用日期'] = get_avail(t1, t2)
    return data

# --- 5. 頁面功能 ---
if menu == "📅 賽程大日曆":
    st.header("📅 賽程大日曆")
    calendar(events=generate_calendar_events(df), options={"headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"}, "locale": "zh-tw"})
    st.divider()
    st.dataframe(df[df['安排日期'] != "未定"].sort_values("安排日期"), use_container_width=True, hide_index=True)

elif menu == "📊 積分排名":
    st.header("📊 預賽戰績排名")
    rank_df = get_rankings(df)
    cols = st.columns(3)
    for i, gn in enumerate(GROUPS.keys()):
        with cols[i]:
            st.markdown(f"#### 🏆 {gn}")
            st.dataframe(rank_df[rank_df['組別'] == gn][["隊伍", "勝場", "積分"]].reset_index(drop=True), use_container_width=True)

elif menu == "🏆 決賽專區":
    st.header("🏆 決賽專區")
    rank_df = get_rankings(df)
    prelims = df[pd.to_numeric(df['ID'], errors='coerce') < 18]
    if ("尚未比賽" in prelims['勝隊'].values) or (len(prelims) < 18):
        st.info("預賽尚未完賽")
    else:
        finals_df = df[pd.to_numeric(df['ID'], errors='coerce') >= 18]
        if finals_df.empty:
            if is_admin and st.button("🎲 進行決賽抽籤"):
                f1 = [rank_df[rank_df['組別'] == gn]['隊伍'].iloc[0] for gn in GROUPS.keys()]
                f2 = [rank_df[rank_df['組別'] == gn]['隊伍'].iloc[1] for gn in GROUPS.keys()]
                random.shuffle(f1); seed1, seed2 = f1[0], f1[1]
                q_pool = [f1[2]] + f2; random.shuffle(q_pool)
                new = [
                    {"ID": "18", "組別": "六強賽 (QF1)", "對戰": f"{q_pool[0]} vs {q_pool[3]}", "T1": q_pool[0], "T2": q_pool[3], "可用日期": get_avail(q_pool[0], q_pool[3]), "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                    {"ID": "19", "組別": "六強賽 (QF2)", "對戰": f"{q_pool[1]} vs {q_pool[2]}", "T1": q_pool[1], "T2": q_pool[2], "可用日期": get_avail(q_pool[1], q_pool[2]), "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                    {"ID": "20", "組別": "四強賽 (SF1)", "對戰": f"{seed1} vs QF1勝隊", "T1": seed1, "T2": "QF1勝隊", "可用日期": get_avail(seed1, "QF1勝隊"), "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                    {"ID": "21", "組別": "四強賽 (SF2)", "對戰": f"{seed2} vs QF2勝隊", "T1": seed2, "T2": "QF2勝隊", "可用日期": get_avail(seed2, "QF2勝隊"), "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                    {"ID": "22", "組別": "季軍戰", "對戰": "SF1敗者 vs SF2敗者", "T1": "SF1敗者", "T2": "SF2敗者", "可用日期": "需協調", "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                    {"ID": "23", "組別": "冠軍戰", "對戰": "SF1勝者 vs SF2勝者", "T1": "SF1勝者", "T2": "SF2勝者", "可用日期": "需協調", "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""}
                ]
                df = pd.concat([df, pd.DataFrame(new)], ignore_index=True)
                conn.update(data=df); st.cache_data.clear(); st.rerun()
        else:
            def g_node(mid):
                r = df[df['ID'] == str(mid)].iloc[0]
                d = r['安排日期'].split('(')[0] if r['安排日期'] != "未定" else "To Be Played"
                w = f"Winner: {r['勝隊']}" if r['勝隊'] != "尚未比賽" else ""
                return f"{r['對戰']}<br/>{d}<br/>{w}"
            m_code = f"graph LR\nS1['{df[df['ID']=='20'].iloc[0]['T1']}'] --> SF1['{g_node(20)}']\nQF1['{g_node(18)}'] --> SF1\nQF2['{g_node(19)}'] --> SF2['{g_node(21)}']\nS2['{df[df['ID']=='21'].iloc[0]['T1']}'] --> SF2\nSF1 --> F['{g_node(23)}']\nSF2 --> F"
            components.html(f"<script type='module'>import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';mermaid.initialize({{startOnLoad:true,theme:'dark',flowchart:{{curve:'stepAfter'}}}});</script><div class='mermaid' style='display:flex;justify-content:center;'>{m_code}</div>", height=450)

elif menu == "📝 更新/安排比賽":
    if is_admin:
        id_map = dict(zip(df['ID'], df['對戰']))
        t_sch, t_scr = st.tabs(["🗓️ 安排時間", "🔢 登錄成績"])
        with t_sch:
            if st.toggle("顯示防衝堂日曆"):
                calendar(events=generate_calendar_events(df), options={"headerToolbar": {"left": "prev,next", "center": "title", "right": "dayGridMonth"}, "locale": "zh-tw", "height": 400})
            st.divider()
            mode = st.radio("篩選", ["未排定", "已排定"], horizontal=True)
            target = df[df['安排日期'] == "未定"]['ID'].tolist() if mode == "未排定" else df[df['安排日期'] != "未定"]['ID'].tolist()
            if target:
                mid = st.selectbox("選擇比賽", options=target, format_func=lambda x: f"[{df[df['ID']==str(x)]['組別'].values[0]}] {id_map[str(x)]}")
                idx = df[df['ID'] == mid].index[0]; row = df.iloc[idx]
                st.info(f"建議可用：{row['可用日期']}")
                # 衝堂警告
                other = df[(df['安排日期'] != "未定") & (df['ID'] != mid)]
                conflict = other[(other['T1'] == row['T1']) | (other['T2'] == row['T1']) | (other['T1'] == row['T2']) | (other['T2'] == row['T2'])]
                occ_dates = []
                if not conflict.empty:
                    st.error("🚨 衝堂警報：\n" + "\n".join([f"- {r['安排日期']} ({r['對戰']})" for _, r in conflict.iterrows()]))
                    occ_dates = [r['安排日期'].split('(')[0] for _, r in conflict.iterrows()]
                with st.form("f_sch"):
                    new_d = st.date_input("選擇日期", value=None)
                    if st.form_submit_button("儲存"):
                        if new_d:
                            d_str = new_d.strftime('%Y/%m/%d')
                            if d_str in occ_dates: st.error("日期衝堂！")
                            else:
                                df.at[idx, '安排日期'] = f"{d_str}({['週一','週二','週三','週四','週五','週六','週日'][new_d.weekday()]})"
                                conn.update(data=df); st.cache_data.clear(); st.rerun()
        with t_scr:
            mode = st.radio("篩選", ["未完賽", "已完賽"], horizontal=True, key="scr_m")
            target = df[df['勝隊'] == "尚未比賽"]['ID'].tolist() if mode == "未完賽" else df[df['勝隊'] != "尚未比賽"]['ID'].tolist()
            if target:
                mid = st.selectbox("選擇比賽", options=target, format_func=lambda x: id_map[str(x)], key="scr_sel")
                idx = df[df['ID'] == mid].index[0]; row = df.iloc[idx]
                with st.form("f_scr"):
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        sc = st.text_input("局數比", value=row['局數比'])
                        ov = st.selectbox("勝負判定", ["🤖 自動", "尚未比賽", row['T1'], row['T2']])
                    with col2:
                        st.write("詳細比分")
                        c1, c2, c3 = st.columns(3)
                        cur_det = row['詳細比分'].split(" / ") if row['詳細比分'] else ["","",""]
                        while len(cur_det) < 3: cur_det.append("")
                        s1, s2, s3 = c1.text_input("1", value=cur_det[0]), c2.text_input("2", value=cur_det[1]), c3.text_input("3", value=cur_det[2])
                    if st.form_submit_button("儲存成績"):
                        df.at[idx, '局數比'] = sc
                        df.at[idx, '詳細比分'] = " / ".join([s for s in [s1, s2, s3] if s.strip()])
                        if ov == "🤖 自動":
                            nums = re.findall(r'\d+', sc)
                            if len(nums) == 2 and int(nums[0])+int(nums[1]) > 0: df.at[idx, '勝隊'] = row['T1'] if int(nums[0]) > int(nums[1]) else row['T2']
                        else: df.at[idx, '勝隊'] = ov
                        df = auto_advance_finals(df); conn.update(data=df); st.cache_data.clear(); st.rerun()
    else: st.error("🔒 管理員登入以編輯")