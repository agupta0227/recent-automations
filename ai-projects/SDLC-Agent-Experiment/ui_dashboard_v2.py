import streamlit as st
import streamlit.components.v1 as components
import json
import subprocess
import sys
import os
import signal
from pathlib import Path
from datetime import datetime as dt
import time

st.set_page_config(
    page_title="SDLC Agent — Pipeline View",
    layout="wide",
    initial_sidebar_state="collapsed"
)

REFRESH_INTERVAL = 3

# ── Session state ─────────────────────────────────────────────
for key, default in [
    ('theme', 'light'),
    ('agent_pid', None),
    ('last_duration', '0m 0s'),
]:
    if key not in st.session_state:
        st.session_state[key] = default

IS_DARK = st.session_state.theme == 'dark'

# ── Full-page theme injection ─────────────────────────────────
page_bg   = '#181816' if IS_DARK else '#f5f5f3'
page_css  = f"""
<style>
  [data-testid="stAppViewContainer"], .stApp,
  section[data-testid="stMain"] {{
    background: {page_bg} !important;
  }}
  header[data-testid="stHeader"] {{ display:none !important; }}
  footer {{ display:none !important; }}
  #MainMenu {{ display:none !important; }}
  [data-testid="collapsedControl"] {{ display:none !important; }}
  .block-container {{
    padding: 8px 12px 0 12px !important;
    max-width: 100% !important;
  }}
  [data-testid="stVerticalBlock"] > div {{ padding:0 !important; }}
  [data-testid="stHorizontalBlock"] {{
    gap: 8px !important;
  }}
  button[kind="primary"] {{
    background: #FEF2F2 !important;
    border: 1px solid #E24B4A !important;
    color: #A32D2D !important;
  }}
</style>
"""
st.markdown(page_css, unsafe_allow_html=True)

# ── Process management ────────────────────────────────────────
def agent_is_running():
    pid = st.session_state.agent_pid
    if pid is None:
        return False
    try:
        import psutil
        p = psutil.Process(pid)
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            st.session_state.agent_pid = None
            return False

if st.session_state.agent_pid and not agent_is_running():
    st.session_state.agent_pid = None

is_proc_running = agent_is_running()

# ── Read status ───────────────────────────────────────────────
status_file       = Path("output/current_status.json")
running_agents    = []
completed_agents  = []
current_iteration = 0
last_message      = ""

if status_file.exists():
    try:
        with open(status_file, encoding='utf-8') as f:
            d = json.load(f)
        running_agents    = d.get('running_agents', [])
        completed_agents  = d.get('completed_agents', [])
        current_iteration = d.get('iteration', 0)
        last_message      = d.get('last_message', '')
    except Exception:
        pass

# ── Requirements ──────────────────────────────────────────────
req_language = "auto"
req_text     = ""
if Path("requirements.txt").exists():
    try:
        lines  = Path("requirements.txt").read_text(encoding="utf-8").splitlines()
        in_req = False
        rlines = []
        for line in lines:
            s = line.strip()
            if s.startswith("#"): continue
            if s.upper().startswith("LANGUAGE:"):
                req_language = s.split(":",1)[1].strip()
            elif s.upper().startswith("REQUIREMENT:"):
                in_req = True
                inline = s.split(":",1)[1].strip()
                if inline: rlines.append(inline)
            elif in_req:
                rlines.append(line.rstrip())
        req_text = " ".join(rlines).strip()
    except Exception:
        pass

# ── Metrics ───────────────────────────────────────────────────
log_dir     = Path("output/logs")
duration    = st.session_state.last_duration
log_content = ""

