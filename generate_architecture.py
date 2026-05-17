"""
Generate STRIDE architecture diagrams as PDF.
Run: uv run python generate_architecture.py
Output: stride_architecture.pdf
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np


def draw_rounded_box(ax, x, y, w, h, text, subtext="", color="#1e293b", border="#334155", text_color="white", fontsize=10):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15", facecolor=color, edgecolor=border, linewidth=1.5)
    ax.add_patch(box)
    if subtext:
        ax.text(x + w/2, y + h/2 + 0.15, text, ha='center', va='center', fontsize=fontsize, fontweight='bold', color=text_color)
        ax.text(x + w/2, y + h/2 - 0.2, subtext, ha='center', va='center', fontsize=7, color="#94a3b8", style='italic')
    else:
        ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=fontsize, fontweight='bold', color=text_color)


def draw_arrow(ax, x1, y1, x2, y2, color="#60a5fa", label="", style="->"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=1.5, connectionstyle="arc3,rad=0"))
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2 + 0.12
        ax.text(mx, my, label, ha='center', va='center', fontsize=6.5, color=color,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='#0f172a', edgecolor='none'))


# ══════════════════════════════════════════════════════════════════
# PAGE 1: Full System Architecture
# ══════════════════════════════════════════════════════════════════
fig1, ax1 = plt.subplots(1, 1, figsize=(14, 10))
fig1.patch.set_facecolor('#0f172a')
ax1.set_facecolor('#0f172a')
ax1.set_xlim(-0.5, 13.5)
ax1.set_ylim(-1, 10)
ax1.axis('off')

# Title
ax1.text(6.75, 9.5, "STRIDE — System Architecture", ha='center', fontsize=20, fontweight='bold', color='white')
ax1.text(6.75, 9.1, "6 Agents · Real Scraping · Thompson Sampling RL · x402 Payments", ha='center', fontsize=10, color='#94a3b8')

# ── User ──
draw_rounded_box(ax1, 0, 7, 2.2, 1, "User", "Streamlit UI", color="#1e1b4b", border="#6366f1")

# ── Agent 1: Memory ──
draw_rounded_box(ax1, 3.5, 7, 2.2, 1, "Memory Agent", "context_graph.json", color="#172554", border="#3b82f6")

# ── Agent 2: RL Bandit ──
draw_rounded_box(ax1, 7, 7, 2.2, 1, "RL Bandit", "Thompson Sampling", color="#14274e", border="#8b5cf6")

# ── Agent 3: Auth ──
draw_rounded_box(ax1, 10.5, 7, 2.2, 1, "Auth Agent", "Scoped Credential", color="#1c1917", border="#f59e0b")

# ── Agent 4: Shopping ──
draw_rounded_box(ax1, 3.5, 4.5, 2.2, 1.3, "Shopping Agent", "Claude Sonnet 4.6\nReAct Loop", color="#022c22", border="#10b981")

# ── Real Websites ──
draw_rounded_box(ax1, 7, 4.8, 2.2, 0.8, "Real Websites", "Zappos · StockX · GOAT · 6pm", color="#1a1a2e", border="#64748b")

# ── Agent 5: Payment ──
draw_rounded_box(ax1, 10.5, 4.5, 2.2, 1.3, "Payment Agent", "x402 Protocol", color="#3b0764", border="#a855f7")

# ── Agent 6: Reflexion ──
draw_rounded_box(ax1, 0, 4.5, 2.2, 1, "Reflexion", "Plain-English Lesson", color="#172554", border="#3b82f6")

# ── x402 Server ──
draw_rounded_box(ax1, 10.5, 2, 2.2, 1, "x402 Server", "FastAPI + Middleware", color="#3b0764", border="#a855f7")

# ── Blockchain ──
draw_rounded_box(ax1, 7, 2, 2.2, 1, "Base Sepolia", "USDC on-chain", color="#1c1917", border="#f59e0b")

# ── Facilitator ──
draw_rounded_box(ax1, 3.5, 2, 2.2, 1, "x402 Facilitator", "x402.org/facilitator", color="#1a1a2e", border="#64748b")

# ── Agent UX ──
draw_rounded_box(ax1, 0, 2, 2.2, 1, "Agent UX APIs", "/agent-profile\n/agent-capabilities", color="#14274e", border="#3b82f6")

# ── Context Graph ──
draw_rounded_box(ax1, 0, 0, 5.7, 0.9, "Context Graph: preferences · trust rules · RL weights · history · guardrails", color="#0f172a", border="#334155", fontsize=8)

# ── Arrows ──
# User → Memory
draw_arrow(ax1, 2.2, 7.5, 3.5, 7.5, label="preferences")
# Memory → Bandit
draw_arrow(ax1, 5.7, 7.5, 7, 7.5, label="context")
# Bandit → Auth
draw_arrow(ax1, 9.2, 7.5, 10.5, 7.5, label="strategy")
# Auth → Shopping (down)
draw_arrow(ax1, 11.6, 7, 11.6, 5.8, label="credential", color="#f59e0b")
ax1.annotate("", xy=(5.7, 5.5), xytext=(11.0, 5.5),
            arrowprops=dict(arrowstyle="->", color="#f59e0b", lw=1.2))
# Shopping → Websites
draw_arrow(ax1, 5.7, 5.0, 7, 5.2, label="scrape", color="#10b981")
# Websites → Shopping
draw_arrow(ax1, 7, 4.9, 5.7, 4.7, label="products", color="#64748b")
# Shopping → Payment
draw_arrow(ax1, 5.7, 4.8, 10.5, 5.0, label="purchase decision", color="#a855f7")
# Payment → x402 Server
draw_arrow(ax1, 11.6, 4.5, 11.6, 3.0, label="POST /purchase", color="#a855f7")
# x402 Server → Facilitator
draw_arrow(ax1, 10.5, 2.5, 5.7, 2.5, label="verify payment", color="#64748b")
# Facilitator → Blockchain
draw_arrow(ax1, 5.7, 2.3, 7, 2.3, label="settle", color="#f59e0b")
# Blockchain → x402 Server
draw_arrow(ax1, 9.2, 2.7, 10.5, 2.7, label="confirmed", color="#10b981")
# Shopping → Reflexion
draw_arrow(ax1, 3.5, 5.0, 2.2, 5.0, label="result", color="#3b82f6")
# Reflexion → Memory (up)
draw_arrow(ax1, 1.1, 5.5, 1.1, 7.0, label="lesson", color="#3b82f6")

# Legend
legend_y = -0.5
ax1.text(0, legend_y, "Agent Colors:", fontsize=8, fontweight='bold', color='#94a3b8')
for i, (name, color) in enumerate([("Memory/Reflexion", "#3b82f6"), ("RL Bandit", "#8b5cf6"),
                                     ("Auth", "#f59e0b"), ("Shopping", "#10b981"), ("Payment/x402", "#a855f7")]):
    ax1.add_patch(plt.Rectangle((2.5 + i*2.2, legend_y - 0.1), 0.3, 0.3, facecolor=color, edgecolor='none'))
    ax1.text(2.9 + i*2.2, legend_y + 0.05, name, fontsize=7, color='white', va='center')


# ══════════════════════════════════════════════════════════════════
# PAGE 2: x402 Payment Flow Detail
# ══════════════════════════════════════════════════════════════════
fig2, ax2 = plt.subplots(1, 1, figsize=(14, 10))
fig2.patch.set_facecolor('#0f172a')
ax2.set_facecolor('#0f172a')
ax2.set_xlim(-0.5, 13.5)
ax2.set_ylim(-0.5, 10)
ax2.axis('off')

# Title
ax2.text(6.75, 9.5, "x402 Payment Flow — How STRIDE Pays", ha='center', fontsize=20, fontweight='bold', color='white')
ax2.text(6.75, 9.0, "Real USDC on Base Sepolia · Verified by On-Chain Facilitator", ha='center', fontsize=10, color='#94a3b8')

# Three columns
col1, col2, col3 = 1.5, 5.5, 10

# Column headers
ax2.text(col1+1, 8.3, "Payment Agent\n(Client)", ha='center', fontsize=11, fontweight='bold', color='#a855f7')
ax2.text(col2+1, 8.3, "x402 Server\n(Store Checkout)", ha='center', fontsize=11, fontweight='bold', color='#10b981')
ax2.text(col3+0.5, 8.3, "Blockchain\n(Base Sepolia)", ha='center', fontsize=11, fontweight='bold', color='#f59e0b')

# Vertical lines
for col in [col1+1, col2+1, col3+0.5]:
    ax2.plot([col, col], [1, 7.8], color='#1e293b', lw=2, linestyle='--')

# Step 1
y = 7.2
draw_rounded_box(ax2, col1-0.3, y-0.25, 2.6, 0.5, "1. POST /purchase", color="#3b0764", border="#a855f7", fontsize=9)
ax2.annotate("", xy=(col2+0.2, y), xytext=(col1+2.3, y),
            arrowprops=dict(arrowstyle="->", color="#a855f7", lw=2))
ax2.text((col1+2.3+col2+0.2)/2, y+0.15, '{"product": "Nike AF1", "price": 109}', ha='center', fontsize=6.5, color='#94a3b8')

# Step 2
y = 6.2
draw_rounded_box(ax2, col2-0.3, y-0.25, 2.6, 0.5, "2. HTTP 402 Returned", color="#022c22", border="#10b981", fontsize=9)
ax2.annotate("", xy=(col1+1.8, y), xytext=(col2-0.3, y),
            arrowprops=dict(arrowstyle="->", color="#10b981", lw=2))
ax2.text((col1+1.8+col2-0.3)/2, y+0.15, '"Pay $0.01 USDC to 0x3D7A..."', ha='center', fontsize=6.5, color='#94a3b8')

# Step 3
y = 5.2
draw_rounded_box(ax2, col1-0.3, y-0.25, 2.6, 0.5, "3. SDK Signs Transfer", color="#3b0764", border="#a855f7", fontsize=9)
ax2.text(col1+1, y-0.55, "EIP-3009 USDC authorization\nsigned with EVM_PRIVATE_KEY", ha='center', fontsize=6.5, color='#64748b')

# Step 4
y = 4.2
draw_rounded_box(ax2, col1-0.3, y-0.25, 2.6, 0.5, "4. Retry with Payment", color="#3b0764", border="#a855f7", fontsize=9)
ax2.annotate("", xy=(col2+0.2, y), xytext=(col1+2.3, y),
            arrowprops=dict(arrowstyle="->", color="#a855f7", lw=2))
ax2.text((col1+2.3+col2+0.2)/2, y+0.15, 'X-PAYMENT header (signed proof)', ha='center', fontsize=6.5, color='#94a3b8')

# Step 5
y = 3.2
draw_rounded_box(ax2, col2-0.3, y-0.25, 2.6, 0.5, "5. Verify via Facilitator", color="#022c22", border="#10b981", fontsize=9)
ax2.annotate("", xy=(col3-0.3, y), xytext=(col2+2.3, y),
            arrowprops=dict(arrowstyle="->", color="#f59e0b", lw=2))
ax2.text((col2+2.3+col3-0.3)/2, y+0.15, 'x402.org/facilitator', ha='center', fontsize=6.5, color='#94a3b8')

# Step 6
y = 2.2
draw_rounded_box(ax2, col3-0.8, y-0.25, 2.6, 0.5, "6. USDC Settled On-Chain", color="#1c1917", border="#f59e0b", fontsize=9)
ax2.text(col3+0.5, y-0.55, "Transaction visible on\nsepolia.basescan.org", ha='center', fontsize=6.5, color='#64748b')

# Step 7
y = 1.2
draw_rounded_box(ax2, col2-0.3, y-0.25, 2.6, 0.5, "7. 200 OK + Confirmation", color="#022c22", border="#10b981", fontsize=9)
ax2.annotate("", xy=(col1+1.8, y), xytext=(col2-0.3, y),
            arrowprops=dict(arrowstyle="->", color="#10b981", lw=2))
ax2.text((col1+1.8+col2-0.3)/2, y+0.15, '{"confirmation_id": "x402-abc123", "tx_hash": "0xbd4d..."}', ha='center', fontsize=6, color='#94a3b8')


# ══════════════════════════════════════════════════════════════════
# PAGE 3: Guardrails Architecture
# ══════════════════════════════════════════════════════════════════
fig3, ax3 = plt.subplots(1, 1, figsize=(14, 10))
fig3.patch.set_facecolor('#0f172a')
ax3.set_facecolor('#0f172a')
ax3.set_xlim(-0.5, 13.5)
ax3.set_ylim(-0.5, 10)
ax3.axis('off')

ax3.text(6.75, 9.5, "STRIDE — Agentic Guardrails", ha='center', fontsize=20, fontweight='bold', color='white')
ax3.text(6.75, 9.0, "4 Layers of Protection Before Any Purchase", ha='center', fontsize=10, color='#94a3b8')

# Layer 1
y = 7.5
draw_rounded_box(ax3, 0.5, y, 12, 1.2, "", color="#1e1b4b", border="#6366f1")
ax3.text(1, y+0.9, "LAYER 1: Preference Guardrails (shopping_agent.py)", fontsize=10, fontweight='bold', color='#818cf8')
ax3.text(1, y+0.5, "Color: 'Only buy tiffany blue'  ·  Specific product: 'Nike x Tiffany AF1 only'", fontsize=8, color='#cbd5e1')
ax3.text(1, y+0.2, "Custom instructions: 'Ask before buying anything else'  ·  Excluded brands: 'No Reebok'", fontsize=8, color='#cbd5e1')

# Layer 2
y = 5.8
draw_rounded_box(ax3, 0.5, y, 12, 1.2, "", color="#1c1917", border="#f59e0b")
ax3.text(1, y+0.9, "LAYER 2: Auth Guardrails (auth_agent.py)", fontsize=10, fontweight='bold', color='#fbbf24')
ax3.text(1, y+0.5, "Session expiry (1hr)  ·  Site whitelist (6 stores)  ·  Spend cap ($150)", fontsize=8, color='#cbd5e1')
ax3.text(1, y+0.2, "Budget enforcement ($120)  ·  Human approval gate (first 3 runs)", fontsize=8, color='#cbd5e1')

# Layer 3
y = 4.1
draw_rounded_box(ax3, 0.5, y, 12, 1.2, "", color="#3b0764", border="#a855f7")
ax3.text(1, y+0.9, "LAYER 3: Payment Guardrails (payment_agent.py)", fontsize=10, fontweight='bold', color='#c084fc')
ax3.text(1, y+0.5, "Auth clearance required  ·  Double-checks spend cap  ·  Human approval flag", fontsize=8, color='#cbd5e1')
ax3.text(1, y+0.2, "Only fires on final episode (exploration runs don't spend money)", fontsize=8, color='#cbd5e1')

# Layer 4
y = 2.4
draw_rounded_box(ax3, 0.5, y, 12, 1.2, "", color="#022c22", border="#10b981")
ax3.text(1, y+0.9, "LAYER 4: Protocol Guardrails (x402_server.py)", fontsize=10, fontweight='bold', color='#34d399')
ax3.text(1, y+0.5, "x402 middleware verifies payment signature  ·  Facilitator validates on-chain", fontsize=8, color='#cbd5e1')
ax3.text(1, y+0.2, "Transaction irreversible but transparent  ·  Verifiable on BaseScan", fontsize=8, color='#cbd5e1')

# Result
y = 0.8
draw_rounded_box(ax3, 2, y, 9, 0.8, "Purchase goes through ONLY if all 4 layers pass", color="#0f172a", border="#10b981", text_color="#10b981", fontsize=11)

# Arrows between layers
for y_start in [7.5, 5.8, 4.1]:
    ax3.annotate("", xy=(6.75, y_start), xytext=(6.75, y_start + 0.0 - 0.1),
                arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))


# ══════════════════════════════════════════════════════════════════
# Save all pages to PDF
# ══════════════════════════════════════════════════════════════════
from matplotlib.backends.backend_pdf import PdfPages

output_path = "stride_architecture.pdf"
with PdfPages(output_path) as pdf:
    pdf.savefig(fig1, facecolor=fig1.get_facecolor(), bbox_inches='tight')
    pdf.savefig(fig2, facecolor=fig2.get_facecolor(), bbox_inches='tight')
    pdf.savefig(fig3, facecolor=fig3.get_facecolor(), bbox_inches='tight')

print(f"Architecture PDF saved to: {output_path}")
print("3 pages: System Architecture · x402 Payment Flow · Guardrails")
plt.close('all')
