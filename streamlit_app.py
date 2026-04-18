import streamlit as st
import streamlit.components.v1 as components 
from streamlit_gsheets import GSheetsConnection
from streamlit_calendar import calendar
import pandas as pd
import re
import random
from datetime import datetime

st.set_page_config(page_title="11隊混排盃賽事網", layout="wide")

# --- 1. 基礎設定與可用日期 ---
GROUPS = {
    "第 1 組": ["土木B", "園藝系", "化工", "工海"],
    "第 2 組": ["生工/農經聯隊", "化學系+化學所", "會計", "藥學系"],
    "第 3 組": ["土木", "機械系", "森林系"]
}

CONSTRAINTS = {
    "森林系": [4, 2], "土木B": [4, 2], "土木": [2, 4],
    "生工/農經聯隊": [1, 4], "園藝系": [3, 4], "藥學系": [4, 2],
    "工海": [4, 5], "化學系+化學所": [3, 1], "機械系": [4, 1],
    "會計": [2, 5], "化工": [3, 2]
}

def get_avail(t1, t2):
    all_days = [1, 2, 3, 4, 5]
    forbidden = set(CONSTRAINTS.get(t1, []) + CONSTRAINTS.get(t2, []))
    avail = [f"週{['0','一','二','三','四','五'][d]}" for d in all_days if d not in forbidden]
    return "、".join(avail) if avail else "需協調"

# --- 2. 讀取資料與清洗 ---
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
    st.warning("正在初始化雲端賽程...")
    matches = []
    idx = 0
    for gn, GROUPS_teams in GROUPS.items():
        for i in range(len(GROUPS_teams)):
            for j in range(i + 1, len(GROUPS_teams)):
                t1, t2 = GROUPS_teams[i], GROUPS_teams[j]
                matches.append({
                    "ID": str(idx), "組別": gn, "對戰": f"{t1} vs {t2}",
                    "T1": t1, "T2": t2, "可用日期": get_avail(t1, t2),
                    "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""
                })
                idx += 1
    df = pd.DataFrame(matches)
    conn.update(data=df)
    st.cache_data.clear()
    st.success("初始化成功！請重新整理。")
    st.stop()

# --- 4. 側邊欄與選單 ---
st.sidebar.title("🏐 11隊混排盃")
menu = st.sidebar.radio("功能選單", ["📅 賽程大日曆", "📊 積分排名", "🏆 決賽專區", "📝 更新/安排比賽"])

st.sidebar.divider()
admin_pw = st.sidebar.text_input("🔒 管理員登入", type="password", placeholder="一般球員請忽略")
is_admin = (admin_pw == st.secrets["manage"]["password"])

# --- 共用函數 ---
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
                        if s1 == 2 and s2 == 0: pts += 3
                        elif s1 == 2 and s2 == 1: pts += 2
                        elif s1 == 1 and s2 == 2: pts += 1
                    else:
                        if s2 == 2 and s1 == 0: pts += 3
                        elif s2 == 2 and s1 == 1: pts += 2
                        elif s2 == 1 and s1 == 2: pts += 1
            rank_list.append({"組別": gn, "隊伍": team, "勝場": wins, "積分": pts})
    return pd.DataFrame(rank_list).sort_values(["組別", "積分"], ascending=[True, False])

def generate_calendar_events(data_df):
    events = []
    df_sched = data_df[data_df['安排日期'].str.contains(r'\d{4}/\d{2}/\d{2}', na=False)]
    for _, row in df_sched.iterrows():
        try:
            date_part = row['安排日期'].split('(')[0]
            date_iso = datetime.strptime(date_part, '%Y/%m/%d').strftime('%Y-%m-%d')
            events.append({
                "title": f"{row['對戰']}",
                "start": date_iso,
                "end": date_iso,
                "backgroundColor": "#1E88E5" if row['勝隊'] == "尚未比賽" else "#43A047"
            })
        except: continue
    return events