if log_dir.exists():
    log_files = [f for f in log_dir.glob("*.log")
                 if f.name not in ("ui_launch_stdout.log","ui_launch_stderr.log")]
    if log_files:
        latest = sorted(log_files, key=lambda x: x.stat().st_mtime)[-1]
        try:
            with open(latest, encoding='utf-8', errors='replace') as f:
                log_content = f.read()
            lines = [l.strip() for l in log_content.splitlines() if l.strip()]
            if len(lines) >= 2:
                fmt = "%Y-%m-%d %H:%M:%S"
                t0  = dt.strptime(lines[0][:19],  fmt)
                t1  = dt.strptime(lines[-1][:19], fmt)
                e   = (t1 - t0).total_seconds()
                if e > 0:
                    computed = f"{int(e//60)}m {int(e%60)}s"
                    duration = computed
                    st.session_state.last_duration = computed
        except Exception:
            pass

perf_data        = {}
tickets_total    = 0
tickets_critical = 0
tickets_major    = 0
tickets_minor    = 0
success_rate     = "0%"

perf_file = Path("output/performance_report.json")
if perf_file.exists():
    try:
        with open(perf_file, encoding='utf-8') as f:
            perf_data = json.load(f)
        tc = sum(a.get('calls',0)     for a in perf_data.get('agents',{}).values())
        sc = sum(a.get('successes',0) for a in perf_data.get('agents',{}).values())
        if tc > 0:
            success_rate = f"{sc/tc*100:.0f}%"
    except Exception:
        pass

if completed_agents and success_rate == "0%":
    success_rate = f"{min(100, round(len(completed_agents)/9*100))}%"

if Path("output/tickets.json").exists():
    try:
        with open("output/tickets.json", encoding='utf-8') as f:
            tl = json.load(f)
        tickets_total    = len(tl)
        tickets_critical = sum(1 for t in tl if t.get('severity')=='CRITICAL')
        tickets_major    = sum(1 for t in tl if t.get('severity')=='MAJOR')
        tickets_minor    = sum(1 for t in tl if t.get('severity')=='MINOR')
    except Exception:
        pass

# ── Overall status ────────────────────────────────────────────
is_complete = 'ProjectOrganizer' in completed_agents and not running_agents
is_error    = 'error' in last_message.lower() or 'failed' in last_message.lower()

if is_error:
    sl,sc_,sbg = 'error',   '#E24B4A','#FCEBEB'
elif is_complete:
    sl,sc_,sbg = 'complete','#1D9E75','#E1F5EE'
elif is_proc_running or running_agents:
    sl,sc_,sbg = 'running', '#EF9F27','#FAEEDA'
elif current_iteration > 0:
    sl,sc_,sbg = 'paused',  '#378ADD','#E6F1FB'
else:
    sl,sc_,sbg = 'idle',    '#888780','#F1EFE8'

blink = 'animation:dot 1.2s ease-in-out infinite;' \
        if sl in ('running','paused') else ''

# ── Palette ───────────────────────────────────────────────────
if IS_DARK:
    bg       = '#181816'
    surface  = '#222220'
    surface2 = '#2c2c2a'
    border   = '#3a3a38'
    fg       = '#e8e6e0'
    fg2      = '#888886'
    fg3      = '#555553'
else:
    bg       = '#f5f5f3'
    surface  = '#ffffff'
    surface2 = '#f0efeb'
    border   = '#e2e0d8'
    fg       = '#1a1a18'
    fg2      = '#666664'
    fg3      = '#999997'

# ── Agents ────────────────────────────────────────────────────
AGENTS = [
    ('RequirementAnalyzer','Requirement Analyzer','linear'),
    ('CodeGenerator',      'Code Generator',      'linear'),
    ('CodeFormatter',      'Code Formatter',       'linear'),
    ('CodeReviewer',       'Code Reviewer',        'loop'),
    ('Tester',             'Tester',               'loop'),
    ('BugFixer',           'Bug Fixer',            'loop'),
    ('ProjectOrganizer',   'Project Organizer',    'finalize'),
]
SUPPORT = [
    ('Tickets',    'Log issues'),
    ('Explain',    'Decision log'),
    ('Performance','Track timings'),
    ('Human gate', 'Approval checks'),
]

def astate(aid):
    if aid in running_agents:   return 'running'
    if aid in completed_agents: return 'done'
    return 'waiting'

