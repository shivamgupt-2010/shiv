"""
ShivAI V2.0 High-Level Admin Dashboard & Governance API.
Provides an interactive web control center to view and adjust runtime settings,
inspect system health, manage models, and test every V2 AI capability directly.
"""
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Query, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from config.settings import settings
from core.routing.registry import model_registry, ModelInfo
from core.resilience.circuit_breaker import circuit_breaker_registry, CircuitState
from core.resilience.key_pool import key_pool_manager
from providers.registry import provider_registry
from security.auth import get_current_user_id

v2_admin_router = APIRouter(tags=["v2 - Admin & Governance"])


class UpdateModelPayload(BaseModel):
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    speed_score: Optional[float] = None
    quality_score: Optional[float] = None
    cost_score: Optional[float] = None
    context_window: Optional[int] = None


class UpdateSettingsPayload(BaseModel):
    router_default_mode: Optional[str] = None
    router_max_retries: Optional[int] = None
    retry_base_delay_seconds: Optional[float] = None
    retry_max_delay_seconds: Optional[float] = None
    circuit_breaker_threshold: Optional[int] = None
    circuit_breaker_recovery_seconds: Optional[float] = None
    rate_limit_per_minute: Optional[int] = None
    request_timeout_seconds: Optional[float] = None


@v2_admin_router.get("/v2/admin/config", response_model=Dict[str, Any])
async def get_admin_config(user_id: str = Depends(get_current_user_id)):
    """Returns current live runtime settings, model states, providers, and circuit breakers."""
    models = model_registry.list_all(enabled_only=False)
    
    # Gather circuit breaker statuses
    breakers = {}
    for prov in ["groq", "gemini", "openai", "anthropic", "deepseek", "mistral"]:
        b = await circuit_breaker_registry.get_or_create(prov)
        breakers[prov] = {
            "state": b.state.value,
            "failure_count": b.failure_count,
            "threshold": b.failure_threshold,
            "recovery_seconds": b.recovery_timeout,
        }

    # Gather provider key availability
    prov_status = {}
    for prov in ["groq", "gemini", "openai", "anthropic", "deepseek", "mistral"]:
        configured = prov in provider_registry.list_configured()
        prov_status[prov] = {
            "configured": configured,
            "status": "ready" if configured else "missing_key",
        }

    return {
        "status": "success",
        "settings": {
            "env": settings.SHIVAI_ENV,
            "port": settings.effective_port,
            "router_default_mode": settings.ROUTER_DEFAULT_MODE,
            "router_max_retries": settings.ROUTER_MAX_RETRIES,
            "retry_base_delay_seconds": settings.RETRY_BASE_DELAY_SECONDS,
            "retry_max_delay_seconds": settings.RETRY_MAX_DELAY_SECONDS,
            "circuit_breaker_threshold": settings.CIRCUIT_BREAKER_THRESHOLD,
            "circuit_breaker_recovery_seconds": settings.CIRCUIT_BREAKER_RECOVERY_SECONDS,
            "rate_limit_per_minute": settings.RATE_LIMIT_PER_MINUTE,
            "request_timeout_seconds": settings.REQUEST_TIMEOUT_SECONDS,
            "shiv_db_url": settings.SHIV_DB_URL,
            "shiv_db_project_id": settings.SHIV_DB_PROJECT_ID,
            "auth_algorithm": settings.SHIV_AUTH_JWT_ALGORITHM,
        },
        "circuit_breakers": breakers,
        "providers": prov_status,
        "models": [m.model_dump() for m in models],
    }


@v2_admin_router.post("/v2/admin/config")
async def update_admin_config(payload: UpdateSettingsPayload, user_id: str = Depends(get_current_user_id)):
    """Dynamically modifies runtime settings without restarting the server."""
    if payload.router_default_mode:
        settings.ROUTER_DEFAULT_MODE = payload.router_default_mode
    if payload.router_max_retries is not None:
        settings.ROUTER_MAX_RETRIES = max(0, min(10, payload.router_max_retries))
    if payload.retry_base_delay_seconds is not None:
        settings.RETRY_BASE_DELAY_SECONDS = max(0.1, payload.retry_base_delay_seconds)
    if payload.retry_max_delay_seconds is not None:
        settings.RETRY_MAX_DELAY_SECONDS = max(1.0, payload.retry_max_delay_seconds)
    if payload.circuit_breaker_threshold is not None:
        settings.CIRCUIT_BREAKER_THRESHOLD = max(1, payload.circuit_breaker_threshold)
        for b in circuit_breaker_registry._breakers.values():
            b.failure_threshold = settings.CIRCUIT_BREAKER_THRESHOLD
    if payload.circuit_breaker_recovery_seconds is not None:
        settings.CIRCUIT_BREAKER_RECOVERY_SECONDS = max(5.0, payload.circuit_breaker_recovery_seconds)
        for b in circuit_breaker_registry._breakers.values():
            b.recovery_timeout = settings.CIRCUIT_BREAKER_RECOVERY_SECONDS
    if payload.rate_limit_per_minute is not None:
        settings.RATE_LIMIT_PER_MINUTE = max(10, payload.rate_limit_per_minute)
    if payload.request_timeout_seconds is not None:
        settings.REQUEST_TIMEOUT_SECONDS = max(5.0, payload.request_timeout_seconds)

    return {
        "status": "success",
        "message": "Runtime configuration updated successfully.",
        "active_settings": {
            "router_default_mode": settings.ROUTER_DEFAULT_MODE,
            "router_max_retries": settings.ROUTER_MAX_RETRIES,
            "retry_base_delay_seconds": settings.RETRY_BASE_DELAY_SECONDS,
            "circuit_breaker_threshold": settings.CIRCUIT_BREAKER_THRESHOLD,
            "circuit_breaker_recovery_seconds": settings.CIRCUIT_BREAKER_RECOVERY_SECONDS,
        }
    }


@v2_admin_router.post("/v2/admin/models/{model_id}")
async def update_model_config(model_id: str, payload: UpdateModelPayload, user_id: str = Depends(get_current_user_id)):
    """Enables/disables or adjusts scoring parameters for a specific model in the registry."""
    model = model_registry.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found in registry.")

    if payload.enabled is not None:
        model.enabled = payload.enabled
    if payload.priority is not None:
        model.priority = payload.priority
    if payload.speed_score is not None:
        model.speed_score = payload.speed_score
    if payload.quality_score is not None:
        model.quality_score = payload.quality_score
    if payload.cost_score is not None:
        model.cost_score = payload.cost_score
    if payload.context_window is not None:
        model.context_window = payload.context_window

    return {"status": "success", "model": model.model_dump()}


@v2_admin_router.post("/v2/admin/circuit-breaker/reset")
async def reset_circuit_breakers(provider: Optional[str] = Query(None), user_id: str = Depends(get_current_user_id)):
    """Resets tripped circuit breakers to CLOSED."""
    if provider:
        b = await circuit_breaker_registry.get_or_create(provider)
        await b.reset()
        return {"status": "success", "message": f"Circuit breaker for '{provider}' reset to CLOSED."}
    else:
        for b in circuit_breaker_registry._breakers.values():
            await b.reset()
        return {"status": "success", "message": "All circuit breakers reset to CLOSED."}