# 💡 更新：讓全自動推進引擎順便計算「可用日期」
def auto_advance_finals(data):
    if not any(data['ID'] == "15"): return data
    
    def get_res(m_id):
        idx = data[data['ID'] == str(m_id)].index
        if not idx.empty:
            row = data.loc[idx[0]]
            if row['勝隊'] not in ["尚未比賽", ""]:
                winner = row['勝隊']
                loser = row['T1'] if row['T2'] == winner else row['T2']
                return winner, loser
        return "尚未產生", "尚未產生"

    qf1_w, _ = get_res(15)
    qf2_w, _ = get_res(16)
    sf1_w, sf1_l = get_res(17)
    sf2_w, sf2_l = get_res(18)

    i17 = data[data['ID'] == "17"].index
    if not i17.empty:
        t1 = data.at[i17[0], 'T1']
        t2 = qf1_w if qf1_w != "尚未產生" else "QF1勝隊"
        data.at[i17[0], 'T2'] = t2
        data.at[i17[0], '對戰'] = f"{t1} vs {t2}"
        data.at[i17[0], '可用日期'] = get_avail(t1, t2)

    i18 = data[data['ID'] == "18"].index
    if not i18.empty:
        t1 = data.at[i18[0], 'T1']
        t2 = qf2_w if qf2_w != "尚未產生" else "QF2勝隊"
        data.at[i18[0], 'T2'] = t2
        data.at[i18[0], '對戰'] = f"{t1} vs {t2}"
        data.at[i18[0], '可用日期'] = get_avail(t1, t2)

    i19 = data[data['ID'] == "19"].index
    if not i19.empty:
        t1 = sf1_l if sf1_l != "尚未產生" else "SF1敗者"
        t2 = sf2_l if sf2_l != "尚未產生" else "SF2敗者"
        data.at[i19[0], 'T1'] = t1
        data.at[i19[0], 'T2'] = t2
        data.at[i19[0], '對戰'] = f"{t1} vs {t2}"
        data.at[i19[0], '可用日期'] = get_avail(t1, t2)

    i20 = data[data['ID'] == "20"].index
    if not i20.empty:
        t1 = sf1_w if sf1_w != "尚未產生" else "SF1勝者"
        t2 = sf2_w if sf2_w != "尚未產生" else "SF2勝者"
        data.at[i20[0], 'T1'] = t1
        data.at[i20[0], 'T2'] = t2
        data.at[i20[0], '對戰'] = f"{t1} vs {t2}"
        data.at[i20[0], '可用日期'] = get_avail(t1, t2)

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
    calendar(events=cal_events, options=calendar_options)
    
    st.divider()
    st.subheader("📋 詳細賽程與比分清單")
    df_sched = df[df['安排日期'] != "未定"].sort_values("安排日期")
    st.dataframe(df_sched[["安排日期", "組別", "對戰", "局數比", "詳細比分", "勝隊"]], use_container_width=True, hide_index=True)

elif menu == "📊 積分排名":
    st.header("📊 預賽戰績排名")
    rank_df = get_rankings(df)
    
    cols = st.columns(3)
    for idx, gn in enumerate(GROUPS.keys()):
        with cols[idx]:
            st.markdown(f"#### 🏆 {gn}")
            group_df = rank_df[rank_df['組別'] == gn][["隊伍", "勝場", "積分"]].reset_index(drop=True)
            group_df.index = group_df.index + 1
            st.dataframe(group_df, use_container_width=True)
            
    st.divider()
    with st.expander("🔍 查看所有隊伍完整排行"):
        st.dataframe(rank_df, use_container_width=True, hide_index=True)