def oneliner(aid):
    s = astate(aid)
    done_map = {
        'RequirementAnalyzer': f"Analyzed · {req_language} selected",
        'CodeGenerator':       "Source files generated",
        'CodeFormatter':       "Code blocks extracted",
        'CodeReviewer':        f"Reviewed · {tickets_total} issues found",
        'Tester':              "Test cases generated",
        'BugFixer':            f"Patches applied · {tickets_major+tickets_critical} addressed",
        'ProjectOrganizer':    "Project organized · README done",
    }
    run_map = {
        'RequirementAnalyzer': "Analyzing requirements...",
        'CodeGenerator':       "Generating source code...",
        'CodeFormatter':       "Extracting code blocks...",
        'CodeReviewer':        f"Reviewing — iteration {current_iteration}...",
        'Tester':              "Generating test cases...",
        'BugFixer':            "Applying patches...",
        'ProjectOrganizer':    "Organizing files...",
    }
    if s == 'done':    return done_map.get(aid, "Completed")
    if s == 'running': return run_map.get(aid, "Running...")
    return "Waiting to start"

def severity(aid):
    if aid in ('CodeReviewer','BugFixer'):
        if tickets_critical > 0: return 'HIGH',  '#FCEBEB','#A32D2D','#F09595'
        if tickets_major    > 0: return 'MED',   '#FAEEDA','#633806','#FAC775'
        return                          'LOW',   '#EAF3DE','#3B6D11','#C0DD97'
    if aid in ('CodeGenerator','Tester'):
        return 'MED','#FAEEDA','#633806','#FAC775'
    return 'LOW','#EAF3DE','#3B6D11','#C0DD97'

def t_str(aid):
    try:
        v = perf_data.get('agents',{}).get(aid.upper(),{}).get('avg_time',0)
        return f"{v:.0f}s" if v > 0 else ""
    except Exception:
        return ""

def make_bar(num, aid, name):
    s = astate(aid)
    if s == 'done':
        lb  = '3px solid #1D9E75'
        bbg = '#0a2e22' if IS_DARK else '#F0FAF6'
        ntc = '#9FE1CB' if IS_DARK else '#E1F5EE'
        nbc = '#1D9E75'
        bbc,bbt = '#1D9E75','#E1F5EE' if not IS_DARK else '#0a2e22'
        anim= ''
        stxt= 'completed'
    elif s == 'running':
        lb  = '3px solid #EF9F27'
        bbg = '#2a2008' if IS_DARK else '#FEFAF2'
        ntc = '#412402'
        nbc = '#EF9F27'
        bbc,bbt = '#EF9F27','#412402'
        anim= 'animation:barpulse 1.4s ease-in-out infinite;'
        stxt= 'running'
    else:
        lb  = f'3px solid {border}'
        bbg = surface
        ntc = fg3
        nbc = border
        bbc,bbt = surface2,fg3
        anim= f'opacity:0.55;'
        stxt= 'waiting'

    sl2,sbg2,sc2,sbc2 = severity(aid)
    t = t_str(aid)
    tc = fg if s != 'waiting' else fg2

    return f"""
<div style="display:flex;align-items:center;gap:10px;padding:8px 14px;
  border-radius:8px;border:0.5px solid {border};border-left:{lb};
  background:{bbg};margin-bottom:4px;{anim}">
  <div style="width:20px;height:20px;border-radius:50%;background:{nbc};
    display:flex;align-items:center;justify-content:center;
    font-size:10px;font-weight:600;color:{ntc};flex-shrink:0;">{num}</div>
  <div style="font-size:13px;font-weight:500;min-width:158px;color:{tc};">{name}</div>
  <div style="font-size:12px;color:{fg2};flex:1;overflow:hidden;
    white-space:nowrap;text-overflow:ellipsis;">{oneliner(aid)}</div>
  <div style="font-size:10px;font-weight:600;padding:2px 7px;border-radius:99px;
    background:{sbg2};color:{sc2};border:0.5px solid {sbc2};
    flex-shrink:0;letter-spacing:0.04em;">{sl2}</div>
  <div style="font-size:10px;font-weight:500;padding:2px 8px;border-radius:99px;
    background:{bbc};color:{bbt};flex-shrink:0;">{stxt}</div>
  <div style="font-size:11px;color:{fg3};min-width:38px;
    text-align:right;flex-shrink:0;">{t}</div>
</div>"""

