from __future__ import annotations

import json
import logging
import os
import tempfile
import webbrowser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from trajex.trace import Trace

logger = logging.getLogger("trajex")

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trajex — Trace Viewer</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'SF Mono','Fira Code','Consolas',monospace;background:#0d1117;color:#c9d1d9;font-size:13px;height:100vh;overflow:hidden}
a{color:#58a6ff}
#top{background:#161b22;border-bottom:1px solid #21262d;padding:10px 16px;display:flex;gap:16px;align-items:center;min-height:50px;flex-wrap:wrap}
#top .logo{font-weight:700;color:#58a6ff;font-size:14px;letter-spacing:.05em;white-space:nowrap}
#top .prompt{flex:1;color:#8b949e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer;transition:color .15s}
#top .prompt:hover{color:#c9d1d9}
#top .prompt.expanded{white-space:normal;overflow:visible}
.pill{padding:2px 10px;border-radius:12px;font-size:11px;font-weight:700;white-space:nowrap}
.pill-success{background:#1a4731;color:#3fb950}
.pill-error{background:#5b1a1a;color:#f85149}
.pill-interrupted{background:#3d2c00;color:#e3b341}
.stat{color:#8b949e;white-space:nowrap;font-size:12px}
.stat b{color:#c9d1d9}
#body{display:flex;height:calc(100vh - 50px)}
#sidebar{width:300px;min-width:220px;border-right:1px solid #21262d;overflow-y:auto;flex-shrink:0}
#sidebar::-webkit-scrollbar{width:4px}
#sidebar::-webkit-scrollbar-thumb{background:#30363d;border-radius:2px}
#detail{flex:1;overflow-y:auto;padding:20px}
#detail::-webkit-scrollbar{width:6px}
#detail::-webkit-scrollbar-thumb{background:#30363d;border-radius:3px}

/* Timeline rows */
.row{padding:8px 12px;border-bottom:1px solid #161b22;cursor:pointer;display:flex;align-items:center;gap:10px;border-left:3px solid transparent;transition:background .1s}
.row:hover{background:#161b22}
.row.active{background:#1c2128;border-left-color:#58a6ff!important}
.row-tool_call{border-left-color:rgba(31,111,235,.5)}
.row-llm_call,.row-llm_response{border-left-color:rgba(139,148,158,.3)}
.row-error{border-left-color:#f85149}
.row-agent_finish{border-left-color:#3fb950}
.row-handoff{border-left-color:#a371f7}
.step-num{color:#484f58;font-size:10px;min-width:22px;text-align:right}
.step-icon{width:20px;text-align:center;font-size:12px;font-weight:700}
.icon-tool_call{color:#1f6feb}
.icon-llm_call,.icon-llm_response{color:#484f58}
.icon-agent_finish{color:#3fb950}
.icon-error{color:#f85149}
.icon-handoff{color:#a371f7}
.icon-agent_action{color:#e3b341}
.step-meta{flex:1;overflow:hidden}
.step-name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12px;font-weight:600}
.step-type{font-size:10px;color:#484f58;text-transform:uppercase;letter-spacing:.05em}
.step-dur{font-size:10px;color:#484f58;white-space:nowrap}

/* Detail pane */
.detail-empty{color:#484f58;text-align:center;padding:80px 40px;font-size:14px}
.detail-title{font-size:17px;font-weight:700;color:#e6edf3;margin-bottom:4px}
.detail-subtitle{font-size:11px;color:#484f58;text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px}
.detail-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:8px;margin-bottom:16px}
.meta-card{background:#161b22;border:1px solid #21262d;border-radius:6px;padding:8px 10px}
.meta-label{font-size:10px;color:#484f58;text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px}
.meta-value{font-size:12px;color:#c9d1d9;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.section{margin-bottom:16px}
.section-label{font-size:10px;color:#484f58;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;display:flex;align-items:center;gap:6px}
.section-label::after{content:'';flex:1;height:1px;background:#21262d}
.code-block{background:#161b22;border:1px solid #21262d;border-radius:6px;padding:12px;white-space:pre-wrap;word-break:break-all;line-height:1.6;font-size:12px;max-height:400px;overflow-y:auto}
.code-block::-webkit-scrollbar{width:4px}
.code-block::-webkit-scrollbar-thumb{background:#30363d}
.reasoning-block{background:#1c2128;border:1px solid #21262d;border-left:3px solid #484f58;border-radius:6px;padding:10px 12px;white-space:pre-wrap;color:#8b949e;font-style:italic;line-height:1.6;font-size:12px}
.error-block{background:#1a0a0a;border:1px solid #5b1a1a;border-radius:6px;padding:10px 12px;color:#f85149;white-space:pre-wrap;font-size:12px;line-height:1.6}

/* JSON syntax */
.jk{color:#7ee787}.js{color:#a5d6ff}.jn{color:#79c0ff}.jb{color:#ff7b72}.jnull{color:#484f58}

/* Search */
#search-wrap{padding:8px 10px;border-bottom:1px solid #21262d;position:sticky;top:0;background:#0d1117;z-index:1}
#search{width:100%;background:#161b22;border:1px solid #21262d;border-radius:4px;padding:5px 8px;color:#c9d1d9;font-family:inherit;font-size:12px;outline:none}
#search:focus{border-color:#388bfd}
#search::placeholder{color:#484f58}

.hidden{display:none!important}
</style>
</head>
<body>
<div id="top">
  <span class="logo">TRAJEX</span>
  <span class="prompt" id="prompt-el" onclick="this.classList.toggle('expanded')" title="Click to expand"></span>
  <div id="status-pill" class="pill"></div>
  <span class="stat">Steps: <b id="stat-steps"></b></span>
  <span class="stat">Tools: <b id="stat-tools"></b></span>
  <span class="stat">Duration: <b id="stat-dur"></b></span>
  <span class="stat">Framework: <b id="stat-fw"></b></span>
</div>
<div id="body">
  <div id="sidebar">
    <div id="search-wrap"><input id="search" placeholder="Filter steps..." oninput="filterSteps(this.value)"></div>
    <div id="timeline"></div>
  </div>
  <div id="detail"><div class="detail-empty">Select a step from the timeline to inspect it.</div></div>
</div>
<script>
const T = TRACE_DATA_PLACEHOLDER;

const ICONS = {tool_call:'T',tool_result:'R',llm_call:'L',llm_response:'L',agent_action:'A',agent_finish:'F',handoff:'H',error:'!'};
const ICON_CLASS = {tool_call:'icon-tool_call',llm_call:'icon-llm_call',llm_response:'icon-llm_response',agent_finish:'icon-agent_finish',error:'icon-error',handoff:'icon-handoff',agent_action:'icon-agent_action'};

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

function fmt_ms(ms){
  if(ms==null)return'—';
  if(ms<1000)return ms.toFixed(0)+'ms';
  return(ms/1000).toFixed(2)+'s';
}

function syntax(obj){
  let s=typeof obj==='string'?obj:JSON.stringify(obj,null,2);
  return esc(s).replace(
    /("(?:\\.|[^"\\])*"(\s*:)?|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    function(m){
      if(m==='null')return'<span class="jnull">'+m+'</span>';
      if(m==='true'||m==='false')return'<span class="jb">'+m+'</span>';
      if(/^-?\d/.test(m))return'<span class="jn">'+m+'</span>';
      if(/:$/.test(m))return'<span class="jk">'+m+'</span>';
      return'<span class="js">'+m+'</span>';
    }
  );
}

function init(){
  document.getElementById('prompt-el').textContent=T.prompt;
  document.getElementById('stat-steps').textContent=T.steps.length;
  const tc=T.steps.filter(s=>s.step_type==='tool_call');
  document.getElementById('stat-tools').textContent=tc.length;
  const s=T.started_at?new Date(T.started_at):null;
  const e=T.ended_at?new Date(T.ended_at):null;
  document.getElementById('stat-dur').textContent=(s&&e)?fmt_ms(e-s):'—';
  const fw=T.metadata&&T.metadata.framework||'unknown';
  document.getElementById('stat-fw').textContent=fw;
  const pill=document.getElementById('status-pill');
  pill.textContent=(T.status||'unknown').toUpperCase();
  pill.className='pill pill-'+(T.status||'unknown');

  const tl=document.getElementById('timeline');
  T.steps.forEach((step,i)=>{
    const row=document.createElement('div');
    row.className='row row-'+step.step_type;
    row.id='row-'+i;
    row.setAttribute('data-name',(step.name||'').toLowerCase());
    row.setAttribute('data-type',step.step_type||'');
    row.onclick=()=>show(i);
    const ic=ICON_CLASS[step.step_type]||'';
    row.innerHTML=
      '<span class="step-num">'+step.index+'</span>'+
      '<span class="step-icon '+ic+'">'+(ICONS[step.step_type]||'?')+'</span>'+
      '<div class="step-meta">'+
        '<div class="step-name">'+esc(step.name)+'</div>'+
        '<div class="step-type">'+esc(step.step_type)+'</div>'+
      '</div>'+
      '<span class="step-dur">'+fmt_ms(step.duration_ms)+'</span>';
    tl.appendChild(row);
  });
}

function filterSteps(q){
  q=q.toLowerCase().trim();
  document.querySelectorAll('.row').forEach(row=>{
    const name=row.getAttribute('data-name');
    const type=row.getAttribute('data-type');
    row.classList.toggle('hidden',q!==''&&!name.includes(q)&&!type.includes(q));
  });
}

function show(i){
  document.querySelectorAll('.row').forEach(r=>r.classList.remove('active'));
  const rowEl=document.getElementById('row-'+i);
  if(rowEl){rowEl.classList.add('active');rowEl.scrollIntoView({block:'nearest'});}
  const step=T.steps[i];
  const d=document.getElementById('detail');
  let html='';
  html+='<div class="detail-title">'+esc(step.name)+'</div>';
  html+='<div class="detail-subtitle">'+esc(step.step_type)+' &nbsp;·&nbsp; step '+step.index+'</div>';
  html+='<div class="detail-grid">';
  html+=mc('Duration',fmt_ms(step.duration_ms));
  html+=mc('Status',step.error?'ERROR':'OK');
  if(step.started_at)html+=mc('Started',step.started_at.replace('T',' ').replace('+00:00','Z'));
  if(step.ended_at)html+=mc('Ended',step.ended_at.replace('T',' ').replace('+00:00','Z'));
  html+='</div>';
  if(step.input!=null){
    const v=typeof step.input==='object'?JSON.stringify(step.input,null,2):String(step.input);
    html+=sec('Input','<div class="code-block">'+syntax(v)+'</div>');
  }
  if(step.output!=null){
    const v=typeof step.output==='object'?JSON.stringify(step.output,null,2):String(step.output);
    html+=sec('Output','<div class="code-block">'+syntax(v)+'</div>');
  }
  if(step.reasoning){
    html+=sec('Reasoning','<div class="reasoning-block">'+esc(step.reasoning)+'</div>');
  }
  if(step.error){
    html+=sec('Error','<div class="error-block">'+esc(step.error)+'</div>');
  }
  if(step.metadata&&Object.keys(step.metadata).length>0){
    html+=sec('Metadata','<div class="code-block">'+syntax(JSON.stringify(step.metadata,null,2))+'</div>');
  }
  d.innerHTML=html;
}

function mc(label,value){
  return'<div class="meta-card"><div class="meta-label">'+esc(label)+'</div><div class="meta-value" title="'+esc(value)+'">'+esc(value)+'</div></div>';
}
function sec(label,body){
  return'<div class="section"><div class="section-label">'+esc(label)+'</div>'+body+'</div>';
}

document.addEventListener('keydown',e=>{
  if(e.key==='/'&&e.target.tagName!=='INPUT'){e.preventDefault();document.getElementById('search').focus();}
  if(e.key==='Escape'){document.getElementById('search').value='';filterSteps('');}
});

init();
</script>
</body>
</html>"""


def generate_viewer_html(trace: "Trace") -> str:
    trace_json = json.dumps(trace.to_dict(), ensure_ascii=False, separators=(",", ":"))
    return _HTML_TEMPLATE.replace("TRACE_DATA_PLACEHOLDER", trace_json)


def write_viewer(trace: "Trace", path: str | None = None) -> str:
    """Write the HTML viewer to a file and return the absolute path.

    Does NOT open a browser — the caller decides what to do with the path.
    In CI environments there is no browser; the file path is what matters.
    """
    html = generate_viewer_html(trace)
    if path is None:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        )
        tmp.write(html)
        tmp.flush()
        tmp.close()
        return os.path.abspath(tmp.name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return os.path.abspath(path)


# Keep old name as alias so existing code doesn't break, but it no longer
# calls webbrowser.open — it just writes and returns the path.
def open_viewer(trace: "Trace") -> str:
    return write_viewer(trace)