elif menu == "🏆 決賽專區":
    st.header("🏆 決賽專區")
    rank_df = get_rankings(df)
    prelims = df[pd.to_numeric(df['ID'], errors='coerce') < 15]
    prelim_done = ("尚未比賽" not in prelims['勝隊'].values) and (len(prelims) == 15)
    
    if not prelim_done:
        st.info("ℹ️ 預賽尚未全部打完，決賽名單稍後公佈！")
        cols = st.columns(3)
        for idx, gn in enumerate(GROUPS.keys()):
            with cols[idx]:
                top2 = rank_df[rank_df['組別'] == gn]['隊伍'].head(2).tolist()
                st.write(f"**{gn} 領先**：\n1. {top2[0] if len(top2)>0 else ''}\n2. {top2[1] if len(top2)>1 else ''}")
    else:
        first_places = []
        second_places = []
        
        cols = st.columns(3)
        for idx, gn in enumerate(GROUPS.keys()):
            with cols[idx]:
                top2 = rank_df[rank_df['組別'] == gn]['隊伍'].head(2).tolist()
                if len(top2) > 0: first_places.append(top2[0])
                if len(top2) > 1: second_places.append(top2[1])
                st.write(f"**{gn} 晉級**：\n1. {top2[0]}\n2. {top2[1]}")
                
        st.divider()
        
        finals_df = df[pd.to_numeric(df['ID'], errors='coerce') >= 15]
        
        if finals_df.empty:
            st.warning("⚠️ 淘汰賽賽程尚未生成。")
            if is_admin:
                if st.button("🎲 進行決賽抽籤並生成賽程 (各組第一名優先抽種子)", use_container_width=True):
                    random.shuffle(first_places)
                    seed1 = first_places[0]
                    seed2 = first_places[1]
                    
                    qf_pool = [first_places[2]] + second_places
                    random.shuffle(qf_pool)
                    qf_team1, qf_team2, qf_team3, qf_team4 = qf_pool
                    
                    # 💡 更新：抽籤時直接代入正確的可用日期函數
                    new_matches = [
                        {"ID": "15", "組別": "六強賽 (QF1)", "對戰": f"{qf_team1} vs {qf_team4}", "T1": qf_team1, "T2": qf_team4, "可用日期": get_avail(qf_team1, qf_team4), "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                        {"ID": "16", "組別": "六強賽 (QF2)", "對戰": f"{qf_team2} vs {qf_team3}", "T1": qf_team2, "T2": qf_team3, "可用日期": get_avail(qf_team2, qf_team3), "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                        {"ID": "17", "組別": "四強賽 (SF1)", "對戰": f"{seed1} vs QF1勝隊", "T1": seed1, "T2": "QF1勝隊", "可用日期": get_avail(seed1, "QF1勝隊"), "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                        {"ID": "18", "組別": "四強賽 (SF2)", "對戰": f"{seed2} vs QF2勝隊", "T1": seed2, "T2": "QF2勝隊", "可用日期": get_avail(seed2, "QF2勝隊"), "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                        {"ID": "19", "組別": "季軍戰", "對戰": "SF1敗者 vs SF2敗者", "T1": "SF1敗者", "T2": "SF2敗者", "可用日期": get_avail("SF1敗者", "SF2敗者"), "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""},
                        {"ID": "20", "組別": "冠軍戰", "對戰": "SF1勝者 vs SF2勝者", "T1": "SF1勝者", "T2": "SF2勝者", "可用日期": get_avail("SF1勝者", "SF2勝者"), "安排日期": "未定", "局數比": "0:0", "勝隊": "尚未比賽", "詳細比分": ""}
                    ]
                    
                    df = pd.concat([df, pd.DataFrame(new_matches)], ignore_index=True)
                    conn.update(data=df)
                    st.cache_data.clear()
                    st.success("✅ 決賽賽程已生成完畢！請至管理員面板排定時間。")
                    st.rerun()
            else:
                st.info("請等待管理員進行抽籤與賽程排定。")
        else:
            st.subheader("🔥 淘汰賽對戰樹狀圖")
            
            def get_f_match(m_id):
                m = finals_df[finals_df['ID'] == str(m_id)]
                if m.empty: return "尚未產生", "尚未產生", "0:0", "尚未產生"
                r = m.iloc[0]
                match_name = str(r['對戰']).replace('"', "'")
                date_str = str(r['安排日期']).split('(')[0] if r['安排日期'] != "未定" else "To Be Played"
                winner = str(r['勝隊'])
                win_text = f"Winner: {winner}" if winner not in ["尚未比賽", ""] else ""
                return f"{match_name}<br/>{date_str}<br/>{win_text}"

            qf1_node = get_f_match(15)
            qf2_node = get_f_match(16)
            sf1_node = get_f_match(17)
            sf2_node = get_f_match(18)
            f_node = get_f_match(20)

            sf1_match = finals_df[finals_df['ID'] == "17"]
            seed1 = sf1_match.iloc[0]['T1'].replace('"', "'") if not sf1_match.empty else "Seed 1"

            sf2_match = finals_df[finals_df['ID'] == "18"]
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
            <style>
                body {{ background-color: #0e1117; color: white; font-family: sans-serif; margin: 0; }}
            </style>
            <script type="module">
                import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
                mermaid.initialize({{ 
                    startOnLoad: true, 
                    theme: 'dark',
                    flowchart: {{ curve: 'stepAfter' }}
                }});
            </script>
            <div class="mermaid" style="display: flex; justify-content: center; align-items: center;">
                {mermaid_code}
            </div>
            """
            
            components.html(html_code, height=450)
            
            st.divider()
            st.markdown("#### 🥉 季軍戰")
            th_m = finals_df[finals_df['ID'] == "19"]
            if not th_m.empty:
                r = th_m.iloc[0]
                th_date = str(r['安排日期']) if r['安排日期'] != "未定" else "To Be Played"
                th_win = f"Winner: {r['勝隊']}" if r['勝隊'] not in ["尚未比賽", ""] else ""
                st.info(f"**{r['對戰']}** | 日期: {th_date} | {th_win}")

elif menu == "📝 更新/安排比賽":
    if is_admin:
        st.header("🛠 管理員編輯面板")
        id_to_match = dict(zip(df['ID'], df['對戰']))
        tab_schedule, tab_score = st.tabs(["🗓️ 安排比賽時間", "🔢 登錄比賽成績"])
        
        # ==========================================
        # 標籤頁 1：安排比賽時間
        # ==========================================
        with tab_schedule:
            st.markdown("#### 第一步：確認日曆避免衝堂")
            if st.toggle("📅 顯示防衝堂排程日曆"):
                admin_events = generate_calendar_events(df)
                admin_cal_opts = {
                    "headerToolbar": {"left": "prev,next", "center": "title", "right": "dayGridMonth"},
                    "initialView": "dayGridMonth",
                    "locale": "zh-tw",
                    "height": 450
                }
                calendar(events=admin_events, options=admin_cal_opts)
            
            st.divider()
            st.markdown("#### 第二步：安排或修改日期")
            
            sched_status = st.radio("篩選賽事狀態", ["🚩 未排定日期 (需安排)", "✅ 已排定日期 (需修改)"], horizontal=True)
            if "未排定" in sched_status:
                target_ids = df[df['安排日期'] == "未定"]['ID'].tolist()
            else:
                target_ids = df[df['安排日期'] != "未定"]['ID'].tolist()
                
            if not target_ids:
                st.success("🎉 此分類目前沒有比賽。")
            else:
                def format_sched_disp(x):
                    name = id_to_match.get(str(x), '未知對戰')
                    grp = df[df['ID'] == str(x)]['組別'].values[0]
                    date_str = df[df['ID'] == str(x)]['安排日期'].values[0]
                    disp = f"[{grp}] {name}"
                    if date_str != "未定":
                        return f"{disp} 👉 (排定於: {date_str})"
                    return disp

                m_id_sched = st.selectbox("選擇要處理的比賽", options=target_ids, format_func=format_sched_disp, key="sel_sched")
                row_idx_sched = df[df['ID'] == m_id_sched].index[0]
                curr_sched = df.iloc[row_idx_sched]
                
                st.info(f"建議可用日期：**{curr_sched['可用日期']}**")
                
                t1, t2 = curr_sched['T1'], curr_sched['T2']
                other_matches = df[(df['安排日期'] != "未定") & (df['ID'] != m_id_sched)]
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
                
                with st.form("form_schedule"):
                    new_date = st.date_input("🗓️ 選擇新的比賽日期", value=None)
                    sub_sched = st.form_submit_button("💾 儲存日期至雲端")
                    
                    if sub_sched:
                        if new_date:
                            date_str_iso = new_date.strftime('%Y/%m/%d')
                            if date_str_iso in occupied_dates_clean:
                                st.error(f"❌ 儲存失敗：{date_str_iso} 當天兩隊中已有隊伍要出賽，請選擇其他日期！")
                            else:
                                w_day = ["週一","週二","週三","週四","週五","週六","週日"][new_date.weekday()]
                                df.at[row_idx_sched, '安排日期'] = f"{date_str_iso}({w_day})"
                                conn.update(data=df)
                                st.cache_data.clear()
                                st.success("✅ 日期已成功更新！")
                                st.rerun()
                        else:
                            st.warning("請先選擇一個日期喔！")

        # ==========================================
        # 標籤頁 2：登錄比賽成績
        # ==========================================
        with tab_score:
            st.markdown("#### 記錄或修改比分")
            
            score_status = st.radio("篩選成績狀態", ["🚩 尚未比賽 (需登錄)", "✅ 已完賽 (需修改)"], horizontal=True)
            if "尚未" in score_status:
                target_score_ids = df[df['勝隊'] == "尚未比賽"]['ID'].tolist()
            else:
                target_score_ids = df[df['勝隊'] != "尚未比賽"]['ID'].tolist()
                
            if not target_score_ids:
                st.success("🎉 此分類目前沒有比賽。")
            else:
                def format_score_disp(x):
                    name = id_to_match.get(str(x), '未知對戰')
                    grp = df[df['ID'] == str(x)]['組別'].values[0]
                    date_str = df[df['ID'] == str(x)]['安排日期'].values[0]
                    disp = f"[{grp}] {name}"
                    return f"{disp} ({date_str})" if date_str != "未定" else disp

                m_id_score = st.selectbox("選擇要記錄成績的比賽", options=target_score_ids, format_func=format_score_disp, key="sel_score")
                row_idx_score = df[df['ID'] == m_id_score].index[0]
                curr_score = df.iloc[row_idx_score]
                
                s_val = str(curr_score['局數比']) if str(curr_score['局數比']).lower() not in ['nan', ''] else "0:0"
                d_val = str(curr_score['詳細比分']) if str(curr_score['詳細比分']).lower() not in ['nan', ''] else ""
                
                st.info(f"目前局數比：**{s_val}**")
                
                with st.form("form_score"):
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        score = st.text_input("🔢 總局數比 (例 2:1)", value=s_val)
                        st.write("---")
                        win_options = ["🤖 自動根據比分計算", "尚未比賽", curr_score['T1'], curr_score['T2']]
                        
                        curr_win = str(curr_score['勝隊'])
                        def_idx = win_options.index(curr_win) if curr_win in win_options and curr_win != "尚未比賽" else 0
                        override_winner = st.selectbox("🏆 勝負判定", win_options, index=def_idx)
                    
                    with col2:
                        st.write("📝 詳細各局比分 (選填)：")
                        s_col1, s_col2, s_col3 = st.columns(3)
                        existing_sets = d_val.split(" / ") if d_val else []
                        while len(existing_sets) < 3: existing_sets.append("")
                        
                        set1 = s_col1.text_input("第一局", value=existing_sets[0], placeholder="25:20")
                        set2 = s_col2.text_input("第二局", value=existing_sets[1], placeholder="21:25")
                        set3 = s_col3.text_input("第三局", value=existing_sets[2], placeholder="15:10")
                    
                    sub_score = st.form_submit_button("💾 儲存成績至雲端")
                    
                    if sub_score:
                        df.at[row_idx_score, '局數比'] = score
                        valid_sets = [s.strip() for s in [set1, set2, set3] if s.strip()]
                        df.at[row_idx_score, '詳細比分'] = " / ".join(valid_sets) if valid_sets else ""
                        
                        if override_winner == "🤖 自動根據比分計算":
                            res = re.findall(r'\d+', score)
                            if len(res) == 2:
                                s1, s2 = int(res[0]), int(res[1])
                                if (s1 + s2 > 0) and (s1 != s2):
                                    df.at[row_idx_score, '勝隊'] = curr_score['T1'] if s1 > s2 else curr_score['T2']
                                else:
                                    df.at[row_idx_score, '勝隊'] = "尚未比賽"
                        else:
                            df.at[row_idx_score, '勝隊'] = override_winner
                        
                        df = auto_advance_finals(df)
                        
                        conn.update(data=df)
                        st.cache_data.clear()
                        st.success("✅ 比賽成績已成功更新！後續賽程已自動推進。")
                        st.rerun()

    else:
        st.error("🔒 這是專屬管理員的功能，一般球員請看其他頁面喔！")