linear_html = loop_html = final_html = ""
for i,(aid,name,phase) in enumerate(AGENTS,1):
    b = make_bar(i,aid,name)
    if phase=='linear':   linear_html += b
    elif phase=='loop':   loop_html   += b
    else:                 final_html  += b

loop_active = any(a in running_agents for a in ['CodeReviewer','Tester','BugFixer'])
sup_anim   = 'animation:barpulse 1.6s ease-in-out infinite;' if loop_active else ''
sup_border = '#7F77DD' if loop_active else border
sup_bg_    = ('#26215C' if IS_DARK else '#EEEDFE') if loop_active else surface2
sup_tc_    = ('#CECBF6' if IS_DARK else '#3C3489') if loop_active else fg3
support_html = "".join(f"""
<div style="flex:1;padding:8px 12px;border-radius:8px;
  border:0.5px solid {sup_border};background:{sup_bg_};
  text-align:center;{sup_anim}">
  <div style="font-size:12px;font-weight:500;color:{sup_tc_};">{n}</div>
  <div style="font-size:10px;color:{sup_tc_};opacity:0.7;margin-top:2px;">{s}</div>
</div>""" for n,s in SUPPORT)

cur = running_agents[0] if running_agents else \
      (completed_agents[-1] if completed_agents else "—")

log_lines_html = "".join(
    f'<div class="ll">{line}</div>'
    for line in log_content.splitlines() if line.strip()
) if log_content else f'<div style="color:{fg3};font-size:12px;">No logs yet.</div>'

req_short = req_text[:55].replace("'","&#39;") + ('…' if len(req_text)>55 else '')
lm_short  = last_message[:55] if last_message else '—'

if is_proc_running:
    ctrl = f"""
<button id="stopbtn"
  style="font-size:12px;font-weight:500;padding:5px 16px;border-radius:8px;
  border:0.5px solid #E24B4A;background:#FEF2F2;color:#A32D2D;cursor:pointer;
  animation:barpulse 2s ease-in-out infinite;">■ Stop</button>"""
else:
    ctrl = f"""
<button id="startbtn"
  style="font-size:12px;font-weight:500;padding:5px 16px;border-radius:8px;
  border:0.5px solid #1D9E75;background:#F0FAF6;color:#0F6E56;cursor:pointer;">
  ▶ Start</button>
<button disabled
  style="font-size:12px;font-weight:500;padding:5px 16px;border-radius:8px;
  border:0.5px solid {border};background:{surface2};color:{fg3};
  cursor:not-allowed;opacity:0.4;">⏸ Pause</button>"""

theme_lbl = "☀️  Light" if IS_DARK else "🌙  Dark"

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
html,body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
  background:{bg};color:{fg};padding:18px 22px 24px;}}
@keyframes barpulse{{0%,100%{{opacity:1}}50%{{opacity:0.55}}}}
@keyframes dot{{0%,100%{{opacity:1}}50%{{opacity:0.2}}}}
.ph{{font-size:10px;color:{fg3};text-transform:uppercase;
  letter-spacing:.07em;margin:13px 0 5px;font-weight:500;}}
.cards{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-top:14px;}}
.card{{background:{surface};border:.5px solid {border};border-radius:12px;padding:12px 14px;}}
.card h3{{font-size:10px;font-weight:600;color:{fg3};text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:8px;}}
.mrow{{display:flex;justify-content:space-between;align-items:baseline;
  padding:4px 0;border-bottom:.5px solid {border};font-size:12px;}}