@v2_admin_router.get("/admin", response_class=HTMLResponse)
@v2_admin_router.get("/dashboard", response_class=HTMLResponse)
async def serve_admin_dashboard(request: Request):
    """Serves the complete high-level interactive Admin Dashboard Single Page Application."""
    return HTMLResponse(content=DASHBOARD_HTML)


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SHIV AI V2.0 — Admin Command Center</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['"Plus Jakarta Sans"', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'monospace'],
          },
          colors: {
            shiv: {
              50: '#f0fdf4',
              500: '#10b981',
              600: '#059669',
              primary: '#6366f1',
              accent: '#06b6d4',
              dark: '#0b0f19',
              card: '#111827',
              border: '#1f2937'
            }
          }
        }
      }
    }
  </script>
  <style>
    body { background-color: #0b0f19; font-family: 'Plus Jakarta Sans', sans-serif; }
    .glass { background: rgba(17, 24, 39, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
    .glass-card { background: rgba(17, 24, 39, 0.85); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.06); }
    .tab-active { background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(6, 182, 212, 0.25)); border-color: #6366f1; color: #fff; }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0b0f19; }
    ::-webkit-scrollbar-thumb { background: #374151; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #4b5563; }
  </style>
</head>
<body class="text-slate-200 min-h-screen flex flex-col antialiased">

  <!-- Top Header Navigation -->
  <header class="sticky top-0 z-50 glass border-b border-slate-800/80 px-6 py-3.5 flex items-center justify-between">
    <div class="flex items-center space-x-4">
      <div class="flex items-center space-x-2.5">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/20">
          ⚡
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h1 class="font-extrabold text-lg tracking-tight bg-gradient-to-r from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">SHIV AI V2.0</h1>
            <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">ORCHESTRATOR</span>
          </div>
          <p class="text-[11px] text-slate-400 font-mono">Platform Admin & Testing Console</p>
        </div>
      </div>
    </div>

    <!-- Right Controls: Status & API Key -->
    <div class="flex items-center space-x-3">
      <div id="connection-pill" class="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        <span>CONNECTED</span>
      </div>

      <div class="flex items-center space-x-2 bg-slate-900/90 border border-slate-800 rounded-lg px-2.5 py-1 text-xs">
        <span class="text-slate-400 font-mono">API Key:</span>
        <input type="password" id="auth-key-input" placeholder="shivai-production-key-2026" value="shivai-production-key-2026" class="bg-transparent text-slate-200 font-mono focus:outline-none w-44">
        <button onclick="saveApiKey()" class="text-indigo-400 hover:text-indigo-300 font-semibold text-[11px]">Set</button>
      </div>

      <button onclick="refreshAllData()" title="Reload Stats" class="p-2 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700/60 transition">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
      </button>
    </div>
  </header>

  <!-- Main Container -->
  <div class="flex-1 flex overflow-hidden">

    <!-- Sidebar Navigation -->
    <aside class="w-64 glass border-r border-slate-800/80 p-4 flex flex-col space-y-1 text-sm font-medium">
      <div class="text-[11px] font-bold uppercase tracking-wider text-slate-400 px-3 py-2">System</div>
      <button onclick="switchTab('overview')" id="tab-btn-overview" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition tab-active">
        <span>📊</span> <span>Overview & Telemetry</span>
      </button>
      <button onclick="switchTab('settings')" id="tab-btn-settings" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>⚙️</span> <span>Settings & Models</span>
      </button>
      
      <div class="text-[11px] font-bold uppercase tracking-wider text-slate-400 px-3 py-2 pt-4">Feature Playgrounds</div>
      <button onclick="switchTab('chat')" id="tab-btn-chat" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>💬</span> <span>Chat & Router</span>
      </button>
      <button onclick="switchTab('voice')" id="tab-btn-voice" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>🎙️</span> <span>Voice AI (STT & TTS)</span>
      </button>
      <button onclick="switchTab('research')" id="tab-btn-research" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>🔍</span> <span>Autonomous Research</span>
      </button>
      <button onclick="switchTab('tools')" id="tab-btn-tools" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>🛠️</span> <span>Tool Sandbox</span>
      </button>
      <button onclick="switchTab('agents')" id="tab-btn-agents" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>🤖</span> <span>Multi-Agent DAG</span>
      </button>
      <button onclick="switchTab('documents')" id="tab-btn-documents" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>📄</span> <span>Docs & Multimodal</span>
      </button>
      <button onclick="switchTab('memory')" id="tab-btn-memory" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>🧠</span> <span>Memory Inspector</span>
      </button>
      <button onclick="switchTab('media')" id="tab-btn-media" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>🎨</span> <span>Media Studio (Free)</span>
      </button>
      <button onclick="switchTab('orchestrator')" id="tab-btn-orchestrator" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>🎯</span> <span>Intent & DAG Planner</span>
      </button>
      <button onclick="switchTab('studios')" id="tab-btn-studios" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>🚀</span> <span>Creative & Dev Studios</span>
      </button>
      <button onclick="switchTab('jobs')" id="tab-btn-jobs" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>⚡</span> <span>Background Jobs</span>
      </button>
      <button onclick="switchTab('devices')" id="tab-btn-devices" class="w-full text-left px-3.5 py-2.5 rounded-xl flex items-center space-x-3 transition text-slate-400 hover:bg-slate-800/50 hover:text-white">
        <span>📱</span> <span>Devices & Automation</span>
      </button>


      <div class="mt-auto pt-6 border-t border-slate-800/60 text-xs text-slate-400 px-3">
        <div class="flex justify-between py-1"><span>Env:</span> <span class="text-slate-200 font-mono" id="stat-env">production</span></div>
        <div class="flex justify-between py-1"><span>Port:</span> <span class="text-slate-200 font-mono" id="stat-port">8000</span></div>
        <div class="flex justify-between py-1"><span>SHIV DB:</span> <span class="text-emerald-400 font-mono">Connected</span></div>
      </div>
    </aside>

    <!-- Main Content Area -->
    <main class="flex-1 overflow-y-auto p-8 space-y-8 bg-gradient-to-b from-slate-950 via-[#0b0f19] to-slate-950">

      <!-- =============================================================== -->
      <!-- TAB 1: OVERVIEW & TELEMETRY -->
      <!-- =============================================================== -->
      <section id="tab-overview" class="space-y-6">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">System Overview & Live Telemetry</h2>
          <p class="text-sm text-slate-400 mt-1">Real-time status of AI models, providers, circuit breakers, and database synchronization.</p>
        </div>

        <!-- Telemetry Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div class="glass-card p-5 rounded-2xl">
            <div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
              <span>Active Models</span>
              <span class="text-indigo-400 text-base">🤖</span>
            </div>
            <div class="text-3xl font-extrabold text-white mt-2" id="card-active-models">--</div>
            <div class="text-xs text-slate-400 mt-1">Registered in orchestrator</div>
          </div>

          <div class="glass-card p-5 rounded-2xl">
            <div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
              <span>Configured Providers</span>
              <span class="text-emerald-400 text-base">🔑</span>
            </div>
            <div class="text-3xl font-extrabold text-emerald-400 mt-2" id="card-active-providers">--</div>
            <div class="text-xs text-slate-400 mt-1">Ready with API keys</div>
          </div>

          <div class="glass-card p-5 rounded-2xl">
            <div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
              <span>Circuit Breakers</span>
              <span class="text-cyan-400 text-base">🛡️</span>
            </div>
            <div class="text-3xl font-extrabold text-cyan-400 mt-2" id="card-circuit-state">ALL CLOSED</div>
            <div class="text-xs text-slate-400 mt-1">0 tripped / degraded</div>
          </div>

          <div class="glass-card p-5 rounded-2xl">
            <div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider">
              <span>Default Mode</span>
              <span class="text-amber-400 text-base">🎯</span>
            </div>
            <div class="text-3xl font-extrabold text-amber-300 mt-2 font-mono uppercase" id="card-routing-mode">AUTO</div>
            <div class="text-xs text-slate-400 mt-1">Intelligent scoring active</div>
          </div>
        </div>

        <!-- Circuit Breaker Matrix & Provider Status -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <div class="flex items-center justify-between">
              <h3 class="font-bold text-base text-white flex items-center space-x-2">
                <span>🛡️</span> <span>Circuit Breakers & Health</span>
              </h3>
              <button onclick="resetAllBreakers()" class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-indigo-400 rounded-lg border border-slate-700 transition">
                Reset All
              </button>
            </div>
            <div class="space-y-2.5 text-sm" id="breakers-container">
              <div class="text-slate-400 text-xs animate-pulse">Loading circuit breakers...</div>
            </div>
          </div>

          <div class="glass-card p-6 rounded-2xl space-y-4">
            <div class="flex items-center justify-between">
              <h3 class="font-bold text-base text-white flex items-center space-x-2">
                <span>🌐</span> <span>SHIV DB & Infrastructure</span>
              </h3>
              <button onclick="testHealthEndpoint()" class="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-cyan-400 rounded-lg border border-slate-700 transition">
                Ping /v2/health
              </button>
            </div>
            <div class="space-y-3 text-xs font-mono bg-slate-900/80 p-4 rounded-xl border border-slate-800" id="infra-info">
              <div class="flex justify-between">
                <span class="text-slate-400">SHIV DB URL:</span>
                <span class="text-slate-200">https://shiv-database.onrender.com</span>
              </div>
              <div class="flex justify-between">
                <span class="text-slate-400">Project ID:</span>
                <span class="text-slate-200">26d20fcf-5c34-4e6d-ad80-bb89f593e2f5</span>
              </div>
              <div class="flex justify-between">
                <span class="text-slate-400">Auth Signature:</span>
                <span class="text-indigo-400">HS256 Verified</span>
              </div>
              <div class="flex justify-between">
                <span class="text-slate-400">Local Cache:</span>
                <span class="text-emerald-400">SQLite Async aiosqlite</span>
              </div>
              <div class="flex justify-between">
                <span class="text-slate-400">Render Tier:</span>
                <span class="text-emerald-400">Free Tier (Zero Cost)</span>
              </div>
            </div>
            <div id="health-ping-result" class="text-xs font-mono p-3 rounded-lg bg-slate-900 border border-slate-800/80 hidden"></div>
          </div>
        </div>
      </section>

      <!-- =============================================================== -->
      <!-- TAB 2: SETTINGS & MODEL REGISTRY GOVERNANCE -->
      <!-- =============================================================== -->
      <section id="tab-settings" class="space-y-6 hidden">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">Runtime Settings & Model Governance</h2>
          <p class="text-sm text-slate-400 mt-1">Alter router behavior, circuit breaker thresholds, and enable/disable individual AI models instantly.</p>
        </div>

        <!-- Dynamic Settings Form -->
        <div class="glass-card p-6 rounded-2xl space-y-5">
          <h3 class="font-bold text-base text-white">Orchestration & Resilience Tuning</h3>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <label class="block text-xs font-semibold text-slate-400 uppercase mb-1">Default Routing Mode</label>
              <select id="cfg-mode" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
                <option value="auto">auto (Intelligent balance)</option>
                <option value="fastest">fastest (Lowest latency)</option>
                <option value="quality">quality (Highest capability)</option>
                <option value="balanced">balanced (Speed + quality)</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-semibold text-slate-400 uppercase mb-1">Max Retries</label>
              <input type="number" id="cfg-retries" min="0" max="10" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
            </div>

            <div>
              <label class="block text-xs font-semibold text-slate-400 uppercase mb-1">Retry Base Delay (sec)</label>
              <input type="number" id="cfg-retry-delay" step="0.1" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
            </div>

            <div>
              <label class="block text-xs font-semibold text-slate-400 uppercase mb-1">Circuit Breaker Threshold</label>
              <input type="number" id="cfg-cb-thresh" min="1" max="20" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
            </div>

            <div>
              <label class="block text-xs font-semibold text-slate-400 uppercase mb-1">Breaker Recovery Cooldown (sec)</label>
              <input type="number" id="cfg-cb-cooldown" min="5" max="300" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
            </div>

            <div>
              <label class="block text-xs font-semibold text-slate-400 uppercase mb-1">Rate Limit (req/min)</label>
              <input type="number" id="cfg-rate-limit" min="10" max="600" class="w-full bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-indigo-500">
            </div>
          </div>

          <div class="flex justify-end pt-2">
            <button onclick="saveRuntimeSettings()" class="px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-semibold text-sm shadow-lg shadow-indigo-500/20 transition">
              Save Runtime Settings
            </button>
          </div>
        </div>

        <!-- Model Registry Table -->
        <div class="glass-card p-6 rounded-2xl space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="font-bold text-base text-white">Central Model Registry</h3>
            <span class="text-xs text-slate-400">Click toggle switches to dynamically disable/enable any model.</span>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left text-sm border-collapse">
              <thead>
                <tr class="border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase">
                  <th class="py-3 px-4">Status</th>
                  <th class="py-3 px-4">Model ID / Name</th>
                  <th class="py-3 px-4">Provider</th>
                  <th class="py-3 px-4">Speed</th>
                  <th class="py-3 px-4">Quality</th>
                  <th class="py-3 px-4">Cost</th>
                  <th class="py-3 px-4">Priority</th>
                  <th class="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody id="models-table-body" class="divide-y divide-slate-800/60 font-mono text-xs">
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- =============================================================== -->
      <!-- TAB 3: CHAT & ROUTER PLAYGROUND -->
      <!-- =============================================================== -->
      <section id="tab-chat" class="space-y-6 hidden">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">Chat & Intelligent Router Playground</h2>
          <p class="text-sm text-slate-400 mt-1">Test the deterministic scoring engine, streaming output, model fallbacks, and task-complexity routing.</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Controls Panel -->
          <div class="glass-card p-5 rounded-2xl space-y-4">
            <h3 class="font-bold text-sm text-white uppercase tracking-wider">Routing Controls</h3>
            
            <div>
              <label class="block text-xs text-slate-400 mb-1">Routing Mode</label>
              <select id="chat-mode" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200">
                <option value="auto">auto (AI Evaluates Task)</option>
                <option value="fastest">fastest (Groq Llama 3.3)</option>
                <option value="quality">quality (Gemini 2.5 Pro)</option>
                <option value="balanced">balanced (Gemini 2.5 Flash)</option>
                <option value="specific">specific (Explicit Model)</option>
              </select>
            </div>

            <div id="chat-specific-model-wrapper" class="hidden">
              <label class="block text-xs text-slate-400 mb-1">Specific Model</label>
              <select id="chat-specific-model" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200">
                <option value="groq_llama_70b">groq_llama_70b (Llama 3.3 70B)</option>
                <option value="groq_llama_8b">groq_llama_8b (Llama 3.1 8B Fast)</option>
                <option value="gemini_2_5_flash">gemini_2_5_flash (Gemini 2.5 Flash)</option>
                <option value="gemini_2_5_pro">gemini_2_5_pro (Gemini 2.5 Pro)</option>
              </select>
            </div>

            <div class="flex items-center space-x-2 pt-2">
              <input type="checkbox" id="chat-stream-toggle" checked class="rounded bg-slate-900 border-slate-700 text-indigo-600 focus:ring-0">
              <label for="chat-stream-toggle" class="text-xs text-slate-300">Enable SSE Real-Time Streaming</label>
            </div>

            <div>
              <label class="block text-xs text-slate-400 mb-1">System Instructions</label>
              <textarea id="chat-system-prompt" rows="2" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-200 font-mono" placeholder="Default ShivAI persona active..."></textarea>
            </div>

            <button onclick="sendChatMessage()" id="btn-send-chat" class="w-full py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 font-semibold text-white text-sm shadow-lg shadow-indigo-500/20 transition flex items-center justify-center space-x-2">
              <span>Execute AI Request</span> <span>➔</span>
            </button>

            <!-- Execution Meta Info -->
            <div id="chat-meta-box" class="hidden text-[11px] font-mono bg-slate-900/90 p-3 rounded-xl border border-slate-800 space-y-1">
              <div class="text-indigo-400 font-semibold mb-1">⚡ Routing Telemetry</div>
              <div>Model: <span id="meta-model" class="text-white">--</span></div>
              <div>Provider: <span id="meta-provider" class="text-white">--</span></div>
              <div>Latency: <span id="meta-latency" class="text-emerald-400">--</span></div>
              <div>Reason: <span id="meta-reason" class="text-slate-400">--</span></div>
            </div>
          </div>

          <!-- Conversation Display -->
          <div class="lg:col-span-2 glass-card p-5 rounded-2xl flex flex-col h-[560px]">
            <div class="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
              <span class="text-xs font-semibold text-slate-400 uppercase">Live Interaction View</span>
              <button onclick="clearChatLog()" class="text-xs text-slate-400 hover:text-slate-300">Clear</button>
            </div>

            <div id="chat-log" class="flex-1 overflow-y-auto space-y-4 p-2 text-sm font-sans">
              <div class="text-center text-slate-400 text-xs py-10">Send a prompt below to see intelligent model routing in action.</div>
            </div>

            <div class="mt-3 pt-3 border-t border-slate-800 flex space-x-2">
              <input type="text" id="chat-input" onkeydown="if(event.key==='Enter') sendChatMessage()" placeholder="Type a message or programming query..." class="flex-1 bg-slate-900 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500">
              <button onclick="sendChatMessage()" class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-medium transition">Send</button>
            </div>
          </div>
        </div>
      </section>

      <!-- =============================================================== -->
      <!-- TAB 4: VOICE AI TESTER -->
      <!-- =============================================================== -->
      <section id="tab-voice" class="space-y-6 hidden">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">Voice AI Studio (Edge-TTS & Groq Whisper)</h2>
          <p class="text-sm text-slate-400 mt-1">Test real-time neural speech synthesis (Hindi, English, Hinglish) and whisper audio transcription.</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Text to Speech Card -->
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <h3 class="font-bold text-base text-white flex items-center space-x-2">
              <span>🔊</span> <span>Neural TTS Synthesizer (Edge-TTS)</span>
            </h3>

            <div>
              <label class="block text-xs text-slate-400 mb-1">Target Voice</label>
              <select id="tts-voice" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200">
                <option value="hi-IN-SwaraNeural">Hindi Female (hi-IN-SwaraNeural)</option>
                <option value="hi-IN-MadhurNeural">Hindi Male (hi-IN-MadhurNeural)</option>
                <option value="en-IN-NeerjaNeural" selected>Indian English (en-IN-NeerjaNeural)</option>
                <option value="en-IN-PrabhatNeural">Indian English Male (en-IN-PrabhatNeural)</option>
                <option value="en-US-JennyNeural">US English (en-US-JennyNeural)</option>
              </select>
            </div>

            <div>
              <label class="block text-xs text-slate-400 mb-1">Text to Synthesize (Hindi / English / Hinglish)</label>
              <textarea id="tts-text" rows="3" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-sm text-slate-200" placeholder="Namaste! Main ShivAI hoon. Aapki kya madad kar sakta hoon?"></textarea>
            </div>

            <div class="flex items-center space-x-3">
              <button onclick="synthesizeSpeech()" id="btn-tts-speak" class="flex-1 py-3 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 font-semibold text-white rounded-xl text-sm transition shadow-lg shadow-emerald-500/20">
                Generate & Play Audio 🔊
              </button>
            </div>

            <audio id="tts-audio-player" controls class="w-full mt-2 hidden"></audio>
            <div id="tts-status" class="text-xs text-slate-400 font-mono"></div>
          </div>

          <!-- Speech to Text Card -->
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <h3 class="font-bold text-base text-white flex items-center space-x-2">
              <span>🎙️</span> <span>Groq Whisper STT Transcriber</span>
            </h3>
            
            <p class="text-xs text-slate-400">Upload any audio sample (.mp3, .wav, .m4a) to transcribe with whisper-large-v3-turbo.</p>

            <div class="border-2 border-dashed border-slate-700/80 rounded-2xl p-6 text-center space-y-3 bg-slate-900/40">
              <input type="file" id="stt-audio-file" accept="audio/*" class="text-xs text-slate-400">
              <p class="text-[11px] text-slate-400">Maximum file size: 25 MB</p>
            </div>

            <button onclick="transcribeAudio()" id="btn-stt-transcribe" class="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition">
              Transcribe Audio with Whisper
            </button>

            <div>
              <label class="block text-xs text-slate-400 mb-1">Transcription Output</label>
              <div id="stt-output" class="bg-slate-900 p-3.5 rounded-xl border border-slate-800 text-xs font-mono min-h-[90px] text-slate-300">
                Transcription text will appear here...
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- =============================================================== -->
      <!-- TAB 5: AUTONOMOUS RESEARCH ENGINE -->
      <!-- =============================================================== -->
      <section id="tab-research" class="space-y-6 hidden">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">Autonomous Web Research Engine</h2>
          <p class="text-sm text-slate-400 mt-1">Multi-source web search via DuckDuckGo, prompt injection filtering, and automated Markdown citation synthesis.</p>
        </div>

        <div class="glass-card p-6 rounded-2xl space-y-4">
          <div class="flex space-x-3">
            <input type="text" id="research-query" placeholder="e.g. Current status of fusion energy commercialization in 2026" class="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-200 focus:outline-none focus:border-indigo-500">
            <button onclick="runResearch()" id="btn-research" class="px-6 py-3 bg-gradient-to-r from-indigo-600 to-cyan-600 hover:from-indigo-500 hover:to-cyan-500 text-white font-semibold rounded-xl text-sm transition shadow-lg shadow-indigo-500/20">
              Start Research 🔍
            </button>
          </div>

          <div id="research-status-pill" class="text-xs font-mono text-cyan-400 hidden"></div>

          <!-- Results Display -->
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-2">
            <div class="lg:col-span-2 space-y-2">
              <label class="block text-xs font-semibold text-slate-400 uppercase">Synthesized Research Document</label>
              <div id="research-output-content" class="bg-slate-900/90 p-5 rounded-2xl border border-slate-800/80 text-sm leading-relaxed text-slate-200 min-h-[300px] whitespace-pre-wrap font-sans">
                Research findings and synthesized conclusions will appear here...
              </div>
            </div>

            <div class="space-y-2">
              <label class="block text-xs font-semibold text-slate-400 uppercase">Extracted Web Sources & Citations</label>
              <div id="research-sources-list" class="bg-slate-900/90 p-4 rounded-2xl border border-slate-800/80 space-y-3 text-xs font-mono min-h-[300px] overflow-y-auto">
                <div class="text-slate-400 text-center py-8">Sources list will appear here...</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- =============================================================== -->
      <!-- TAB 6: TOOL SANDBOX -->
      <!-- =============================================================== -->
      <section id="tab-tools" class="space-y-6 hidden">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">Tool Sandbox & Code Execution</h2>
          <p class="text-sm text-slate-400 mt-1">Execute Python scripts in a hardened subprocess sandbox with strict 5-second limits, or invoke built-in tools.</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Python Sandbox Card -->
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <div class="flex items-center justify-between">
              <h3 class="font-bold text-sm text-white flex items-center space-x-2">
                <span>🐍</span> <span>Sandboxed Python Execution</span>
              </h3>
              <span class="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">5s Max Timeout</span>
            </div>

            <textarea id="sandbox-code" rows="8" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs font-mono text-emerald-400" placeholder="# Enter Python code to execute safely
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
squares = [x**2 for x in numbers]
print(f'Calculated sum of squares: {sum(squares)}')">numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
squares = [x**2 for x in numbers]
print(f'Calculated sum of squares: {sum(squares)}')</textarea>

            <button onclick="executeSandboxCode()" id="btn-run-sandbox" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-sm font-semibold transition">
              Run Code in Sandbox ➔
            </button>

            <div>
              <label class="block text-xs text-slate-400 mb-1">Sandbox Console Output</label>
              <div id="sandbox-result" class="bg-slate-950 p-4 rounded-xl border border-slate-800/80 text-xs font-mono min-h-[90px] whitespace-pre-wrap text-slate-300">
                Output will appear here...
              </div>
            </div>
          </div>

          <!-- Builtin Tool Tester -->
          <div class="glass-card p-6 rounded-2xl space-y-4">
            <h3 class="font-bold text-sm text-white flex items-center space-x-2">
              <span>🛠️</span> <span>Built-in Tool Invocations</span>
            </h3>

            <div>
              <label class="block text-xs text-slate-400 mb-1">Select Tool</label>
              <select id="tool-select" onchange="updateToolArgsSample()" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200">
                <option value="calculator">calculator (Safe Math Expression)</option>
                <option value="datetime">datetime (Current Timestamp & Timezones)</option>
                <option value="web_search">web_search (DuckDuckGo Search)</option>
              </select>
            </div>

            <div>
              <label class="block text-xs text-slate-400 mb-1">Tool Arguments (JSON)</label>
              <textarea id="tool-args" rows="4" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs font-mono text-slate-200">{"expression": "sqrt(144) + 25 * 4"}</textarea>
            </div>

            <button onclick="executeBuiltinTool()" id="btn-run-tool" class="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition">
              Execute Tool
            </button>

            <div>
              <label class="block text-xs text-slate-400 mb-1">Tool Response</label>
              <div id="tool-result" class="bg-slate-900 p-4 rounded-xl border border-slate-800/80 text-xs font-mono min-h-[90px] text-slate-300">
                Result will appear here...
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- =============================================================== -->
      <!-- TAB 7: MULTI-AGENT ORCHESTRATION -->
      <!-- =============================================================== -->
      <section id="tab-agents" class="space-y-6 hidden">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">Multi-Agent Task Orchestrator (DAG)</h2>
          <p class="text-sm text-slate-400 mt-1">Decompose complex goals into subtasks executed collaboratively by Planner, Researcher, Engineer, and Writer.</p>
        </div>

        <div class="glass-card p-6 rounded-2xl space-y-4">
          <div>
            <label class="block text-xs text-slate-400 mb-1">High-Level Objective / Mission</label>
            <textarea id="agent-goal" rows="2" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-sm text-slate-200" placeholder="e.g. Design a high-concurrency event-driven notification architecture for 10 million users"></textarea>
          </div>

          <div class="flex items-center space-x-4 text-xs text-slate-300">
            <span class="text-slate-400 font-semibold uppercase">Agent Team:</span>
            <label class="flex items-center space-x-1.5"><input type="checkbox" id="role-planner" checked class="rounded bg-slate-900"> <span>Planner</span></label>
            <label class="flex items-center space-x-1.5"><input type="checkbox" id="role-researcher" checked class="rounded bg-slate-900"> <span>Researcher</span></label>
            <label class="flex items-center space-x-1.5"><input type="checkbox" id="role-engineer" checked class="rounded bg-slate-900"> <span>Engineer</span></label>
            <label class="flex items-center space-x-1.5"><input type="checkbox" id="role-writer" checked class="rounded bg-slate-900"> <span>Writer</span></label>
          </div>

          <button onclick="runMultiAgentTask()" id="btn-run-agent" class="py-3 px-6 bg-gradient-to-r from-indigo-600 via-indigo-500 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white font-semibold rounded-xl text-sm transition shadow-lg shadow-indigo-500/20">
            Execute Multi-Agent Mission ➔
          </button>

          <div id="agent-pipeline-view" class="space-y-3 pt-3">
            <div class="text-xs text-slate-400">Agent subtask outputs and final synthesis will appear here.</div>
          </div>
        </div>
      </section>

      <!-- =============================================================== -->
      <!-- TAB 8: DOCUMENTS & MULTIMODAL -->
      <!-- =============================================================== -->
      <section id="tab-documents" class="space-y-6 hidden">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">Document Ingestion & Multimodal QA</h2>
          <p class="text-sm text-slate-400 mt-1">Upload PDF or image files to extract content, perform Gemini Vision OCR, and query with AI context.</p>
        </div>

        <div class="glass-card p-6 rounded-2xl space-y-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs text-slate-400 mb-1">Upload File (PDF or Image)</label>
              <input type="file" id="doc-file-input" accept=".pdf,image/*" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-300">
            </div>
            <div>
              <label class="block text-xs text-slate-400 mb-1">Instruction / Query</label>
              <input type="text" id="doc-query-input" placeholder="Summarize key architectural takeaways" value="Summarize key architectural takeaways" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-xs text-slate-200">
            </div>
          </div>

          <button onclick="analyzeDocument()" id="btn-analyze-doc" class="py-2.5 px-6 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition">
            Analyze Document
          </button>

          <div id="doc-analysis-result" class="bg-slate-900 p-4 rounded-xl border border-slate-800 text-xs font-mono min-h-[160px] whitespace-pre-wrap text-slate-300">
            Document analysis findings will appear here...
          </div>
        </div>
      </section>

      <!-- =============================================================== -->
      <!-- TAB 9: MEMORY & IDENTITY INSPECTOR -->
      <!-- =============================================================== -->
      <section id="tab-memory" class="space-y-6 hidden">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">Hierarchical Memory & Identity Inspector</h2>
          <p class="text-sm text-slate-400 mt-1">Inspect persistent facts stored for the user and verify automated sensitive data redactor filters.</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div class="glass-card p-5 rounded-2xl space-y-3">
            <h3 class="font-bold text-sm text-white">Add User Fact / Memory</h3>
            <div>
              <label class="block text-xs text-slate-400 mb-1">Memory Type</label>
              <select id="mem-type" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200">
                <option value="user_preference">User Preference</option>
                <option value="project_context">Project Context</option>
                <option value="learned_fact">Learned Fact</option>
              </select>
            </div>

            <div>
              <label class="block text-xs text-slate-400 mb-1">Memory Content</label>
              <textarea id="mem-content" rows="3" placeholder="e.g. User prefers concise Python with strict type hinting" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs text-slate-200"></textarea>
            </div>

            <button onclick="addMemoryRecord()" class="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition">
              Store Memory
            </button>
          </div>

          <div class="lg:col-span-2 glass-card p-5 rounded-2xl space-y-3">
            <div class="flex items-center justify-between">
              <h3 class="font-bold text-sm text-white">Stored Memories</h3>
              <button onclick="loadUserMemories()" class="text-xs text-indigo-400 hover:underline">Refresh</button>
            </div>

            <div id="memories-list" class="space-y-2 text-xs font-mono max-h-[360px] overflow-y-auto">
            </div>
          </div>
        </div>
      </section>

      <!-- =============================================================== -->
      <!-- TAB 10: FREE MULTIMODAL MEDIA STUDIO -->
      <!-- =============================================================== -->
      <section id="tab-media" class="hidden space-y-6">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">Free Multimodal Studio (Images, Videos & Audio)</h2>
          <p class="text-sm text-slate-400 mt-1">Generate high-resolution photorealistic images, short video animations, and neural audio 100% free with zero GPU overhead.</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- Card 1: Text-to-Image -->
          <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
            <div class="flex items-center space-x-2 text-indigo-400 font-bold text-sm">
              <span>🖼️</span> <span>Text-to-Image (FLUX.1 Schnell)</span>
            </div>
            <div>
              <label class="block text-xs text-slate-400 mb-1">Image Prompt</label>
              <textarea id="media-img-prompt" rows="3" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200" placeholder="A futuristic city in the Himalayas at sunrise, cyberpunk aesthetics, volumetric lighting, photorealistic 8k"></textarea>
            </div>
            <div class="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label class="block text-slate-400 mb-1">Model Variant</label>
                <select id="media-img-model" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-300">
                  <option value="flux">FLUX.1 Schnell (Highest Quality)</option>
                  <option value="turbo">SDXL Turbo (Fastest)</option>
                  <option value="flux-realism">FLUX Realism</option>
                  <option value="flux-anime">FLUX Anime</option>
                </select>
              </div>
              <div>
                <label class="block text-slate-400 mb-1">Dimensions</label>
                <select id="media-img-size" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-300">
                  <option value="1024x1024">Square (1024 x 1024)</option>
                  <option value="1280x720">Landscape (1280 x 720)</option>
                  <option value="720x1280">Portrait (720 x 1280)</option>
                </select>
              </div>
            </div>
            <button onclick="generateStudioImage()" id="btn-gen-img" class="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition">
              Generate Image ✨
            </button>
            <div id="media-img-preview" class="min-h-[220px] bg-slate-950 rounded-xl border border-slate-800/80 flex items-center justify-center overflow-hidden p-2">
              <span class="text-xs text-slate-500">Generated image will appear here</span>
            </div>
          </div>

          <!-- Card 2: Text-to-Video & Speech -->
          <div class="space-y-6">
            <!-- Text-to-Video -->
            <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
              <div class="flex items-center space-x-2 text-cyan-400 font-bold text-sm">
                <span>🎬</span> <span>Text-to-Video / Animation</span>
              </div>
              <div>
                <label class="block text-xs text-slate-400 mb-1">Video Prompt</label>
                <input id="media-vid-prompt" type="text" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200" placeholder="A golden eagle soaring over snow-capped mountains in slow motion">
              </div>
              <button onclick="generateStudioVideo()" id="btn-gen-vid" class="w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl text-sm font-semibold transition">
                Generate Video Clip 🎥
              </button>
              <div id="media-vid-preview" class="min-h-[160px] bg-slate-950 rounded-xl border border-slate-800/80 flex items-center justify-center overflow-hidden p-2">
                <span class="text-xs text-slate-500">Generated video will appear here</span>
              </div>
            </div>

            <!-- Neural Audio Speech -->
            <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
              <div class="flex items-center space-x-2 text-emerald-400 font-bold text-sm">
                <span>🔊</span> <span>Neural Voice Synthesis (Edge-TTS)</span>
              </div>
              <div>
                <label class="block text-xs text-slate-400 mb-1">Text to Speak (Hindi / English / Hinglish)</label>
                <input id="media-tts-text" type="text" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200" value="नमस्ते, शिव एआई वी२ में आपका स्वागत है।">
              </div>
              <div class="flex space-x-3 text-xs">
                <select id="media-tts-voice" class="flex-1 bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-300">
                  <option value="hi-IN-SwaraNeural">Swara (Hindi Female - Natural)</option>
                  <option value="hi-IN-MadhurNeural">Madhur (Hindi Male)</option>
                  <option value="en-IN-NeerjaNeural">Neerja (Indian English Female)</option>
                  <option value="en-IN-PrabhatNeural">Prabhat (Indian English Male)</option>
                  <option value="en-US-JennyNeural">Jenny (US English)</option>
                </select>
                <button onclick="generateStudioSpeech()" class="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-sm font-semibold transition">
                  Speak 🗣️
                </button>
              </div>
              <audio id="media-audio-player" controls class="w-full hidden mt-2"></audio>
            </div>
          </div>
        </div>
      </section>

      <!-- Section: Intent & DAG Planner -->
      <section id="tab-orchestrator" class="hidden space-y-6">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">Universal Intent & DAG Task Planner</h2>
          <p class="text-sm text-slate-400 mt-1">Classify complex multimodal requests across 17 domains and synthesize dependency-aware execution plans.</p>
        </div>

        <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
          <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider">User Goal or Complex Task Prompt</label>
          <div class="flex space-x-3">
            <input type="text" id="orch-prompt" class="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-200"
                   placeholder="e.g. Build a 2D neon space shooter arcade game with touch controls, audio, and high score"
                   value="Build a full-stack SaaS application with FastAPI, SQLite, and responsive Tailwind UI">
            <button onclick="analyzeOrchestration()" class="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 font-semibold text-white rounded-xl text-sm transition">
              Deconstruct & Plan 🎯
            </button>
          </div>

          <div id="orch-results" class="hidden space-y-6 pt-4 border-t border-slate-800/60">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
                <span class="text-xs text-slate-400 block mb-1">Primary Intent</span>
                <span class="text-base font-bold text-indigo-400" id="orch-primary">-</span>
              </div>
              <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
                <span class="text-xs text-slate-400 block mb-1">Confidence Score</span>
                <span class="text-base font-bold text-emerald-400" id="orch-confidence">-</span>
              </div>
              <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
                <span class="text-xs text-slate-400 block mb-1">Assigned Lead Agent</span>
                <span class="text-base font-bold text-cyan-400" id="orch-agent">-</span>
              </div>
            </div>

            <div>
              <h3 class="text-sm font-bold text-white mb-3">Synthesized DAG Execution Steps</h3>
              <div id="orch-steps-list" class="space-y-3"></div>
            </div>
          </div>
        </div>
      </section>

      <!-- Section: Creative & Dev Studios -->
      <section id="tab-studios" class="hidden space-y-6">
        <div>
          <h2 class="text-2xl font-bold tracking-tight text-white">Creative & Development Studios</h2>
          <p class="text-sm text-slate-400 mt-1">Instant generation sandboxes for 2D Design, 3D Assets, Browser Games, and Full-Stack Web Applications.</p>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <!-- 1. 2D Design Studio -->
          <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
            <div class="flex items-center space-x-2 text-cyan-400 font-bold text-sm">
              <span>🎨</span> <span>2D Layered Design Studio</span>
            </div>
            <div class="space-y-3 text-xs">
              <div>
                <label class="block text-slate-400 mb-1">Design Headline</label>
                <input type="text" id="studio-design-headline" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-slate-200" value="ShivAI Next-Gen Multimodal Architecture">
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-slate-400 mb-1">Preset Format</label>
                  <select id="studio-design-preset" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-300">
                    <option value="social_banner">Social Banner (1200x630)</option>
                    <option value="square_post">Square Post (1080x1080)</option>
                    <option value="youtube_thumbnail">YouTube Thumbnail (1280x720)</option>
                  </select>
                </div>
                <div>
                  <label class="block text-slate-400 mb-1">Background Color</label>
                  <input type="text" id="studio-design-bg" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-200" value="#0F172A">
                </div>
              </div>
              <button onclick="renderStudioDesign()" class="w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl font-semibold transition">
                Render Vector SVG Canvas 🖼️
              </button>
            </div>
            <div id="studio-design-preview" class="border border-slate-800 rounded-xl p-2 bg-slate-950/80 flex items-center justify-center min-h-[160px] overflow-hidden">
              <span class="text-xs text-slate-500 italic">Rendered SVG canvas will appear here</span>
            </div>
          </div>

          <!-- 2. 3D Asset Studio -->
          <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
            <div class="flex items-center space-x-2 text-purple-400 font-bold text-sm">
              <span>🧊</span> <span>3D Procedural Asset Studio</span>
            </div>
            <div class="space-y-3 text-xs">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-slate-400 mb-1">Procedural Mesh</label>
                  <select id="studio-3d-mesh" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-300">
                    <option value="cube">Cube (Sharp Normals)</option>
                    <option value="sphere">UV Sphere (Smooth)</option>
                    <option value="cylinder">Cylinder (Parametric)</option>
                  </select>
                </div>
                <div>
                  <label class="block text-slate-400 mb-1">PBR Albedo Color</label>
                  <input type="text" id="studio-3d-color" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-200" value="#38BDF8">
                </div>
              </div>
              <button onclick="renderStudio3D()" class="w-full py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl font-semibold transition">
                Synthesize 3D Mesh & Viewport 🧊
              </button>
            </div>
            <div id="studio-3d-preview" class="border border-slate-800 rounded-xl overflow-hidden min-h-[160px] bg-slate-950 flex items-center justify-center">
              <span class="text-xs text-slate-500 italic">3D WebGL interactive viewport will render here</span>
            </div>
          </div>

          <!-- 3. Game Studio -->
          <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
            <div class="flex items-center space-x-2 text-rose-400 font-bold text-sm">
              <span>🎮</span> <span>Game Development Studio</span>
            </div>
            <div class="space-y-3 text-xs">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-slate-400 mb-1">Game Title</label>
                  <input type="text" id="studio-game-title" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-200" value="Cyber Orbit Runner">
                </div>
                <div>
                  <label class="block text-slate-400 mb-1">Game Engine</label>
                  <select id="studio-game-type" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-300">
                    <option value="2d">2D HTML5 Canvas + Web Audio</option>
                    <option value="3d">3D WebGL Three.js Arena</option>
                  </select>
                </div>
              </div>
              <button onclick="renderStudioGame()" class="w-full py-2.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl font-semibold transition">
                Generate & Launch Playable Game 🕹️
              </button>
            </div>
            <div id="studio-game-preview" class="border border-slate-800 rounded-xl overflow-hidden min-h-[200px] bg-slate-950 flex items-center justify-center">
              <span class="text-xs text-slate-500 italic">Playable standalone game will run inside this container</span>
            </div>
          </div>

          <!-- 4. Full-Stack App Builder -->
          <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
            <div class="flex items-center space-x-2 text-amber-400 font-bold text-sm">
              <span>📦</span> <span>Full-Stack App Builder</span>
            </div>
            <div class="space-y-3 text-xs">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-slate-400 mb-1">Application Name</label>
                  <input type="text" id="studio-app-name" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-200" value="QuickTask Pro">
                </div>
                <div>
                  <label class="block text-slate-400 mb-1">Primary Entity</label>
                  <input type="text" id="studio-app-entity" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-200" value="Task">
                </div>
              </div>
              <button onclick="bundleStudioApp()" class="w-full py-2.5 bg-amber-600 hover:bg-amber-500 text-white rounded-xl font-semibold transition">
                Generate & Package Full-Stack App ZIP 🚀
              </button>
            </div>
            <div id="studio-app-preview" class="border border-slate-800 rounded-xl p-4 bg-slate-950/80 min-h-[160px] text-xs space-y-2">
              <span class="text-slate-500 italic block">Multi-tier FastAPI + Tailwind project manifest and ZIP download will appear here</span>
            </div>
          </div>
        </div>
      </section>

      <!-- Section: Background Jobs -->
      <section id="tab-jobs" class="hidden space-y-6">
        <div class="flex justify-between items-center">
          <div>
            <h2 class="text-2xl font-bold tracking-tight text-white">Background Job Queue</h2>
            <p class="text-sm text-slate-400 mt-1">Monitor prioritized task processing, worker states, and downloadable artifacts.</p>
          </div>
          <button onclick="loadBackgroundJobs()" class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold transition">
            Refresh Jobs 🔄
          </button>
        </div>

        <div class="rounded-2xl glass border border-slate-800/80 overflow-hidden">
          <table class="w-full text-left text-xs text-slate-300">
            <thead class="bg-slate-900/80 text-slate-400 border-b border-slate-800/80">
              <tr>
                <th class="p-3.5">Job ID</th>
                <th class="p-3.5">Type</th>
                <th class="p-3.5">Priority</th>
                <th class="p-3.5">Status</th>
                <th class="p-3.5">Progress</th>
                <th class="p-3.5">Artifacts</th>
              </tr>
            </thead>
            <tbody id="jobs-table-body" class="divide-y divide-slate-800/40">
              <tr>
                <td colspan="6" class="p-4 text-center text-slate-500 italic">No background jobs active</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Section: Devices & Automation Operator -->
      <section id="tab-devices" class="hidden space-y-6">
        <div class="flex justify-between items-center">
          <div>
            <h2 class="text-2xl font-bold tracking-tight text-white">Universal Device Operator & Work Automation</h2>
            <p class="text-sm text-slate-400 mt-1">Permission-governed digital execution across Windows, Android, Browser, and Workplace APIs.</p>
          </div>
          <div class="flex items-center space-x-3">
            <button onclick="loadDevicesDashboard()" class="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold transition">
              Refresh Telemetry 🔄
            </button>
            <button id="btn-emergency-stop" onclick="triggerEmergencyStopUI()" class="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-bold transition shadow-lg shadow-rose-900/40 flex items-center space-x-2">
              <span>🛑</span> <span>EMERGENCY STOP</span>
            </button>
            <button id="btn-emergency-reset" onclick="resetEmergencyStopUI()" class="hidden px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition">
              Reset Emergency Stop 🟢
            </button>
          </div>
        </div>

        <!-- Emergency Status Banner -->
        <div id="device-emergency-alert" class="hidden p-4 rounded-2xl bg-rose-950/80 border border-rose-800/80 text-rose-200 text-xs flex items-center justify-between">
          <div class="flex items-center space-x-3">
            <span class="text-2xl">⚠️</span>
            <div>
              <span class="font-bold uppercase tracking-wider block">System Kill Switch Active</span>
              <span id="device-emergency-reason" class="text-rose-300">All device automation and external actions are locked.</span>
            </div>
          </div>
        </div>

        <!-- 2-Column Grid -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

          <!-- Left Column: Devices & Observation -->
          <div class="space-y-6">
            <!-- Connected Devices Card -->
            <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-2 text-indigo-400 font-bold text-sm">
                  <span>📱</span> <span>Enrolled & Paired Devices</span>
                </div>
                <button onclick="requestDevicePairingUI()" class="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-[11px] font-semibold transition">
                  + Pair Device
                </button>
              </div>

              <div id="pairing-code-banner" class="hidden p-3 rounded-xl bg-indigo-950/60 border border-indigo-800 text-xs text-indigo-200 flex justify-between items-center">
                <span>Pairing Code: <strong id="pairing-code-display" class="text-base text-white font-mono ml-2">--</strong></span>
                <span class="text-[10px] text-indigo-400">Expires in 5m</span>
              </div>

              <div class="rounded-xl overflow-hidden border border-slate-800">
                <table class="w-full text-left text-xs text-slate-300">
                  <thead class="bg-slate-900/80 text-slate-400 border-b border-slate-800">
                    <tr>
                      <th class="p-2.5">Name</th>
                      <th class="p-2.5">Type</th>
                      <th class="p-2.5">Status</th>
                      <th class="p-2.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody id="devices-table-body" class="divide-y divide-slate-800/40">
                    <tr><td colspan="4" class="p-3 text-center text-slate-500 italic">Loading devices...</td></tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Active Window & Screen Observation -->
            <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-2 text-cyan-400 font-bold text-sm">
                  <span>🖥️</span> <span>Foreground Window & UI Observation</span>
                </div>
                <button onclick="observeHostDeviceUI()" class="px-2.5 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-[11px] font-semibold transition">
                  Capture State 👁️
                </button>
              </div>

              <div id="observation-result" class="space-y-2 text-xs">
                <div class="p-3 rounded-xl bg-slate-950 border border-slate-800/80 font-mono space-y-1">
                  <div><span class="text-slate-500">Active Window:</span> <span id="obs-window-title" class="text-slate-200">--</span></div>
                  <div><span class="text-slate-500">Process Name:</span> <span id="obs-process-name" class="text-cyan-400">--</span> <span class="text-slate-600">(PID: <span id="obs-pid">--</span>)</span></div>
                  <div><span class="text-slate-500">Window Bounds:</span> <span id="obs-bounds" class="text-slate-400">--</span></div>
                  <div><span class="text-slate-500">Sanitized Secrets:</span> <span id="obs-redacted" class="text-emerald-400">0</span></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Right Column: Approvals Inbox & 3-Tier Policy Engine -->
          <div class="space-y-6">
            <!-- Pending Approvals Inbox -->
            <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-2 text-amber-400 font-bold text-sm">
                  <span>🛡️</span> <span>3-Tier Policy Approvals Inbox</span>
                </div>
                <span id="pending-approvals-badge" class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-950 text-amber-400 border border-amber-800">0 PENDING</span>
              </div>

              <div id="approvals-inbox-list" class="space-y-3 text-xs max-h-[220px] overflow-y-auto">
                <div class="p-4 text-center text-slate-500 italic">No consequential actions pending human approval.</div>
              </div>
            </div>

            <!-- Action Policy Simulator -->
            <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
              <div class="flex items-center space-x-2 text-purple-400 font-bold text-sm">
                <span>🧪</span> <span>Action Policy Simulator</span>
              </div>
              <div class="space-y-3 text-xs">
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="block text-slate-400 mb-1">Target Action</label>
                    <select id="sim-action-type" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-300">
                      <option value="observe_state">Category A: Observe Window State (Low Risk)</option>
                      <option value="launch_app">Category A: Launch App (Local Workspace)</option>
                      <option value="publish_post">Category B: Publish Social Post (Consequential)</option>
                      <option value="send_email">Category B: Send Email to Client (Consequential)</option>
                      <option value="submit_form">Category C: Bank Transfer / Payment Form (Sensitive)</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-slate-400 mb-1">Target Device / App</label>
                    <input type="text" id="sim-target-app" class="w-full bg-slate-950 border border-slate-800 rounded-xl p-2 text-slate-200" value="host-local-primary">
                  </div>
                </div>
                <button onclick="simulateDeviceAction()" class="w-full py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl font-semibold transition">
                  Dispatch Action Through Policy Engine 🛡️
                </button>
                <div id="sim-result-box" class="hidden p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-[11px] text-slate-300 whitespace-pre-wrap max-h-36 overflow-y-auto"></div>
              </div>
            </div>

            <!-- Recurring Automation Schedules -->
            <div class="p-6 rounded-2xl glass border border-slate-800/80 space-y-4">
              <div class="flex items-center space-x-2 text-emerald-400 font-bold text-sm">
                <span>⏱️</span> <span>Background Recurring Automations</span>
              </div>
              <div id="schedules-list" class="space-y-2 text-xs">
                <div class="p-3 text-center text-slate-500 italic">Loading schedules...</div>
              </div>
            </div>

          </div>
        </div>
      </section>


    </main>
  </div>

  <!-- Global Notification Banner -->
  <div id="toast-banner" class="fixed bottom-6 right-6 z-50 transform translate-y-20 opacity-0 transition-all duration-300 pointer-events-none px-4 py-3 rounded-xl text-xs font-semibold shadow-2xl glass border border-slate-700 flex items-center space-x-2">
    <span id="toast-icon">ℹ️</span>
    <span id="toast-msg">Notification message</span>
  </div>

  <!-- Client-side Logic -->
  <script>
    let activeTab = 'overview';
    let currentApiKey = localStorage.getItem('shivai_api_key') || 'shivai-production-key-2026';
    document.getElementById('auth-key-input').value = currentApiKey;

    function saveApiKey() {
      const val = document.getElementById('auth-key-input').value.trim();
      currentApiKey = val;
      localStorage.setItem('shivai_api_key', val);
      showToast('API Key updated successfully', 'success');
      refreshAllData();
    }

    function showToast(msg, type = 'info') {
      const banner = document.getElementById('toast-banner');
      const msgEl = document.getElementById('toast-msg');
      const iconEl = document.getElementById('toast-icon');
      msgEl.innerText = msg;
      iconEl.innerText = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
      banner.classList.remove('translate-y-20', 'opacity-0');
      setTimeout(() => {
        banner.classList.add('translate-y-20', 'opacity-0');
      }, 3500);
    }

    function switchTab(tabId) {
      document.querySelectorAll('main > section').forEach(sec => sec.classList.add('hidden'));
      document.querySelectorAll('aside button').forEach(btn => {
        btn.classList.remove('tab-active');
        btn.classList.add('text-slate-400');
      });

      document.getElementById('tab-' + tabId).classList.remove('hidden');
      const btn = document.getElementById('tab-btn-' + tabId);
      if (btn) {
        btn.classList.add('tab-active');
        btn.classList.remove('text-slate-400');
      }
      activeTab = tabId;

      if (tabId === 'memory') loadUserMemories();
      if (tabId === 'jobs') loadBackgroundJobs();
      if (tabId === 'devices') loadDevicesDashboard();
      if (tabId === 'overview' || tabId === 'settings') refreshAllData();
    }


    async function apiRequest(endpoint, method = 'GET', body = null) {
      const headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + currentApiKey
      };
      if (body && !(body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
      }

      const opts = { method, headers };
      if (body) {
        opts.body = (body instanceof FormData) ? body : JSON.stringify(body);
      }

      const res = await fetch(endpoint, opts);
      if (!res.ok) {
        let errDetail = 'Request failed (' + res.status + ')';
        try {
          const errJson = await res.json();
          errDetail = errJson.detail?.message || errJson.error?.message || JSON.stringify(errJson);
        } catch(e) {}
        throw new Error(errDetail);
      }
      return await res.json();
    }

    // Refresh telemetry and settings
    async function refreshAllData() {
      try {
        const data = await apiRequest('/v2/admin/config');
        if (data && data.status === 'success') {
          // Cards
          document.getElementById('card-active-models').innerText = data.models.filter(m => m.enabled).length + ' / ' + data.models.length;
          
          let configuredCount = 0;
          for (let p in data.providers) {
            if (data.providers[p].configured) configuredCount++;
          }
          document.getElementById('card-active-providers').innerText = configuredCount + ' Ready';
          document.getElementById('card-routing-mode').innerText = data.settings.router_default_mode;
          document.getElementById('stat-env').innerText = data.settings.env;
          document.getElementById('stat-port').innerText = data.settings.port;

          // Form fields
          document.getElementById('cfg-mode').value = data.settings.router_default_mode;
          document.getElementById('cfg-retries').value = data.settings.router_max_retries;
          document.getElementById('cfg-retry-delay').value = data.settings.retry_base_delay_seconds;
          document.getElementById('cfg-cb-thresh').value = data.settings.circuit_breaker_threshold;
          document.getElementById('cfg-cb-cooldown').value = data.settings.circuit_breaker_recovery_seconds;
          document.getElementById('cfg-rate-limit').value = data.settings.rate_limit_per_minute;

          // Circuit breakers list
          let cbHtml = '';
          let anyOpen = false;
          for (let prov in data.circuit_breakers) {
            const b = data.circuit_breakers[prov];
            const isOpen = b.state === 'OPEN';
            if (isOpen) anyOpen = true;
            cbHtml += `
              <div class="flex items-center justify-between p-3 rounded-xl bg-slate-900 border border-slate-800">
                <div class="flex items-center space-x-2.5">
                  <span class="w-2.5 h-2.5 rounded-full ${isOpen ? 'bg-rose-500 animate-pulse' : 'bg-emerald-400'}"></span>
                  <span class="font-bold uppercase text-slate-200 text-xs">${prov}</span>
                </div>
                <div class="flex items-center space-x-4 text-xs font-mono">
                  <span class="${isOpen ? 'text-rose-400 font-bold' : 'text-slate-400'}">State: ${b.state}</span>
                  <span class="text-slate-400">Failures: ${b.failure_count}/${b.threshold}</span>
                  ${isOpen ? `<button onclick="resetBreaker('${prov}')" class="px-2 py-0.5 bg-rose-500/20 text-rose-300 rounded border border-rose-500/30 text-[10px]">Reset</button>` : ''}
                </div>
              </div>
            `;
          }
          document.getElementById('breakers-container').innerHTML = cbHtml;
          document.getElementById('card-circuit-state').innerText = anyOpen ? 'DEGRADED' : 'ALL CLOSED';
          document.getElementById('card-circuit-state').className = anyOpen ? 'text-3xl font-extrabold text-rose-500 mt-2' : 'text-3xl font-extrabold text-cyan-400 mt-2';

          // Model table
          let modelRows = '';
          data.models.forEach(m => {
            modelRows += `
              <tr class="hover:bg-slate-900/60 transition">
                <td class="py-3 px-4">
                  <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold ${m.enabled ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'}">
                    ${m.enabled ? 'ACTIVE' : 'DISABLED'}
                  </span>
                </td>
                <td class="py-3 px-4 font-semibold text-white">${m.display_name || m.model_name} <div class="text-[10px] text-slate-400 font-normal">${m.model_id}</div></td>
                <td class="py-3 px-4 uppercase text-slate-300">${m.provider}</td>
                <td class="py-3 px-4 text-cyan-400">${m.speed_score}</td>
                <td class="py-3 px-4 text-indigo-400">${m.quality_score}</td>
                <td class="py-3 px-4 text-emerald-400">${m.cost_score}</td>
                <td class="py-3 px-4 text-amber-400">${m.priority}</td>
                <td class="py-3 px-4 text-right">
                  <button onclick="toggleModel('${m.model_id}', ${!m.enabled})" class="px-2.5 py-1 text-[11px] rounded-lg ${m.enabled ? 'bg-slate-800 text-rose-400 hover:bg-rose-500/20' : 'bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30'} border border-slate-700 transition">
                    ${m.enabled ? 'Disable' : 'Enable'}
                  </button>
                </td>
              </tr>
            `;
          });
          document.getElementById('models-table-body').innerHTML = modelRows;
        }
      } catch (err) {
        showToast(err.message, 'error');
      }
    }

    async function saveRuntimeSettings() {
      try {
        const payload = {
          router_default_mode: document.getElementById('cfg-mode').value,
          router_max_retries: parseInt(document.getElementById('cfg-retries').value),
          retry_base_delay_seconds: parseFloat(document.getElementById('cfg-retry-delay').value),
          circuit_breaker_threshold: parseInt(document.getElementById('cfg-cb-thresh').value),
          circuit_breaker_recovery_seconds: parseFloat(document.getElementById('cfg-cb-cooldown').value),
          rate_limit_per_minute: parseInt(document.getElementById('cfg-rate-limit').value)
        };
        const res = await apiRequest('/v2/admin/config', 'POST', payload);
        showToast(res.message, 'success');
        refreshAllData();
      } catch (err) {
        showToast(err.message, 'error');
      }
    }

    async function toggleModel(modelId, targetState) {
      try {
        await apiRequest('/v2/admin/models/' + modelId, 'POST', { enabled: targetState });
        showToast(`Model ${modelId} ${targetState ? 'enabled' : 'disabled'}`, 'success');
        refreshAllData();
      } catch (err) {
        showToast(err.message, 'error');
      }
    }

    async function resetBreaker(provider) {
      try {
        await apiRequest('/v2/admin/circuit-breaker/reset?provider=' + provider, 'POST');
        showToast(`Circuit breaker for ${provider} reset`, 'success');
        refreshAllData();
      } catch (err) {
        showToast(err.message, 'error');
      }
    }

    async function resetAllBreakers() {
      try {
        await apiRequest('/v2/admin/circuit-breaker/reset', 'POST');
        showToast('All circuit breakers reset to CLOSED', 'success');
        refreshAllData();
      } catch (err) {
        showToast(err.message, 'error');
      }
    }

    async function testHealthEndpoint() {
      const box = document.getElementById('health-ping-result');
      box.classList.remove('hidden');
      box.innerText = 'Pinging /v2/health...';
      try {
        const start = Date.now();
        const res = await apiRequest('/v2/health');
        const ms = Date.now() - start;
        box.innerText = `Ping OK (${ms}ms):\\n` + JSON.stringify(res, null, 2);
      } catch (e) {
        box.innerText = 'Error: ' + e.message;
      }
    }

    // Chat Playground
    document.getElementById('chat-mode').addEventListener('change', (e) => {
      const wrap = document.getElementById('chat-specific-model-wrapper');
      wrap.classList.toggle('hidden', e.target.value !== 'specific');
    });

    async function sendChatMessage() {
      const input = document.getElementById('chat-input');
      const text = input.value.trim();
      if (!text) return;

      input.value = '';
      const chatLog = document.getElementById('chat-log');

      // Append user bubble
      const userBubble = document.createElement('div');
      userBubble.className = 'flex justify-end';
      userBubble.innerHTML = `<div class="bg-indigo-600 text-white px-4 py-2.5 rounded-2xl max-w-[80%] text-sm">${escapeHtml(text)}</div>`;
      chatLog.appendChild(userBubble);
      chatLog.scrollTop = chatLog.scrollHeight;

      // Assistant placeholder
      const aiBubble = document.createElement('div');
      aiBubble.className = 'flex justify-start';
      const aiContent = document.createElement('div');
      aiContent.className = 'bg-slate-900 border border-slate-800 text-slate-200 px-4 py-2.5 rounded-2xl max-w-[85%] text-sm whitespace-pre-wrap';
      aiContent.innerText = 'Thinking...';
      aiBubble.appendChild(aiContent);
      chatLog.appendChild(aiBubble);
      chatLog.scrollTop = chatLog.scrollHeight;

      const mode = document.getElementById('chat-mode').value;
      const isStream = document.getElementById('chat-stream-toggle').checked;
      const specificModel = (mode === 'specific') ? document.getElementById('chat-specific-model').value : null;
      const sysPrompt = document.getElementById('chat-system-prompt').value.trim();

      const startTime = Date.now();

      try {
        if (!isStream) {
          const payload = {
            message: text,
            routing_mode: mode,
            model: specificModel,
            system_prompt: sysPrompt || undefined
          };
          const res = await apiRequest('/v2/chat', 'POST', payload);
          const elapsed = Date.now() - startTime;
          aiContent.innerText = res.response || res.content;

          // Update meta box
          document.getElementById('chat-meta-box').classList.remove('hidden');
          document.getElementById('meta-model').innerText = res.model || 'auto';
          document.getElementById('meta-provider').innerText = res.provider || 'orchestrator';
          document.getElementById('meta-latency').innerText = elapsed + 'ms';
          document.getElementById('meta-reason').innerText = res.routing_reason || 'Highest score under ' + mode;
        } else {
          // SSE Streaming
          const response = await fetch('/api/v1/chat/stream', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ' + currentApiKey
            },
            body: JSON.stringify({
              messages: [{ role: 'user', content: text }],
              model: specificModel || undefined
            })
          });

          aiContent.innerText = '';
          const reader = response.body.getReader();
          const decoder = new TextDecoder('utf-8');
          let fullText = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value);
            const lines = chunk.split('\\n');
            for (let line of lines) {
              if (line.startsWith('data: ')) {
                const dataStr = line.substring(6).trim();
                if (dataStr === '[DONE]') continue;
                try {
                  const parsed = JSON.parse(dataStr);
                  if (parsed.delta) {
                    fullText += parsed.delta;
                    aiContent.innerText = fullText;
                    chatLog.scrollTop = chatLog.scrollHeight;
                  }
                } catch(e) {}
              }
            }
          }
          const elapsed = Date.now() - startTime;
          document.getElementById('chat-meta-box').classList.remove('hidden');
          document.getElementById('meta-model').innerText = specificModel || 'auto stream';
          document.getElementById('meta-provider').innerText = 'groq/gemini';
          document.getElementById('meta-latency').innerText = elapsed + 'ms';
          document.getElementById('meta-reason').innerText = 'Streaming chunk generator';
        }
      } catch (err) {
        aiContent.innerText = '⚠️ Error: ' + err.message;
      }
    }

    function clearChatLog() {
      document.getElementById('chat-log').innerHTML = '';
      document.getElementById('chat-meta-box').classList.add('hidden');
    }

    // Voice AI TTS
    async function synthesizeSpeech() {
      const text = document.getElementById('tts-text').value.trim();
      const voice = document.getElementById('tts-voice').value;
      const statusEl = document.getElementById('tts-status');
      const audioPlayer = document.getElementById('tts-audio-player');
      if (!text) {
        showToast('Please enter text to synthesize', 'info');
        return;
      }

      statusEl.innerText = 'Generating neural voice stream...';
      try {
        const res = await fetch('/v2/voice/tts', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + currentApiKey
          },
          body: JSON.stringify({ text, voice })
        });
        if (!res.ok) throw new Error('TTS generation failed (' + res.status + ')');

        const blob = await res.blob();
        const audioUrl = URL.createObjectURL(blob);
        audioPlayer.src = audioUrl;
        audioPlayer.classList.remove('hidden');
        audioPlayer.play();
        statusEl.innerText = 'Playing neural audio (' + (blob.size / 1024).toFixed(1) + ' KB)';
      } catch (e) {
        statusEl.innerText = 'Error: ' + e.message;
      }
    }

    // Voice AI STT
    async function transcribeAudio() {
      const fileInput = document.getElementById('stt-audio-file');
      const output = document.getElementById('stt-output');
      if (!fileInput.files.length) {
        showToast('Please select an audio file first', 'info');
        return;
      }

      output.innerText = 'Transcribing audio with Whisper Large V3 Turbo...';
      const formData = new FormData();
      formData.append('audio', fileInput.files[0]);

      try {
        const res = await apiRequest('/v2/voice/stt', 'POST', formData);
        output.innerText = `[Language: ${res.language || 'detected'}] [Duration: ${res.duration_seconds || '0'}s]\\n\\n` + res.text;
      } catch (e) {
        output.innerText = 'Error: ' + e.message;
      }
    }

    // Autonomous Research
    async function runResearch() {
      const q = document.getElementById('research-query').value.trim();
      if (!q) return;

      const statusPill = document.getElementById('research-status-pill');
      const outContent = document.getElementById('research-output-content');
      const outSources = document.getElementById('research-sources-list');

      statusPill.classList.remove('hidden');
      statusPill.innerText = '🔍 Searching DuckDuckGo and decomposing query...';
      outContent.innerText = 'Gathering web sources and synthesizing answer...';
      outSources.innerHTML = '';

      try {
        const res = await apiRequest('/v2/research', 'POST', { query: q, max_results: 5 });
        statusPill.innerText = `Completed in ${res.execution_time_seconds || 1.2}s. Citations extracted.`;
        outContent.innerText = res.synthesis || res.content;

        let srcHtml = '';
        if (res.sources && res.sources.length) {
          res.sources.forEach((s, idx) => {
            srcHtml += `
              <div class="p-2.5 rounded-lg bg-slate-950 border border-slate-800 space-y-1">
                <div class="font-bold text-slate-200">[${idx + 1}] ${escapeHtml(s.title || 'Source')}</div>
                <div class="text-[10px] text-slate-400 truncate">${escapeHtml(s.snippet || '')}</div>
                <a href="${s.url}" target="_blank" class="text-cyan-400 hover:underline block truncate text-[10px]">${s.url}</a>
              </div>
            `;
          });
        } else {
          srcHtml = '<div class="text-slate-400">0 sources returned.</div>';
        }
        outSources.innerHTML = srcHtml;
      } catch (e) {
        outContent.innerText = 'Error: ' + e.message;
        statusPill.innerText = 'Research failed.';
      }
    }

    // Sandbox Execution
    async function executeSandboxCode() {
      const code = document.getElementById('sandbox-code').value;
      const resEl = document.getElementById('sandbox-result');
      resEl.innerText = 'Running in restricted subprocess sandbox...';

      try {
        const res = await apiRequest('/v2/tools/execute', 'POST', {
          tool_name: 'python_sandbox',
          arguments: { code }
        });
        resEl.innerText = `Exit Code: ${res.exit_code} | Runtime: ${res.execution_time_seconds || 0}s\\n\\n` +
          `[STDOUT]:\\n${res.stdout || '(no stdout)'}\\n\\n` +
          `[STDERR]:\\n${res.stderr || '(clean)'}`;
      } catch (e) {
        resEl.innerText = 'Sandbox Error: ' + e.message;
      }
    }

    // Builtin Tools
    function updateToolArgsSample() {
      const sel = document.getElementById('tool-select').value;
      const argsBox = document.getElementById('tool-args');
      if (sel === 'calculator') argsBox.value = '{"expression": "sqrt(144) + 25 * 4"}';
      if (sel === 'datetime') argsBox.value = '{"timezone": "Asia/Kolkata"}';
      if (sel === 'web_search') argsBox.value = '{"query": "ShivAI Python AI Orchestrator"}';
    }

    async function executeBuiltinTool() {
      const tool = document.getElementById('tool-select').value;
      const resEl = document.getElementById('tool-result');
      let args = {};
      try {
        args = JSON.parse(document.getElementById('tool-args').value);
      } catch(e) {
        showToast('Invalid JSON in tool arguments', 'error');
        return;
      }

      resEl.innerText = 'Executing tool ' + tool + '...';
      try {
        const res = await apiRequest('/v2/tools/execute', 'POST', {
          tool_name: tool,
          arguments: args
        });
        resEl.innerText = JSON.stringify(res, null, 2);
      } catch (e) {
        resEl.innerText = 'Error: ' + e.message;
      }
    }

    // Multi-Agent Task
    async function runMultiAgentTask() {
      const goal = document.getElementById('agent-goal').value.trim();
      const pipelineView = document.getElementById('agent-pipeline-view');
      if (!goal) return;

      const roles = [];
      if (document.getElementById('role-planner').checked) roles.push('planner');
      if (document.getElementById('role-researcher').checked) roles.push('researcher');
      if (document.getElementById('role-engineer').checked) roles.push('engineer');
      if (document.getElementById('role-writer').checked) roles.push('writer');

      pipelineView.innerHTML = '<div class="text-xs text-indigo-400 font-mono animate-pulse">Orchestrating agent DAG and executing subtasks...</div>';

      try {
        const res = await apiRequest('/v2/agents/execute', 'POST', { goal, team_roles: roles });
        let html = `
          <div class="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3 font-mono text-xs">
            <div class="text-emerald-400 font-bold">✨ Multi-Agent Goal Achieved (${res.duration_seconds || 1.8}s)</div>
            <div class="text-slate-300 font-sans text-sm whitespace-pre-wrap">${escapeHtml(res.final_output || res.synthesis || '')}</div>
          </div>
        `;
        if (res.tasks_executed && res.tasks_executed.length) {
          html += '<div class="space-y-2 mt-4">';
          res.tasks_executed.forEach((t, i) => {
            html += `
              <div class="p-3 rounded-lg bg-slate-950 border border-slate-800/80 text-xs font-mono">
                <div class="text-indigo-400 font-semibold">[Step ${i+1}] Role: ${t.role}</div>
                <div class="text-slate-400 mt-1">${escapeHtml(t.output || '')}</div>
              </div>
            `;
          });
          html += '</div>';
        }
        pipelineView.innerHTML = html;
      } catch (e) {
        pipelineView.innerHTML = `<div class="text-rose-400 font-mono text-xs">Error: ${e.message}</div>`;
      }
    }

    // Document Analysis
    async function analyzeDocument() {
      const fileInput = document.getElementById('doc-file-input');
      const query = document.getElementById('doc-query-input').value.trim();
      const resEl = document.getElementById('doc-analysis-result');

      if (!fileInput.files.length) {
        showToast('Please select a PDF or image file first', 'info');
        return;
      }

      resEl.innerText = 'Extracting document chunks and analyzing with vision/text processor...';
      const formData = new FormData();
      formData.append('file', fileInput.files[0]);
      formData.append('query', query);

      try {
        const res = await apiRequest('/v2/documents/analyze', 'POST', formData);
        resEl.innerText = JSON.stringify(res, null, 2);
      } catch (e) {
        resEl.innerText = 'Error: ' + e.message;
      }
    }

    // Memories
    async function loadUserMemories() {
      const list = document.getElementById('memories-list');
      list.innerHTML = '<div class="text-slate-400">Loading user memories...</div>';
      try {
        const res = await apiRequest('/v2/memory');
        const items = res.memories || res.items || [];
        if (!items.length) {
          list.innerHTML = '<div class="text-slate-400">No memories stored for this user yet.</div>';
          return;
        }
        let html = '';
        items.forEach(m => {
          html += `
            <div class="p-3 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
              <div>
                <span class="text-[10px] text-indigo-400 uppercase font-bold">[${m.memory_type || 'fact'}]</span>
                <div class="text-slate-200 mt-0.5">${escapeHtml(m.content)}</div>
              </div>
              <button onclick="deleteMemory('${m.id}')" class="text-rose-400 hover:text-rose-300 text-xs px-2 py-1">Delete</button>
            </div>
          `;
        });
        list.innerHTML = html;
      } catch (e) {
        list.innerHTML = `<div class="text-rose-400">Error: ${e.message}</div>`;
      }
    }

    async function addMemoryRecord() {
      const content = document.getElementById('mem-content').value.trim();
      const type = document.getElementById('mem-type').value;
      if (!content) return;

      try {
        await apiRequest('/v2/memory', 'POST', { content, memory_type: type });
        document.getElementById('mem-content').value = '';
        showToast('Memory saved with sensitive filter active', 'success');
        loadUserMemories();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function deleteMemory(id) {
      try {
        await apiRequest('/v2/memory/' + id, 'DELETE');
        showToast('Memory item removed', 'success');
        loadUserMemories();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
    async function generateStudioImage() {
      const prompt = document.getElementById('media-img-prompt').value.trim();
      if (!prompt) return showToast('Please enter an image prompt', 'error');
      const model = document.getElementById('media-img-model').value;
      const size = document.getElementById('media-img-size').value.split('x');
      const width = parseInt(size[0]);
      const height = parseInt(size[1]);

      const btn = document.getElementById('btn-gen-img');
      const preview = document.getElementById('media-img-preview');
      btn.innerText = 'Generating Image... ⏳';
      btn.disabled = true;
      preview.innerHTML = '<span class="text-xs text-indigo-400 animate-pulse font-mono">Generating high-res image with FLUX.1...</span>';

      try {
        const res = await apiRequest('/v2/media/image', 'POST', { prompt, model, width, height });
        preview.innerHTML = `<a href="${res.image_url}" target="_blank" title="Click to view full size"><img src="${res.image_url}" class="max-h-[360px] w-auto rounded-lg shadow-xl hover:scale-105 transition" alt="${escapeHtml(prompt)}" /></a>`;
        showToast('Image generated successfully!', 'success');
      } catch (e) {
        preview.innerHTML = `<span class="text-xs text-rose-400 font-mono">Error: ${escapeHtml(e.message)}</span>`;
        showToast(e.message, 'error');
      } finally {
        btn.innerText = 'Generate Image ✨';
        btn.disabled = false;
      }
    }

    async function generateStudioVideo() {
      const prompt = document.getElementById('media-vid-prompt').value.trim();
      if (!prompt) return showToast('Please enter a video prompt', 'error');

      const btn = document.getElementById('btn-gen-vid');
      const preview = document.getElementById('media-vid-preview');
      btn.innerText = 'Generating Video... ⏳';
      btn.disabled = true;
      preview.innerHTML = '<span class="text-xs text-cyan-400 animate-pulse font-mono">Generating video animation...</span>';

      try {
        const res = await apiRequest('/v2/media/video', 'POST', { prompt, duration: 3 });
        preview.innerHTML = `<video controls autoplay loop class="max-h-[260px] rounded-lg shadow-xl"><source src="${res.video_url}" type="video/mp4">Your browser does not support the video tag.</video>`;
        showToast('Video generated successfully!', 'success');
      } catch (e) {
        preview.innerHTML = `<span class="text-xs text-rose-400 font-mono">Error: ${escapeHtml(e.message)}</span>`;
        showToast(e.message, 'error');
      } finally {
        btn.innerText = 'Generate Video Clip 🎥';
        btn.disabled = false;
      }
    }

    function generateStudioSpeech() {
      const text = document.getElementById('media-tts-text').value.trim();
      if (!text) return showToast('Please enter text to speak', 'error');
      const voice = document.getElementById('media-tts-voice').value;
      const player = document.getElementById('media-audio-player');
      
      const audioUrl = `/v2/media/speech?text=${encodeURIComponent(text)}&voice=${encodeURIComponent(voice)}`;
      player.src = audioUrl;
      player.classList.remove('hidden');
      player.play();
      showToast('Playing neural speech audio', 'success');
    }

    // --- Intent & Orchestrator JS ---
    async function analyzeOrchestration() {
      const prompt = document.getElementById('orch-prompt').value.trim();
      if (!prompt) return showToast('Please enter a goal or task prompt', 'error');

      try {
        const [intent, plan] = await Promise.all([
          apiRequest('/v2/orchestration/classify', 'POST', { prompt }),
          apiRequest('/v2/orchestration/plan', 'POST', { goal: prompt })
        ]);

        document.getElementById('orch-results').classList.remove('hidden');
        document.getElementById('orch-primary').innerText = intent.primary_intent.toUpperCase().replace(/_/g, ' ');
        document.getElementById('orch-confidence').innerText = (intent.confidence * 100).toFixed(0) + '%';
        document.getElementById('orch-agent').innerText = intent.recommended_agent.toUpperCase();

        const stepsList = document.getElementById('orch-steps-list');
        stepsList.innerHTML = plan.steps.map((s, idx) => `
          <div class="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 flex items-start space-x-3">
            <span class="w-6 h-6 rounded-full bg-indigo-950 text-indigo-400 border border-indigo-800 flex items-center justify-center font-bold text-xs shrink-0">${idx+1}</span>
            <div class="flex-1 space-y-1">
              <div class="flex justify-between items-center">
                <span class="font-bold text-slate-200 text-xs">${escapeHtml(s.name)}</span>
                <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300">Agent: ${escapeHtml(s.assigned_agent)}</span>
              </div>
              <p class="text-[11px] text-slate-400">${escapeHtml(s.description)}</p>
              <div class="text-[10px] text-emerald-400/80 font-mono">Validation: ${escapeHtml(s.validation_criteria)}</div>
            </div>
          </div>
        `).join('');

        showToast('Task decomposed into execution DAG', 'success');
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    // --- 2D Design Studio JS ---
    async function renderStudioDesign() {
      const headline = document.getElementById('studio-design-headline').value.trim();
      const preset = document.getElementById('studio-design-preset').value;
      const bg = document.getElementById('studio-design-bg').value.trim();
      const preview = document.getElementById('studio-design-preview');

      preview.innerHTML = '<span class="text-xs text-cyan-400 animate-pulse font-mono">Rendering vector SVG canvas...</span>';
      try {
        const res = await apiRequest('/v2/studios/design/create', 'POST', {
          name: 'Banner',
          preset,
          background_color: bg,
          headline
        });
        preview.innerHTML = `<div class="w-full max-h-[300px] overflow-hidden rounded-lg shadow-xl">${res.svg}</div>`;
        showToast('SVG canvas rendered successfully', 'success');
      } catch (e) {
        preview.innerHTML = `<span class="text-xs text-rose-400 font-mono">Error: ${escapeHtml(e.message)}</span>`;
        showToast(e.message, 'error');
      }
    }

    // --- 3D Asset Studio JS ---
    async function renderStudio3D() {
      const mesh_type = document.getElementById('studio-3d-mesh').value;
      const color = document.getElementById('studio-3d-color').value.trim();
      const preview = document.getElementById('studio-3d-preview');

      preview.innerHTML = '<span class="text-xs text-purple-400 animate-pulse font-mono">Synthesizing 3D mesh geometry...</span>';
      try {
        const res = await apiRequest('/v2/studios/threed/create', 'POST', {
          name: 'Asset',
          mesh_type,
          color,
          metallic: 0.3,
          roughness: 0.4
        });
        const blob = new Blob([res.html_preview], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        preview.innerHTML = `<iframe src="${url}" class="w-full h-[240px] border-0 rounded-lg"></iframe>`;
        showToast(`3D ${mesh_type} mesh synthesized (${res.triangle_count} triangles)`, 'success');
      } catch (e) {
        preview.innerHTML = `<span class="text-xs text-rose-400 font-mono">Error: ${escapeHtml(e.message)}</span>`;
        showToast(e.message, 'error');
      }
    }

    // --- Game Studio JS ---
    async function renderStudioGame() {
      const title = document.getElementById('studio-game-title').value.trim() || 'Neon Runner';
      const game_type = document.getElementById('studio-game-type').value;
      const preview = document.getElementById('studio-game-preview');

      preview.innerHTML = '<span class="text-xs text-rose-400 animate-pulse font-mono">Generating game loop & Web Audio synthesizer...</span>';
      try {
        const res = await apiRequest('/v2/studios/games/create', 'POST', {
          title,
          game_type
        });
        const blob = new Blob([res.html_bundle], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        preview.innerHTML = `<iframe src="${url}" class="w-full h-[320px] border-0 rounded-lg"></iframe>`;
        showToast(`Playable ${game_type.toUpperCase()} game running!`, 'success');
      } catch (e) {
        preview.innerHTML = `<span class="text-xs text-rose-400 font-mono">Error: ${escapeHtml(e.message)}</span>`;
        showToast(e.message, 'error');
      }
    }

    // --- Full-Stack App Builder JS ---
    async function bundleStudioApp() {
      const app_name = document.getElementById('studio-app-name').value.trim() || 'My App';
      const entity_name = document.getElementById('studio-app-entity').value.trim() || 'Item';
      const preview = document.getElementById('studio-app-preview');

      preview.innerHTML = '<span class="text-xs text-amber-400 animate-pulse font-mono">Generating full-stack FastAPI + Tailwind project...</span>';
      try {
        const res = await apiRequest('/v2/studios/apps/create', 'POST', {
          app_name,
          entity_name
        });
        preview.innerHTML = `
          <div class="space-y-2">
            <div class="flex justify-between items-center text-emerald-400 font-bold">
              <span>✅ ${escapeHtml(res.app_name)} Built Successfully</span>
              <a href="/v2/jobs/${res.project_id}/artifacts/${res.artifact.name}" class="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded-lg font-semibold transition" download>
                Download ZIP Bundle 📦
              </a>
            </div>
            <div class="text-[11px] text-slate-400">Generated Files: ${res.files.map(f => `<code class="bg-slate-900 px-1 py-0.5 rounded text-amber-300 font-mono">${f}</code>`).join(' ')}</div>
            <div class="text-[10px] text-slate-500 font-mono">Validated Syntax: Python AST verified | HTML5 UI integrated</div>
          </div>
        `;
        showToast('Full-Stack App bundle created successfully', 'success');
      } catch (e) {
        preview.innerHTML = `<span class="text-xs text-rose-400 font-mono">Error: ${escapeHtml(e.message)}</span>`;
        showToast(e.message, 'error');
      }
    }

    // --- Background Jobs JS ---
    async function loadBackgroundJobs() {
      const tbody = document.getElementById('jobs-table-body');
      try {
        const jobs = await apiRequest('/v2/jobs');
        if (!jobs || jobs.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="p-4 text-center text-slate-500 italic">No background jobs registered yet</td></tr>';
          return;
        }
        tbody.innerHTML = jobs.map(j => {
          const badgeClass = j.status === 'completed' ? 'bg-emerald-950 text-emerald-400 border-emerald-800' :
                             j.status === 'running' ? 'bg-indigo-950 text-indigo-400 border-indigo-800 animate-pulse' :
                             j.status === 'failed' ? 'bg-rose-950 text-rose-400 border-rose-800' :
                             'bg-slate-800 text-slate-400 border-slate-700';
          return `
            <tr class="hover:bg-slate-800/20">
              <td class="p-3.5 font-mono text-slate-300">${escapeHtml(j.job_id)}</td>
              <td class="p-3.5 font-semibold text-white">${escapeHtml(j.job_type)}</td>
              <td class="p-3.5 text-slate-400 font-mono">${j.priority === 1 ? 'CRITICAL' : j.priority === 2 ? 'HIGH' : 'NORMAL'}</td>
              <td class="p-3.5"><span class="px-2 py-0.5 rounded-full border text-[10px] font-bold ${badgeClass}">${j.status.toUpperCase()}</span></td>
              <td class="p-3.5">
                <div class="w-24 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                  <div class="bg-indigo-500 h-1.5" style="width: ${j.progress.percentage}%"></div>
                </div>
                <span class="text-[10px] text-slate-400">${j.progress.percentage}%</span>
              </td>
              <td class="p-3.5">
                ${j.artifacts && j.artifacts.length > 0 ?
                  j.artifacts.map(a => `<a href="/v2/jobs/${j.job_id}/artifacts/${a.name}" class="text-xs text-cyan-400 hover:underline block">${escapeHtml(a.name)}</a>`).join('') :
                  '<span class="text-slate-600">-</span>'}
              </td>
            </tr>
          `;
        }).join('');
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-rose-400 font-mono">Error: ${escapeHtml(e.message)}</td></tr>`;
      }
    }

    // Device Operator & Automation JavaScript Handlers
    async function loadDevicesDashboard() {
      // 1. Check Emergency Stop Status
      try {
        const es = await apiRequest('/v2/devices/emergency-stop/status');
        const alertBox = document.getElementById('device-emergency-alert');
        const stopBtn = document.getElementById('btn-emergency-stop');
        const resetBtn = document.getElementById('btn-emergency-reset');
        if (es.is_active) {
          alertBox.classList.remove('hidden');
          document.getElementById('device-emergency-reason').innerText = `Reason: ${es.reason} (Triggered by ${es.triggered_by})`;
          stopBtn.classList.add('opacity-50', 'pointer-events-none');
          resetBtn.classList.remove('hidden');
        } else {
          alertBox.classList.add('hidden');
          stopBtn.classList.remove('opacity-50', 'pointer-events-none');
          resetBtn.classList.add('hidden');
        }
      } catch (e) {
        console.error('Error fetching emergency stop status', e);
      }

      // 2. Load Devices
      const devTbody = document.getElementById('devices-table-body');
      try {
        const devs = await apiRequest('/v2/devices');
        if (!devs.length) {
          devTbody.innerHTML = '<tr><td colspan="4" class="p-3 text-center text-slate-500 italic">No devices enrolled</td></tr>';
        } else {
          devTbody.innerHTML = devs.map(d => `
            <tr class="hover:bg-slate-800/30">
              <td class="p-2.5 font-semibold text-white">${escapeHtml(d.name)}</td>
              <td class="p-2.5 font-mono text-cyan-400 text-[11px]">${d.device_type}</td>
              <td class="p-2.5"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${d.status === 'online' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-rose-950 text-rose-400 border border-rose-800'}">${d.status.toUpperCase()}</span></td>
              <td class="p-2.5 text-right">
                ${d.status !== 'revoked' ? `<button onclick="revokeDeviceUI('${d.device_id}')" class="text-rose-400 hover:text-rose-300 text-[10px] underline">Revoke</button>` : '<span class="text-slate-600 text-[10px]">Revoked</span>'}
              </td>
            </tr>
          `).join('');
        }
      } catch (e) {
        devTbody.innerHTML = `<tr><td colspan="4" class="p-3 text-center text-rose-400">Error: ${escapeHtml(e.message)}</td></tr>`;
      }

      // 3. Load Pending Approvals
      const apprList = document.getElementById('approvals-inbox-list');
      const apprBadge = document.getElementById('pending-approvals-badge');
      try {
        const apprs = await apiRequest('/v2/devices/approvals/pending');
        apprBadge.innerText = `${apprs.length} PENDING`;
        if (!apprs.length) {
          apprList.innerHTML = '<div class="p-4 text-center text-slate-500 italic">No consequential actions pending human approval.</div>';
        } else {
          apprList.innerHTML = apprs.map(a => `
            <div class="p-3 rounded-xl bg-slate-900 border border-amber-800/60 space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-[10px] font-bold text-amber-400 uppercase tracking-wider">${a.risk_category}</span>
                <span class="text-[10px] text-slate-500 font-mono">${a.action_id}</span>
              </div>
              <div class="font-semibold text-slate-200 text-xs">${escapeHtml(a.summary)}</div>
              <div class="text-[11px] text-slate-400">${escapeHtml(a.consequences)}</div>
              <div class="flex items-center space-x-2 pt-1">
                <button onclick="decideApprovalUI('${a.approval_id}', true)" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-[10px] font-bold transition">
                  Approve ✅
                </button>
                <button onclick="decideApprovalUI('${a.approval_id}', false)" class="px-3 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-[10px] font-bold transition">
                  Reject ❌
                </button>
              </div>
            </div>
          `).join('');
        }
      } catch (e) {
        apprList.innerHTML = `<div class="p-3 text-center text-rose-400">Error: ${escapeHtml(e.message)}</div>`;
      }

      // 4. Load Recurring Schedules
      const schedList = document.getElementById('schedules-list');
      try {
        const scheds = await apiRequest('/v2/automation/schedules');
        if (!scheds.length) {
          schedList.innerHTML = '<div class="p-3 text-center text-slate-500 italic">No scheduled automations configured</div>';
        } else {
          schedList.innerHTML = scheds.map(s => `
            <div class="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
              <div>
                <div class="font-semibold text-slate-200 text-xs">${escapeHtml(s.name)}</div>
                <div class="text-[10px] text-slate-500">${escapeHtml(s.description)}</div>
              </div>
              <div class="flex items-center space-x-2">
                <button onclick="toggleScheduleUI('${s.workflow_id}', ${!s.is_enabled})" class="px-2 py-0.5 rounded text-[10px] font-bold ${s.is_enabled ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-slate-800 text-slate-400 border border-slate-700'}">
                  ${s.is_enabled ? 'ENABLED' : 'DISABLED'}
                </button>
                <button onclick="triggerScheduleUI('${s.workflow_id}')" class="px-2 py-0.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-[10px] font-semibold">
                  Run ⚡
                </button>
              </div>
            </div>
          `).join('');
        }
      } catch (e) {
        schedList.innerHTML = `<div class="p-3 text-center text-rose-400">Error: ${escapeHtml(e.message)}</div>`;
      }
    }

    async function triggerEmergencyStopUI() {
      if (!confirm("Are you sure you want to trigger the SYSTEM EMERGENCY STOP? All device actions and active workflows will be immediately terminated.")) return;
      try {
        await apiRequest('/v2/devices/emergency-stop/trigger', 'POST', { reason: 'User initiated emergency stop from Command Center' });
        showToast('EMERGENCY STOP TRIGGERED: All devices locked', 'error');
        loadDevicesDashboard();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function resetEmergencyStopUI() {
      try {
        await apiRequest('/v2/devices/emergency-stop/reset', 'POST');
        showToast('Emergency Stop Reset: Devices restored to normal operation', 'success');
        loadDevicesDashboard();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function requestDevicePairingUI() {
      try {
        const res = await apiRequest('/v2/devices/pair/request', 'POST', { name: 'New Client Device', device_type: 'android', ttl_seconds: 300 });
        document.getElementById('pairing-code-banner').classList.remove('hidden');
        document.getElementById('pairing-code-display').innerText = res.pairing_code;
        showToast('Pairing code generated: valid for 5 minutes', 'success');
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function revokeDeviceUI(deviceId) {
      if (!confirm(`Revoke device access for '${deviceId}'?`)) return;
      try {
        await apiRequest(`/v2/devices/${deviceId}/revoke`, 'POST');
        showToast(`Device ${deviceId} revoked`, 'success');
        loadDevicesDashboard();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function observeHostDeviceUI() {
      try {
        const obs = await apiRequest('/v2/devices/host-local-primary/observe', 'POST');
        document.getElementById('obs-window-title').innerText = obs.active_window_title || 'Active Desktop';
        document.getElementById('obs-process-name').innerText = obs.active_process_name || 'explorer.exe';
        document.getElementById('obs-pid').innerText = obs.active_pid || '0';
        document.getElementById('obs-bounds').innerText = `${obs.window_rect.width}x${obs.window_rect.height} at (${obs.window_rect.x}, ${obs.window_rect.y})`;
        document.getElementById('obs-redacted').innerText = obs.redacted_secrets_count;
        showToast('Screen and foreground window state captured', 'success');
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function decideApprovalUI(approvalId, approved) {
      try {
        await apiRequest(`/v2/devices/approvals/${approvalId}/decide`, 'POST', { approved, notes: approved ? 'Approved by Admin' : 'Rejected by Admin' });
        showToast(`Ticket ${approvalId} ${approved ? 'APPROVED' : 'REJECTED'}`, approved ? 'success' : 'error');
        loadDevicesDashboard();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function simulateDeviceAction() {
      const atype = document.getElementById('sim-action-type').value;
      const target = document.getElementById('sim-target-app').value.trim();
      const resBox = document.getElementById('sim-result-box');
      resBox.classList.remove('hidden');
      resBox.innerText = 'Evaluating action through 3-tier policy engine...';

      try {
        const payload = {
          action_type: atype,
          target_app: target,
          params: atype === 'submit_form' ? { account_action: 'bank_transfer', amount: '$5,000' } : { note: 'Simulation test' }
        };
        const res = await apiRequest('/v2/devices/host-local-primary/action', 'POST', payload);
        resBox.innerText = JSON.stringify(res, null, 2);
        if (res.status === 'pending_approval') {
          showToast(`Action requires approval (${res.risk_category})`, 'info');
          loadDevicesDashboard();
        } else {
          showToast(`Action completed: verified=${res.verification?.verified}`, 'success');
        }
      } catch (e) {
        resBox.innerText = 'Error: ' + e.message;
        showToast(e.message, 'error');
      }
    }

    async function toggleScheduleUI(wfId, enable) {
      try {
        await apiRequest(`/v2/automation/schedules/${wfId}/toggle`, 'POST', { enabled: enable });
        showToast(`Schedule ${enable ? 'enabled' : 'disabled'}`, 'success');
        loadDevicesDashboard();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    async function triggerScheduleUI(wfId) {
      try {
        const res = await apiRequest(`/v2/automation/schedules/${wfId}/trigger`, 'POST');
        showToast(`Workflow ${res.workflow_name} triggered!`, 'success');
        loadDevicesDashboard();
      } catch (e) {
        showToast(e.message, 'error');
      }
    }

    // Initialize on page load
    window.addEventListener('DOMContentLoaded', () => {
      refreshAllData();
    });

  </script>
</body>
</html>
"""