.mrow:last-child{{border-bottom:none;}}
.ml{{color:{fg2};}} .mv{{font-weight:500;color:{fg};}}
.mv.g{{color:#0F6E56;}} .mv.a{{color:#854F0B;}} .mv.r{{color:#A32D2D;}}
.logwrap{{height:200px;overflow-y:auto;margin-top:4px;
  background:{surface2};border-radius:8px;padding:8px 10px;}}
.logwrap::-webkit-scrollbar{{width:4px;}}
.logwrap::-webkit-scrollbar-thumb{{background:{border};border-radius:2px;}}
.ll{{font-size:10px;font-family:'Courier New',monospace;color:{fg2};
  padding:1px 0;line-height:1.5;white-space:pre-wrap;word-break:break-all;}}
.mb{{display:flex;flex:1;flex-direction:column;align-items:center;
  padding:6px 4px;border-radius:8px;}}
.mb .n{{font-size:20px;font-weight:500;line-height:1.1;}}
.mb .l{{font-size:10px;margin-top:2px;}}
</style>
</head><body>

<!-- TOP BAR -->
<div style="display:flex;align-items:center;justify-content:space-between;
  margin-bottom:16px;gap:12px;flex-wrap:wrap;">
  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
    <span style="font-size:17px;font-weight:600;color:{fg};white-space:nowrap;">
      SDLC — Pipeline View</span>
    <span style="display:inline-flex;align-items:center;gap:5px;font-size:11px;
      padding:3px 10px;border-radius:99px;background:#E1F5EE;color:#0F6E56;font-weight:500;">
      <svg width="6" height="6"><circle cx="3" cy="3" r="3" fill="#1D9E75"/></svg>
      iter {current_iteration} / 5</span>
    <span style="display:inline-flex;align-items:center;gap:5px;font-size:11px;
      padding:3px 10px;border-radius:99px;background:{sbg};color:{sc_};font-weight:500;">
      <span style="width:6px;height:6px;border-radius:50%;background:{sc_};
        display:inline-block;{blink}"></span>{sl}</span>
    <span style="font-size:11px;color:{fg3};max-width:280px;overflow:hidden;
      white-space:nowrap;text-overflow:ellipsis;" title="{req_text[:200]}">
      <b style="color:{fg2};font-weight:500;">{req_language}</b> · {req_short}</span>
  </div>
  <div style="display:flex;align-items:center;gap:8px;">
    <span style="font-size:12px;font-weight:500;color:{fg2};">{duration}</span>
  </div>
</div>

<!-- AGENT BARS -->
<div class="ph">linear phase</div>
{linear_html}
<div class="ph">review loop — iteration {current_iteration}</div>
{loop_html}
<div class="ph">finalize</div>
{final_html}

<!-- SUPPORT ROW -->
<div class="ph">supporting agents</div>
<div style="display:flex;gap:8px;margin-bottom:2px;">{support_html}</div>

<!-- CARDS -->
<div class="cards">
  <div class="card">
    <h3>current agent</h3>
    <div style="font-size:14px;font-weight:500;color:{fg};margin-bottom:2px;">{cur}</div>
    <div style="font-size:11px;color:{fg2};margin-bottom:8px;">
      {oneliner(cur) if cur!='—' else 'No agent active yet'}</div>
    <div style="display:flex;gap:5px;margin-bottom:8px;">
      <div class="mb" style="background:#FAEEDA;">
        <div class="n" style="color:#854F0B;">{tickets_total}</div>
        <div class="l" style="color:#BA7517;">tickets</div></div>
      <div class="mb" style="background:#FCEBEB;">
        <div class="n" style="color:#A32D2D;">{tickets_critical}</div>
        <div class="l" style="color:#E24B4A;">critical</div></div>
      <div class="mb" style="background:#FAEEDA;">
        <div class="n" style="color:#854F0B;">{tickets_major}</div>
        <div class="l" style="color:#BA7517;">major</div></div>
      <div class="mb" style="background:#E1F5EE;">
        <div class="n" style="color:#0F6E56;">{tickets_minor}</div>
        <div class="l" style="color:#1D9E75;">minor</div></div>
    </div>
  </div>

  <div class="card">
    <h3>run summary</h3>
    <div class="mrow"><span class="ml">Duration</span>
      <span class="mv">{duration}</span></div>
    <div class="mrow"><span class="ml">Iterations</span>
      <span class="mv">{current_iteration} / 5</span></div>
    <div class="mrow"><span class="ml">Success rate</span>
      <span class="mv g">{success_rate}</span></div>
    <div class="mrow"><span class="ml">Agents done</span>
      <span class="mv">{len(completed_agents)} / {len(AGENTS)}</span></div>
    <div class="mrow"><span class="ml">Total tickets</span>
      <span class="mv a">{tickets_total}</span></div>
    <div class="mrow"><span class="ml">Last update</span>
      <span class="mv" style="font-size:10px;max-width:160px;text-align:right;
        overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{lm_short}</span></div>
  </div>

  <div class="card">
    <h3>live logs</h3>
    <div class="logwrap" id="lb">{log_lines_html}</div>
  </div>
</div>

<div style="font-size:10px;color:{fg3};margin-top:12px;text-align:right;">
  auto-refreshing every {REFRESH_INTERVAL}s · SDLC Agentic AI</div>

<script>
var lb=document.getElementById('lb');
if(lb) lb.scrollTop=lb.scrollHeight;
function sendH(){{
  var h=document.body.scrollHeight;
  window.parent.postMessage({{type:'streamlit:setFrameHeight',height:h+32}},'*');
}}
window.addEventListener('load',sendH);
window.addEventListener('resize',sendH);
if(window.ResizeObserver) new ResizeObserver(sendH).observe(document.body);
setTimeout(sendH,50);setTimeout(sendH,400);setTimeout(sendH,1000);

// controls handled by Streamlit buttons above
</script>
</body></html>"""

# ── Streamlit wrapper — control bar above component ──────────
# Row 1: theme toggle (far right)
_, theme_col = st.columns([20, 2])
with theme_col:
    if st.button("🌙 Dark" if not IS_DARK else "☀️ Light",
                 key="theme_btn", use_container_width=True):
        st.session_state.theme = 'dark' if not IS_DARK else 'light'
        st.rerun()

# Row 2: Start / Stop side by side
if not is_proc_running:
    _, start_col, _ = st.columns([8, 4, 8])
    with start_col:
        if st.button("▶  START EXECUTION",
                     key="start_btn", use_container_width=True):
            try:
                os.makedirs("output/logs", exist_ok=True)
                st.session_state.last_duration = '0m 0s'
                proc = subprocess.Popen(
                    [sys.executable, "main_agent_fixed.py"],
                    stdout=open("output/logs/ui_launch_stdout.log","w",
                                encoding="utf-8"),
                    stderr=open("output/logs/ui_launch_stderr.log","w",
                                encoding="utf-8"),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
                )
                st.session_state.agent_pid = proc.pid
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start: {e}")
else:
    st.success(f"🟢 Agent running (PID {st.session_state.agent_pid})"
               f" — {duration} elapsed", icon=None)
    _, stop_col, _ = st.columns([8, 4, 8])
    with stop_col:
        if st.button("⏹  STOP EXECUTION",
                     key="stop_btn", type="primary",
                     use_container_width=True):
            try:
                if os.name == 'nt':
                    subprocess.call(['taskkill','/F','/T','/PID',
                                     str(st.session_state.agent_pid)])
                else:
                    os.kill(st.session_state.agent_pid, signal.SIGTERM)
                st.session_state.agent_pid = None
                st.rerun()
            except Exception as e:
                st.error(f"Stop failed: {e}")

# Single full-width component — display only
components.html(html, height=1000, scrolling=False)

time.sleep(REFRESH_INTERVAL)
st.rerun()
