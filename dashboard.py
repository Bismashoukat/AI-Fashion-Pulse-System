import os
import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import date, timedelta
import io
from gtts import gTTS
import tempfile
import os
from PIL import Image
try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except Exception:
    PYZBAR_AVAILABLE = False
import numpy as np

st.set_page_config(page_title="AI Fashion-Pulse Dashboard", layout="wide", page_icon="👗")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=DM+Sans:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; background-color: #0d0f14; color: #e8e6e1; }
h1, h2, h3 { font-family: 'Playfair Display', serif !important; color: #f5c842 !important; }
.metric-card { background: linear-gradient(135deg, #1a1d27, #22263a); border: 1px solid #2e3450; border-radius: 16px; padding: 20px 24px; text-align: center; height: 100%; }
.metric-value { font-size: 1.6rem; font-weight: 700; color: #f5c842; }
.metric-label { font-size: 0.85rem; color: #8a8fa8; margin-top: 4px; }
.alert-box { background: linear-gradient(135deg, #2a1515, #3a1a1a); border-left: 4px solid #ff4f4f; border-radius: 10px; padding: 16px 20px; margin: 10px 0; }
.success-box { background: linear-gradient(135deg, #0f2a1a, #1a3a22); border-left: 4px solid #2ecc71; border-radius: 10px; padding: 16px 20px; margin: 10px 0; }
.voice-box { background: linear-gradient(135deg, #1a1527, #22163a); border: 1px solid #6d28d9; border-radius: 12px; padding: 16px 20px; margin: 16px 0; text-align: center; }
.ai-box { background: linear-gradient(135deg, #0f1a2a, #1a2a3a); border: 1px solid #0ea5e9; border-radius: 12px; padding: 20px 24px; margin: 10px 0; }
.target-box { background: linear-gradient(135deg, #1a1d27, #22263a); border: 1px solid #f5c842; border-radius: 16px; padding: 20px; margin: 10px 0; }
.barcode-box { background: linear-gradient(135deg, #0f1a2a, #1a2a3a); border: 1px solid #0ea5e9; border-radius: 12px; padding: 16px 20px; margin: 10px 0; }
.discount-badge { background: #ff4f4f; color: white; padding: 3px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: bold; }
div[data-testid="stTabs"] button { font-family: 'DM Sans', sans-serif; font-size: 0.9rem; color: #8a8fa8; }
div[data-testid="stTabs"] button[aria-selected="true"] { color: #f5c842 !important; border-bottom: 2px solid #f5c842 !important; }
.stButton > button { background: linear-gradient(135deg, #f5c842, #e8a820); color: #0d0f14; font-weight: 600; border: none; border-radius: 10px; padding: 10px 24px; font-family: 'DM Sans', sans-serif; transition: all 0.2s ease; }
.stButton > button:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(245, 200, 66, 0.35); }
.stDataFrame { border-radius: 12px; overflow: hidden; }
section[data-testid="stSidebar"] { background: linear-gradient(180deg, #13161f, #1a1d27); border-right: 1px solid #2e3450; }
hr { border-color: #2e3450; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# DATABASE FUNCTIONS
# ─────────────────────────────────────────────
import os

def get_connection():
    url = os.environ.get("DATABASE_URL", "postgresql://postgres:gxqVNPIpkdHRmKUSpgqqQwdRBeLDMffv@shuttle.proxy.rlwy.net:29286/railway")
    return psycopg2.connect(url)

@st.cache_data(ttl=30)
def get_products():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM products", conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_sales():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM sales ORDER BY sale_date DESC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_monthly_stats():
    try:
        conn = get_connection()
        df = pd.read_sql_query("""
            SELECT COALESCE(SUM(sale_price * quantity_sold), 0) as monthly_revenue,
                COALESCE(SUM((sale_price - cost_price) * quantity_sold), 0) as monthly_profit,
                COALESCE(SUM(quantity_sold), 0) as monthly_qty,
                COALESCE(COUNT(DISTINCT item_name), 0) as items_sold
            FROM sales
            WHERE EXTRACT(MONTH FROM sale_date) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM sale_date) = EXTRACT(YEAR FROM CURRENT_DATE)
        """, conn)
        conn.close()
        return df.iloc[0]
    except:
        return None

@st.cache_data(ttl=30)
def get_top_products():
    try:
        conn = get_connection()
        df = pd.read_sql_query("""
            SELECT item_name, SUM(quantity_sold) as total_qty, SUM(sale_price * quantity_sold) as total_revenue
            FROM sales
            WHERE EXTRACT(MONTH FROM sale_date) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM sale_date) = EXTRACT(YEAR FROM CURRENT_DATE)
            GROUP BY item_name ORDER BY total_revenue DESC LIMIT 5
        """, conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_category_profit():
    try:
        conn = get_connection()
        df = pd.read_sql_query("""
            SELECT p.category,
                COALESCE(SUM(s.sale_price * s.quantity_sold), 0) as total_revenue,
                COALESCE(SUM((s.sale_price - s.cost_price) * s.quantity_sold), 0) as total_profit,
                COALESCE(SUM(s.quantity_sold), 0) as total_qty
            FROM products p LEFT JOIN sales s ON p.item_name = s.item_name
            GROUP BY p.category ORDER BY total_profit DESC
        """, conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_restocks():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM restocks ORDER BY restock_date DESC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_customers():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM customers ORDER BY total_purchases DESC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_weekly_sales():
    try:
        conn = get_connection()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        df = pd.read_sql_query(f"""
            SELECT item_name, SUM(quantity_sold) as qty,
                SUM(sale_price * quantity_sold) as revenue,
                SUM((sale_price - cost_price) * quantity_sold) as profit
            FROM sales WHERE sale_date >= '{week_start}'
            GROUP BY item_name ORDER BY revenue DESC
        """, conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_target():
    try:
        conn = get_connection()
        month_name = date.today().strftime('%B')
        year = date.today().year
        df = pd.read_sql_query(f"SELECT * FROM targets WHERE month='{month_name}' AND year={year}", conn)
        conn.close()
        return df.iloc[0] if not df.empty else None
    except:
        return None

@st.cache_data(ttl=30)
def get_discounts():
    try:
        conn = get_connection()
        df = pd.read_sql_query(f"SELECT * FROM discounts WHERE is_active=TRUE AND end_date >= '{date.today()}'", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=30)
def get_suppliers():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM suppliers ORDER BY supplier_name", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

def get_user(username, password):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        conn.close()
        return user
    except:
        return None

def run_query(query, params=()):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Database error: {e}")
        return False


# ─────────────────────────────────────────────
# BARCODE SCANNER FUNCTION
# ─────────────────────────────────────────────
def scan_barcode(image_file):
    if not PYZBAR_AVAILABLE:
        return None
    try:
        image = Image.open(image_file)
        img_array = np.array(image)
        barcodes = pyzbar.decode(img_array)
        if barcodes:
            return barcodes[0].data.decode('utf-8')
        return None
    except:
        return None

# ─────────────────────────────────────────────
# VOICE FUNCTION
# ─────────────────────────────────────────────
def generate_voice_summary(total_products, low_stock_count, total_value, monthly_rev, monthly_prof, monthly_qty, top_product, low_stock_names, profit_margin):
    text = f"""Welcome to AI Fashion-Pulse Smart Inventory System.
    Current inventory status: {total_products} products in stock.
    Low stock alert: {low_stock_count} items need immediate restocking.
    Total inventory value: Rs. {total_value:,.0f}.
    This month: Revenue Rs. {monthly_rev:,.0f}. Profit Rs. {monthly_prof:,.0f}.
    Profit margin: {profit_margin:.1f} percent. Units sold: {monthly_qty}.
    Top selling product: {top_product}.
    Critical restock needed for: {low_stock_names}.
    Thank you for using AI Fashion-Pulse System."""
    tts = gTTS(text=text, lang='en', slow=False)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
        tts.save(f.name)
        return f.name


# ─────────────────────────────────────────────
# INVOICE GENERATOR
# ─────────────────────────────────────────────
def generate_invoice_html(invoice_num, customer_name, customer_phone, items, total):
    today_str = date.today().strftime("%d %B %Y")
    rows = ""
    for item in items:
        rows += f"<tr><td style='padding:8px; border-bottom:1px solid #2e3450;'>{item['name']}</td><td style='padding:8px; border-bottom:1px solid #2e3450; text-align:center;'>{item['qty']}</td><td style='padding:8px; border-bottom:1px solid #2e3450; text-align:right;'>Rs. {item['price']:,.2f}</td><td style='padding:8px; border-bottom:1px solid #2e3450; text-align:right;'>Rs. {item['qty']*item['price']:,.2f}</td></tr>"
    return f"""<html><body style="font-family:Arial; background:#0d0f14; color:#e8e6e1; padding:30px;">
    <div style="max-width:600px; margin:auto; background:#1a1d27; border-radius:16px; padding:30px; border:1px solid #2e3450;">
    <div style="text-align:center; margin-bottom:20px;"><h1 style="color:#f5c842;">👗 AI Fashion-Pulse</h1><p style="color:#8a8fa8;">Smart Inventory System</p></div>
    <div style="display:flex; justify-content:space-between; margin-bottom:20px;">
    <div><p style="color:#8a8fa8; margin:0;">Invoice To:</p><p style="font-weight:bold;">{customer_name}</p><p style="color:#8a8fa8;">{customer_phone}</p></div>
    <div style="text-align:right;"><p style="color:#8a8fa8;">Invoice #: <strong style="color:#f5c842;">{invoice_num}</strong></p><p style="color:#8a8fa8;">Date: {today_str}</p></div></div>
    <table style="width:100%; border-collapse:collapse;"><thead><tr style="background:#22263a;">
    <th style="padding:10px; text-align:left; color:#f5c842;">Product</th><th style="padding:10px; text-align:center; color:#f5c842;">Qty</th>
    <th style="padding:10px; text-align:right; color:#f5c842;">Price</th><th style="padding:10px; text-align:right; color:#f5c842;">Total</th>
    </tr></thead><tbody>{rows}</tbody></table>
    <div style="text-align:right; margin-top:20px; border-top:2px solid #f5c842; padding-top:10px;"><h2 style="color:#f5c842;">Total: Rs. {total:,.2f}</h2></div>
    <p style="text-align:center; color:#8a8fa8; margin-top:20px;">Thank you for shopping with AI Fashion-Pulse! 🙏</p></div></body></html>"""


# ─────────────────────────────────────────────
# LOGIN SYSTEM
# ─────────────────────────────────────────────
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.full_name = ""
if 'scanned_product' not in st.session_state:
    st.session_state.scanned_product = None

if not st.session_state.logged_in:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_login = st.columns([1, 2, 1])[1]
    with col_login:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#1a1d27,#22263a); border:1px solid #2e3450; border-radius:20px; padding:40px; text-align:center;">
            <h1 style="color:#f5c842; font-size:2rem;">👗</h1>
            <h2 style="color:#f5c842;">AI Fashion-Pulse</h2>
            <p style="color:#8a8fa8;">Smart Inventory System</p>
        </div>""", unsafe_allow_html=True)
        st.markdown("### 🔐 Login")
        username = st.text_input("Username", placeholder="owner / staff / manager", key="login_username")
        password = st.text_input("Password", type="password", placeholder="Enter password", key="login_password")
        if st.button("🚀 Login", use_container_width=True):
            user = get_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username = user[1]
                st.session_state.role = user[3]
                st.session_state.full_name = user[4]
                st.rerun()
            else:
                st.error("❌ Galat username ya password!")
        st.markdown("---")
        st.markdown("<p style='text-align:center; color:#8a8fa8; font-size:0.8rem;'>owner / owner123 &nbsp;|&nbsp; staff / staff123 &nbsp;|&nbsp; manager / manager123</p>", unsafe_allow_html=True)
    st.stop()


# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
df = get_products()
sales_df = get_sales()
monthly = get_monthly_stats()
top_products_df = get_top_products()
category_profit_df = get_category_profit()
restock_df = get_restocks()
customers_df = get_customers()
weekly_df = get_weekly_sales()
target = get_target()
discounts_df = get_discounts()
suppliers_df = get_suppliers()
role = st.session_state.role

monthly_rev = float(monthly['monthly_revenue']) if monthly is not None else 0
monthly_prof = float(monthly['monthly_profit']) if monthly is not None else 0
monthly_qty = int(monthly['monthly_qty']) if monthly is not None else 0
profit_margin = (monthly_prof / monthly_rev * 100) if monthly_rev > 0 else 0


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 👗 Fashion-Pulse")
    st.markdown(f"👤 **{st.session_state.full_name}**")
    role_colors = {"owner": "#f5c842", "manager": "#0ea5e9", "staff": "#2ecc71"}
    rc = role_colors.get(role, "#8a8fa8")
    st.markdown(f"<span style='background:{rc}; color:#0d0f14; padding:3px 10px; border-radius:20px; font-size:0.8rem; font-weight:bold;'>{role.upper()}</span>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### 🔍 Filter Inventory")
    if not df.empty:
        category_filter = st.multiselect("Category", options=df['category'].unique(), default=df['category'].unique(), key="sidebar_cat")
        stock_status = st.radio("Stock Status", ["All", "Low Stock", "In Stock"], key="sidebar_stock")
        search_query = st.text_input("🔎 Search Product", placeholder="e.g. Summer Kurta", key="sidebar_search")
    else:
        category_filter = []
        stock_status = "All"
        search_query = ""
    st.markdown("---")
    st.markdown(f"### 📅 {date.today().strftime('%d %B %Y')}")
    st.markdown("---")
    if monthly is not None:
        st.markdown("### 📊 This Month")
        st.markdown(f"💰 **Rs. {monthly_rev:,.2f}**")
        st.markdown(f"📈 **Rs. {monthly_prof:,.2f}**")
        st.markdown(f"📦 **{monthly_qty} units**")
    st.markdown("---")
    if st.button("🚪 Logout", key="logout_btn"):
        st.session_state.logged_in = False
        st.session_state.scanned_product = None
        st.rerun()


# ─────────────────────────────────────────────
# FILTER LOGIC
# ─────────────────────────────────────────────
if not df.empty and category_filter:
    filtered_df = df[df['category'].isin(category_filter)]
    if 'min_threshold' in filtered_df.columns:
        if stock_status == "Low Stock":
            filtered_df = filtered_df[filtered_df['current_stock'] <= filtered_df['min_threshold']]
        elif stock_status == "In Stock":
            filtered_df = filtered_df[filtered_df['current_stock'] > filtered_df['min_threshold']]
    if search_query:
        filtered_df = filtered_df[filtered_df['item_name'].str.contains(search_query, case=False, na=False)]
else:
    filtered_df = df.copy() if not df.empty else pd.DataFrame()

if not filtered_df.empty and 'min_threshold' in filtered_df.columns:
    low_stock_items = filtered_df[filtered_df['current_stock'] <= filtered_df['min_threshold']]
elif not filtered_df.empty:
    low_stock_items = filtered_df[filtered_df['current_stock'] <= 5]
else:
    low_stock_items = pd.DataFrame()

total_value = (filtered_df['current_stock'] * filtered_df['price']).sum() if not filtered_df.empty else 0
total_sold = sales_df['quantity_sold'].sum() if not sales_df.empty else 0


# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown("# 👗 AI Fashion-Pulse: Smart Inventory Dashboard")
st.markdown("---")


# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
if role == "staff":
    tab1, tab2 = st.tabs(["📊 Dashboard", "🛒 Record Sale"])
    tab3 = tab4 = tab5 = tab6 = tab7 = tab8 = tab9 = tab10 = None
else:
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "📊 Dashboard", "🛒 Record Sale", "➕ Add Product",
        "✏️ Edit / Delete", "📥 Export Data", "📋 Restock History",
        "👥 Customers", "🤖 AI Predictions", "🏭 Suppliers", "⚙️ Settings"
    ])


# ════════════════════════════════════
# TAB 1: DASHBOARD
# ════════════════════════════════════
with tab1:
    if not filtered_df.empty:
        if not low_stock_items.empty:
            st.markdown(f'<div class="alert-box">⚠️ <strong>{len(low_stock_items)} items</strong> need restocking! — {", ".join(low_stock_items["item_name"].tolist())}</div>', unsafe_allow_html=True)

        if not discounts_df.empty:
            disc_items = ', '.join([f"{r['item_name']} ({r['discount_percent']}% off)" for _, r in discounts_df.iterrows()])
            st.markdown(f'<div style="background:linear-gradient(135deg,#1a2a0f,#2a3a1a); border-left:4px solid #f5c842; border-radius:10px; padding:12px 20px; margin:10px 0;">🏷️ <strong>Active Discounts:</strong> {disc_items}</div>', unsafe_allow_html=True)

        if target is not None:
            target_rev = float(target['target_revenue'])
            progress = min((monthly_rev / target_rev * 100), 100) if target_rev > 0 else 0
            pcol = "#2ecc71" if progress >= 80 else "#f5c842" if progress >= 50 else "#ff4f4f"
            st.markdown(f"""<div class="target-box">
                <p style="color:#f5c842; font-weight:bold; margin:0 0 8px 0;">🎯 Monthly Target — {date.today().strftime('%B %Y')}</p>
                <p style="color:#e8e6e1; margin:0 0 8px 0;">Achieved: <strong>Rs. {monthly_rev:,.2f}</strong> / Target: <strong>Rs. {target_rev:,.2f}</strong></p>
                <div style="background:#2e3450; border-radius:20px; height:20px; overflow:hidden;">
                    <div style="background:{pcol}; width:{progress}%; height:100%; border-radius:20px;"></div>
                </div>
                <p style="color:{pcol}; font-weight:bold; margin:8px 0 0 0;">{progress:.1f}% {'🎉' if progress >= 100 else '💪'}</p>
            </div>""", unsafe_allow_html=True)

        st.markdown("#### 📦 Inventory Overview")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f'<div class="metric-card"><div class="metric-value">{len(filtered_df)}</div><div class="metric-label">Total Products</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#ff4f4f">{len(low_stock_items)}</div><div class="metric-label">Low Stock Alerts ⚠️</div></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="metric-card"><div class="metric-value">Rs. {total_value:,.2f}</div><div class="metric-label">Total Inventory Value</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("#### 📅 This Month's Performance")
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#a78bfa">Rs. {monthly_rev:,.2f}</div><div class="metric-label">📅 Monthly Revenue</div></div>', unsafe_allow_html=True)
        with m2: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#2ecc71">Rs. {monthly_prof:,.2f}</div><div class="metric-label">📈 Monthly Profit</div></div>', unsafe_allow_html=True)
        with m3: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#f5c842">{profit_margin:.1f}%</div><div class="metric-label">💹 Profit Margin</div></div>', unsafe_allow_html=True)
        with m4: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#38bdf8">{monthly_qty}</div><div class="metric-label">📦 Units This Month</div></div>', unsafe_allow_html=True)
        with m5: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#fb923c">{int(total_sold)}</div><div class="metric-label">🛍️ Total Ever Sold</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown('<div class="voice-box"><p style="color:#a78bfa; font-size:1rem; margin:0;">🎙️ <strong>AI Voice Summary</strong> — Click below to hear your dashboard report</p></div>', unsafe_allow_html=True)
        if st.button("🎙️ Play AI Voice Summary", key="voice_btn"):
            with st.spinner("Generating..."):
                try:
                    low_names = ', '.join(low_stock_items['item_name'].tolist()) if not low_stock_items.empty else "None"
                    top = top_products_df.iloc[0]['item_name'] if not top_products_df.empty else "N/A"
                    audio_file = generate_voice_summary(len(filtered_df), len(low_stock_items), total_value, monthly_rev, monthly_prof, monthly_qty, top, low_names, profit_margin)
                    st.audio(audio_file, format='audio/mp3')
                    st.success("✅ Voice summary ready!")
                    os.unlink(audio_file)
                except Exception as e:
                    st.error(f"Error: {e}")
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("### 📊 Visual Analytics")
        col_a, col_b = st.columns(2)
        with col_a:
            fig1 = px.bar(filtered_df, x='item_name', y='current_stock', color='current_stock', color_continuous_scale='teal', title="Stock Levels per Product", template="plotly_dark")
            fig1.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#e8e6e1')
            st.plotly_chart(fig1, use_container_width=True)
        with col_b:
            fig2 = px.pie(filtered_df, names='category', values='current_stock', hole=0.4, title="Category Distribution", template="plotly_dark", color_discrete_sequence=px.colors.sequential.Teal)
            fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='#e8e6e1')
            st.plotly_chart(fig2, use_container_width=True)

        if not sales_df.empty:
            st.markdown("### 📈 Sales Analytics")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                sales_trend = sales_df.groupby('sale_date')['quantity_sold'].sum().reset_index()
                fig3 = px.line(sales_trend, x='sale_date', y='quantity_sold', title="Daily Units Sold Trend", template="plotly_dark", color_discrete_sequence=['#f5c842'])
                fig3.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#e8e6e1')
                st.plotly_chart(fig3, use_container_width=True)
            with col_s2:
                if not top_products_df.empty:
                    fig4 = px.bar(top_products_df, x='item_name', y='total_revenue', title="Top 5 Products This Month", template="plotly_dark", color='total_revenue', color_continuous_scale='Purples')
                    fig4.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#e8e6e1')
                    st.plotly_chart(fig4, use_container_width=True)

        if not category_profit_df.empty:
            st.markdown("### 🏷️ Category-wise Profit Analysis")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                fig_cat = px.bar(category_profit_df, x='category', y='total_profit', title="Profit by Category", template="plotly_dark", color='total_profit', color_continuous_scale='Greens')
                fig_cat.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#e8e6e1')
                st.plotly_chart(fig_cat, use_container_width=True)
            with col_c2:
                fig_cat2 = px.pie(category_profit_df, names='category', values='total_revenue', title="Revenue Share by Category", template="plotly_dark", hole=0.4, color_discrete_sequence=px.colors.sequential.Purples_r)
                fig_cat2.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color='#e8e6e1')
                st.plotly_chart(fig_cat2, use_container_width=True)

        if not low_stock_items.empty:
            st.markdown("### 🚨 Critical Restock Items")
            dcols = ['item_name', 'category', 'current_stock', 'price']
            if 'min_threshold' in low_stock_items.columns: dcols.append('min_threshold')
            st.dataframe(low_stock_items[dcols], use_container_width=True)

        st.markdown("### 📝 Full Inventory Details")
        st.dataframe(filtered_df, use_container_width=True)
    else:
        st.info("No data found.")


# ════════════════════════════════════
# TAB 2: RECORD SALE + BARCODE
# ════════════════════════════════════
with tab2:
    st.markdown("### 🛒 Record a Sale")

    # ── BARCODE SCANNER ──────────────────────
    st.markdown("""
    <div class="barcode-box">
        <p style="color:#0ea5e9; font-weight:bold; margin:0 0 8px 0;">📷 Barcode Scanner</p>
        <p style="color:#8a8fa8; margin:0; font-size:0.85rem;">Product ka barcode scan karo — automatic select ho jaayega!</p>
    </div>
    """, unsafe_allow_html=True)

    bc_col1, bc_col2 = st.columns([1, 2])
    with bc_col1:
        uploaded_barcode = st.file_uploader(
            "📸 Upload Barcode Image",
            type=['png', 'jpg', 'jpeg'],
            key="barcode_upload",
            help="Product ka barcode photo upload karo"
        )

    with bc_col2:
        if uploaded_barcode is not None:
            image = Image.open(uploaded_barcode)
            st.image(image, caption="Uploaded Image", width=200)
            barcode_data = scan_barcode(uploaded_barcode)

            if barcode_data:
                st.success(f"✅ Barcode detected: **{barcode_data}**")
                if not df.empty:
                    matched = df[df['item_name'].str.lower().str.contains(barcode_data.lower(), na=False)]
                    if not matched.empty:
                        st.success(f"🎯 Product found: **{matched.iloc[0]['item_name']}**")
                        st.session_state.scanned_product = matched.iloc[0]['item_name']
                    else:
                        # Try exact match
                        exact = df[df['item_name'].str.lower() == barcode_data.lower()]
                        if not exact.empty:
                            st.success(f"🎯 Product found: **{exact.iloc[0]['item_name']}**")
                            st.session_state.scanned_product = exact.iloc[0]['item_name']
                        else:
                            st.warning(f"⚠️ '{barcode_data}' database mein nahi mila. Manual select karo.")
            else:
                st.error("❌ Barcode detect nahi hua. Clear image upload karein.")

        if st.session_state.scanned_product:
            st.markdown(f'<div class="success-box">🎯 Scanned Product: <strong>{st.session_state.scanned_product}</strong></div>', unsafe_allow_html=True)
            if st.button("🔄 Clear Scan", key="clear_scan_btn"):
                st.session_state.scanned_product = None
                st.rerun()

    st.markdown("---")

    # ── SALE FORM ────────────────────────────
    if not df.empty:
        col1, col2, col3 = st.columns(3)

        # Auto-select scanned product
        product_list = df['item_name'].tolist()
        default_idx = 0
        if st.session_state.scanned_product and st.session_state.scanned_product in product_list:
            default_idx = product_list.index(st.session_state.scanned_product)

        with col1:
            sale_item = st.selectbox("Select Product", product_list, index=default_idx, key="sale_product_select")
        with col2:
            sale_qty = st.number_input("Quantity Sold", min_value=1, step=1, value=1, key="sale_qty_input")
        with col3:
            sale_price_default = float(df[df['item_name'] == sale_item]['price'].values[0]) if sale_item else 0.0
            disc_row = discounts_df[discounts_df['item_name'] == sale_item] if not discounts_df.empty else pd.DataFrame()
            if not disc_row.empty:
                disc_pct = float(disc_row.iloc[0]['discount_percent'])
                discounted_price = sale_price_default * (1 - disc_pct / 100)
                st.markdown(f'<span class="discount-badge">{disc_pct}% OFF</span> Original: Rs. {sale_price_default:,.2f}', unsafe_allow_html=True)
                sale_price = st.number_input("Sale Price (Rs.)", min_value=0.0, step=100.0, value=discounted_price, key="sale_price_disc")
            else:
                sale_price = st.number_input("Sale Price (Rs.)", min_value=0.0, step=100.0, value=sale_price_default, key="sale_price_normal")

        cost_default = sale_price_default * 0.6
        cost_price = st.number_input("Cost Price (Rs.)", min_value=0.0, step=100.0, value=cost_default, key="sale_cost_input")

        if sale_item:
            current_stock_val = int(df[df['item_name'] == sale_item]['current_stock'].values[0])
            thresh = int(df[df['item_name'] == sale_item]['min_threshold'].values[0]) if 'min_threshold' in df.columns else 5
            if current_stock_val <= thresh:
                st.warning(f"⚠️ Low stock! Only {current_stock_val} units available.")
            else:
                st.info(f"✅ Available stock: {current_stock_val} units")

        cust_names = ["Walk-in Customer"] + (customers_df['name'].tolist() if not customers_df.empty else [])
        selected_customer = st.selectbox("Customer", cust_names, key="sale_customer_select")

        if st.button("✅ Confirm Sale", key="confirm_sale_btn"):
            current = int(df[df['item_name'] == sale_item]['current_stock'].values[0])
            if sale_qty > current:
                st.error(f"❌ Not enough stock! Available: {current} units")
            else:
                s1 = run_query("INSERT INTO sales (item_name, quantity_sold, sale_price, cost_price, sale_date) VALUES (%s, %s, %s, %s, %s)", (sale_item, sale_qty, sale_price, cost_price, date.today()))
                s2 = run_query("UPDATE products SET current_stock = current_stock - %s WHERE item_name = %s", (sale_qty, sale_item))
                if selected_customer != "Walk-in Customer":
                    run_query("UPDATE customers SET total_purchases = total_purchases + %s WHERE name = %s", (sale_price * sale_qty, selected_customer))
                if s1 and s2:
                    profit = (sale_price - cost_price) * sale_qty
                    st.markdown(f'<div class="success-box">✅ Sale recorded! <strong>{sale_qty}x {sale_item}</strong> for Rs. {sale_price:,.2f} each.<br>💰 Profit: <strong>Rs. {profit:,.2f}</strong></div>', unsafe_allow_html=True)
                    invoice_html = generate_invoice_html(f"INV-{date.today().strftime('%Y%m%d')}-{sale_qty}", selected_customer, "", [{'name': sale_item, 'qty': sale_qty, 'price': sale_price}], sale_price * sale_qty)
                    st.download_button("⬇️ Download Invoice", data=invoice_html.encode(), file_name=f"invoice_{date.today()}.html", mime="text/html", key="invoice_download")
                    st.session_state.scanned_product = None
                    st.cache_data.clear()
                    st.rerun()

    if not sales_df.empty:
        st.markdown("### 📋 Sales History")
        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            filter_type = st.selectbox("Quick Filter", ["All Time", "Today", "This Week", "This Month", "Custom Range"], key="sales_filter_type")
        today = date.today()
        if filter_type == "Today": start_date, end_date = today, today
        elif filter_type == "This Week": start_date, end_date = today - timedelta(days=today.weekday()), today
        elif filter_type == "This Month": start_date, end_date = today.replace(day=1), today
        elif filter_type == "Custom Range":
            with dc2: start_date = st.date_input("Start Date", value=today.replace(day=1), key="sales_start_date")
            with dc3: end_date = st.date_input("End Date", value=today, key="sales_end_date")
        else: start_date, end_date = None, None

        filtered_sales = sales_df.copy()
        if start_date and end_date:
            filtered_sales['sale_date'] = pd.to_datetime(filtered_sales['sale_date']).dt.date
            filtered_sales = filtered_sales[(filtered_sales['sale_date'] >= start_date) & (filtered_sales['sale_date'] <= end_date)]

        if not filtered_sales.empty:
            fs_rev = (filtered_sales['sale_price'] * filtered_sales['quantity_sold']).sum()
            fs_profit = ((filtered_sales['sale_price'] - filtered_sales['cost_price']) * filtered_sales['quantity_sold']).sum()
            fs_qty = filtered_sales['quantity_sold'].sum()
            fs1, fs2, fs3 = st.columns(3)
            with fs1: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#a78bfa">Rs. {fs_rev:,.2f}</div><div class="metric-label">Revenue</div></div>', unsafe_allow_html=True)
            with fs2: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#2ecc71">Rs. {fs_profit:,.2f}</div><div class="metric-label">Profit</div></div>', unsafe_allow_html=True)
            with fs3: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#38bdf8">{int(fs_qty)}</div><div class="metric-label">Units Sold</div></div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(filtered_sales, use_container_width=True)
        else:
            st.info("Is period mein koi sales nahi mili.")


# ════════════════════════════════════
# OWNER / MANAGER TABS
# ════════════════════════════════════
if role in ["owner", "manager"]:

    with tab3:
        st.markdown("### ➕ Add New Product")
        with st.form("inventory_form", clear_on_submit=True):
            cf1, cf2, cf3 = st.columns(3)
            with cf1:
                new_name = st.text_input("Product Name", placeholder="e.g. Silk Dupatta", key="add_name")
                new_cat = st.text_input("Category", placeholder="e.g. Ethnic", key="add_cat")
            with cf2:
                new_size = st.selectbox("Size", ["S", "M", "L", "XL", "Free Size", "N/A"], key="add_size")
                new_color = st.text_input("Color", placeholder="e.g. Red", key="add_color")
            with cf3:
                new_stock = st.number_input("Current Stock", min_value=0, step=1, value=10, key="add_stock")
                new_price = st.number_input("Price (Rs.)", min_value=0, step=100, value=1500, key="add_price")
            new_threshold = st.number_input("Min Threshold", min_value=1, step=1, value=5, key="add_threshold")
            submit_button = st.form_submit_button("➕ Add Product")
        if submit_button:
            if new_name and new_cat:
                success = run_query("INSERT INTO products (item_name, category, current_stock, price, size, color, min_threshold) VALUES (%s, %s, %s, %s, %s, %s, %s)", (new_name, new_cat, new_stock, new_price, new_size, new_color, new_threshold))
                if success:
                    st.markdown(f'<div class="success-box">✅ <strong>{new_name}</strong> added!</div>', unsafe_allow_html=True)
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.warning("⚠️ Name aur Category zaruri hain.")

    with tab4:
        st.markdown("### ✏️ Edit or Delete a Product")
        if not df.empty:
            selected_product = st.selectbox("Select Product", df['item_name'].tolist(), key="edit_product_select")
            product_row = df[df['item_name'] == selected_product].iloc[0]
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### ✏️ Edit")
                with st.form("edit_form"):
                    edit_cat = st.text_input("Category", value=str(product_row.get('category', '')), key="edit_cat")
                    edit_size = st.selectbox("Size", ["S", "M", "L", "XL", "Free Size", "N/A"], index=["S", "M", "L", "XL", "Free Size", "N/A"].index(str(product_row.get('size', 'N/A'))) if str(product_row.get('size', 'N/A')) in ["S", "M", "L", "XL", "Free Size", "N/A"] else 5, key="edit_size")
                    edit_color = st.text_input("Color", value=str(product_row.get('color', '')), key="edit_color")
                    edit_stock = st.number_input("Current Stock", min_value=0, step=1, value=int(product_row.get('current_stock', 0)), key="edit_stock")
                    edit_price = st.number_input("Price (Rs.)", min_value=0, step=100, value=int(product_row.get('price', 0)), key="edit_price")
                    edit_threshold = st.number_input("Min Threshold", min_value=1, step=1, value=int(product_row.get('min_threshold', 5)), key="edit_threshold")
                    update_btn = st.form_submit_button("💾 Save Changes")
                if update_btn:
                    success = run_query("UPDATE products SET category=%s, size=%s, color=%s, current_stock=%s, price=%s, min_threshold=%s WHERE item_name=%s", (edit_cat, edit_size, edit_color, edit_stock, edit_price, edit_threshold, selected_product))
                    if success:
                        st.success("✅ Updated!")
                        st.cache_data.clear()
                        st.rerun()
            with col2:
                st.markdown("#### 🗑️ Delete")
                st.warning(f"Delete **'{selected_product}'**?")
                confirm_delete = st.checkbox("Haan, delete karna chahti/chahta hun", key="delete_confirm")
                if st.button("🗑️ Delete Product", disabled=not confirm_delete, key="delete_btn"):
                    success = run_query("DELETE FROM products WHERE item_name = %s", (selected_product,))
                    if success:
                        st.success("🗑️ Deleted!")
                        st.cache_data.clear()
                        st.rerun()

    with tab5:
        st.markdown("### 📥 Export Data")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📦 Inventory")
            if not df.empty:
                st.download_button("⬇️ Inventory CSV", data=df.to_csv(index=False).encode('utf-8'), file_name=f"inventory_{date.today()}.csv", mime="text/csv", key="inv_csv")
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer: df.to_excel(writer, index=False, sheet_name='Inventory')
                st.download_button("⬇️ Inventory Excel", data=buffer.getvalue(), file_name=f"inventory_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="inv_excel")
        with col2:
            st.markdown("#### 🛒 Sales")
            if not sales_df.empty:
                st.download_button("⬇️ Sales CSV", data=sales_df.to_csv(index=False).encode('utf-8'), file_name=f"sales_{date.today()}.csv", mime="text/csv", key="sales_csv")
                buffer2 = io.BytesIO()
                with pd.ExcelWriter(buffer2, engine='openpyxl') as writer: sales_df.to_excel(writer, index=False, sheet_name='Sales')
                st.download_button("⬇️ Sales Excel", data=buffer2.getvalue(), file_name=f"sales_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="sales_excel")
        pv1, pv2 = st.tabs(["Inventory", "Sales"])
        with pv1:
            if not df.empty: st.dataframe(df, use_container_width=True)
        with pv2:
            if not sales_df.empty: st.dataframe(sales_df, use_container_width=True)
            else: st.info("Koi sales nahi.")

    with tab6:
        st.markdown("### 📋 Restock History")
        with st.form("restock_form", clear_on_submit=True):
            rc1, rc2, rc3 = st.columns(3)
            with rc1: restock_item = st.selectbox("Product", df['item_name'].tolist() if not df.empty else [], key="restock_item_select")
            with rc2: restock_qty = st.number_input("Quantity Added", min_value=1, step=1, value=10, key="restock_qty")
            with rc3: restock_notes = st.text_input("Notes", placeholder="e.g. Monthly restock", key="restock_notes")
            restock_btn = st.form_submit_button("✅ Record Restock")
        if restock_btn:
            r1 = run_query("INSERT INTO restocks (item_name, quantity_added, restock_date, notes) VALUES (%s, %s, %s, %s)", (restock_item, restock_qty, date.today(), restock_notes))
            r2 = run_query("UPDATE products SET current_stock = current_stock + %s WHERE item_name = %s", (restock_qty, restock_item))
            if r1 and r2:
                st.markdown(f'<div class="success-box">✅ {restock_qty} units added to {restock_item}!</div>', unsafe_allow_html=True)
                st.cache_data.clear()
                st.rerun()
        restock_df = get_restocks()
        if not restock_df.empty:
            r1c, r2c, r3c = st.columns(3)
            with r1c: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#2ecc71">{len(restock_df)}</div><div class="metric-label">Total Restocks</div></div>', unsafe_allow_html=True)
            with r2c: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#38bdf8">{restock_df["quantity_added"].sum()}</div><div class="metric-label">Units Restocked</div></div>', unsafe_allow_html=True)
            with r3c: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#f5c842">{restock_df["item_name"].nunique()}</div><div class="metric-label">Products Restocked</div></div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(restock_df, use_container_width=True)

    with tab7:
        st.markdown("### 👥 Customer Management")
        with st.form("customer_form", clear_on_submit=True):
            cst1, cst2 = st.columns(2)
            with cst1:
                cust_name = st.text_input("Name", placeholder="e.g. Ayesha Khan", key="cust_name")
                cust_phone = st.text_input("Phone", placeholder="e.g. 0300-1234567", key="cust_phone")
            with cst2:
                cust_email = st.text_input("Email", placeholder="optional", key="cust_email")
                cust_address = st.text_input("Address", placeholder="optional", key="cust_address")
            cust_btn = st.form_submit_button("➕ Add Customer")
        if cust_btn and cust_name:
            success = run_query("INSERT INTO customers (name, phone, email, address, total_purchases) VALUES (%s, %s, %s, %s, 0)", (cust_name, cust_phone, cust_email, cust_address))
            if success:
                st.markdown(f'<div class="success-box">✅ {cust_name} added!</div>', unsafe_allow_html=True)
                st.cache_data.clear()
                st.rerun()
        customers_df = get_customers()
        if not customers_df.empty:
            cu1, cu2, cu3 = st.columns(3)
            with cu1: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#a78bfa">{len(customers_df)}</div><div class="metric-label">Total Customers</div></div>', unsafe_allow_html=True)
            with cu2: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#f5c842; font-size:1.2rem;">{customers_df.iloc[0]["name"]}</div><div class="metric-label">🏆 Top Customer</div></div>', unsafe_allow_html=True)
            with cu3: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#2ecc71">Rs. {customers_df["total_purchases"].sum():,.2f}</div><div class="metric-label">Total Revenue</div></div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.dataframe(customers_df, use_container_width=True)
        else:
            st.info("Koi customer nahi mila.")

    with tab8:
        st.markdown("### 🤖 AI-Powered Predictions & Insights")
        if not weekly_df.empty:
            st.markdown("#### 📊 This Week's Report")
            w1, w2, w3 = st.columns(3)
            with w1: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#a78bfa">Rs. {weekly_df["revenue"].sum():,.2f}</div><div class="metric-label">Weekly Revenue</div></div>', unsafe_allow_html=True)
            with w2: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#2ecc71">Rs. {weekly_df["profit"].sum():,.2f}</div><div class="metric-label">Weekly Profit</div></div>', unsafe_allow_html=True)
            with w3: st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#38bdf8">{int(weekly_df["qty"].sum())}</div><div class="metric-label">Weekly Units</div></div>', unsafe_allow_html=True)
            st.dataframe(weekly_df, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 🌟 Seasonal AI Predictions")
        current_month = date.today().month
        seasons = {
            3: ("🌸 Spring/Eid Season", ["Summer Kurta", "Embroidered Lawn Suit", "Chiffon Dupatta"], "Eid ul Fitr aa rahi hai! Ethnic wear demand highest hogi."),
            4: ("🌸 Spring/Eid Season", ["Summer Kurta", "Embroidered Lawn Suit", "Chiffon Dupatta"], "Eid ul Fitr season! Lawn suits aur kurtas stock barhao."),
            5: ("☀️ Summer Season", ["Cotton Shirt", "Silk Tunic", "Straight Pants"], "Garmi shuru. Light fabric products zyada biken ge."),
            6: ("☀️ Peak Summer", ["Cotton Shirt", "Silk Tunic", "heels"], "Peak summer — cotton aur light western wear demand mein."),
            7: ("🌧️ Monsoon Season", ["Velvet Shawl", "Casual Jeans", "Cotton Shirt"], "Barsaat ka mausam. Casual wear popular."),
            8: ("🌧️ Monsoon/Back to School", ["Casual Jeans", "Cotton Shirt", "Straight Pants"], "School/college season — casual western wear."),
            9: ("🍂 Autumn Season", ["Velvet Shawl", "Straight Cut Trousers", "heels"], "Thandi aa rahi hai. Shawls aur formal wear stock karo."),
            10: ("🍂 Eid ul Adha Prep", ["Embroidered Lawn Suit", "Summer Kurta", "party wear heels"], "Eid ul Adha ki tayari! Ethnic formal wear."),
            11: ("❄️ Winter Beginning", ["Velvet Shawl", "Casual Jeans", "Straight Cut Trousers"], "Thanda shuru. Winter accessories aur jeans."),
            12: ("❄️ Winter Peak", ["Velvet Shawl", "Embellished Clutch", "party wear heels"], "Winter weddings ka season. Party wear stock karo!"),
            1: ("❄️ Winter/Sale Season", ["Cotton Shirt", "Casual Jeans", "Silk Tunic"], "Clearance sale ka waqt hai."),
            2: ("💕 Valentine/Spring Prep", ["Embellished Clutch", "heels", "party wear heels"], "Valentine's Day — accessories popular."),
        }
        season_name, recommend_items, advice = seasons.get(current_month, ("General Season", [], "Regular stock maintenance karein."))
        st.markdown(f"""<div class="ai-box">
            <h3 style="color:#0ea5e9; margin:0 0 10px 0;">{season_name}</h3>
            <p style="color:#e8e6e1; margin:0 0 10px 0;">📅 {date.today().strftime('%B %Y')}</p>
            <p style="color:#8a8fa8; margin:0 0 15px 0;">{advice}</p>
            <p style="color:#f5c842; font-weight:bold; margin:0 0 8px 0;">🎯 Recommended Stock Up:</p>
            {''.join([f'<span style="background:#1a2a3a; color:#0ea5e9; padding:4px 12px; border-radius:20px; margin:4px; display:inline-block;">📦 {item}</span>' for item in recommend_items])}
        </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### 💡 AI Business Insights")
        if monthly_rev > 0:
            if profit_margin < 30: st.markdown("⚠️ **Low Profit Margin** — Cost prices check karein.")
            elif profit_margin > 50: st.markdown("✅ **Excellent Profit Margin** — Pricing strategy kaam kar rahi hai!")
            if not top_products_df.empty: st.markdown(f"🏆 **Best Performer** — {top_products_df.iloc[0]['item_name']} is month sabse zyada revenue.")
            if not low_stock_items.empty: st.markdown(f"🚨 **{len(low_stock_items)} items critical** — immediate restock zaruri.")
            if not customers_df.empty: st.markdown(f"👥 **{len(customers_df)} customers** — loyalty program start karein!")

    with tab9:
        st.markdown("### 🏭 Supplier Management")
        with st.form("supplier_form", clear_on_submit=True):
            sp1, sp2, sp3 = st.columns(3)
            with sp1:
                sup_name = st.text_input("Supplier Name", placeholder="e.g. Ahmed Textiles", key="sup_name")
                sup_phone = st.text_input("Phone", placeholder="e.g. 0300-1234567", key="sup_phone")
            with sp2:
                sup_email = st.text_input("Email", placeholder="optional", key="sup_email")
                sup_city = st.text_input("City", placeholder="e.g. Lahore", key="sup_city")
            with sp3:
                sup_cat = st.selectbox("Category", ["Ethnic", "Western", "Accessories", "Footwear", "makeup", "All"], key="sup_cat_select")
                sup_notes = st.text_input("Notes", placeholder="e.g. Reliable supplier", key="sup_notes")
            sup_btn = st.form_submit_button("➕ Add Supplier")
        if sup_btn and sup_name:
            success = run_query("INSERT INTO suppliers (supplier_name, phone, email, product_category, city, last_order_date, notes) VALUES (%s, %s, %s, %s, %s, %s, %s)", (sup_name, sup_phone, sup_email, sup_cat, sup_city, date.today(), sup_notes))
            if success:
                st.markdown(f'<div class="success-box">✅ Supplier <strong>{sup_name}</strong> added!</div>', unsafe_allow_html=True)
                st.cache_data.clear()
                st.rerun()
        suppliers_df = get_suppliers()
        if not suppliers_df.empty:
            st.markdown(f"#### 📋 All Suppliers ({len(suppliers_df)} total)")
            st.dataframe(suppliers_df, use_container_width=True)
        else:
            st.info("Koi supplier nahi mila.")

    with tab10:
        st.markdown("### ⚙️ Settings")
        st.markdown("#### 🎯 Set Monthly Sales Target")
        with st.form("target_form", clear_on_submit=True):
            t1, t2, t3 = st.columns(3)
            with t1: target_month = st.selectbox("Month", ["January","February","March","April","May","June","July","August","September","October","November","December"], index=date.today().month - 1, key="target_month_select")
            with t2: target_year = st.number_input("Year", min_value=2024, max_value=2030, value=date.today().year, key="target_year_input")
            with t3: target_revenue_input = st.number_input("Target Revenue (Rs.)", min_value=0, step=10000, value=200000, key="target_rev_input")
            target_units_input = st.number_input("Target Units", min_value=0, step=10, value=100, key="target_units_input")
            target_btn = st.form_submit_button("💾 Save Target")
        if target_btn:
            run_query("DELETE FROM targets WHERE month=%s AND year=%s", (target_month, target_year))
            success = run_query("INSERT INTO targets (month, year, target_revenue, target_units) VALUES (%s, %s, %s, %s)", (target_month, target_year, target_revenue_input, target_units_input))
            if success:
                st.success(f"✅ Target set: Rs. {target_revenue_input:,} for {target_month} {target_year}")
                st.cache_data.clear()

        st.markdown("---")
        st.markdown("#### 🏷️ Manage Discounts")
        with st.form("discount_form", clear_on_submit=True):
            d1, d2, d3 = st.columns(3)
            with d1: disc_item = st.selectbox("Product", df['item_name'].tolist() if not df.empty else [], key="disc_product_select")
            with d2: disc_pct_input = st.number_input("Discount %", min_value=1, max_value=90, step=5, value=10, key="disc_pct_input")
            with d3:
                disc_start = st.date_input("Start Date", value=date.today(), key="disc_start_date")
                disc_end = st.date_input("End Date", value=date.today() + timedelta(days=7), key="disc_end_date")
            disc_btn = st.form_submit_button("➕ Add Discount")
        if disc_btn:
            success = run_query("INSERT INTO discounts (item_name, discount_percent, start_date, end_date, is_active) VALUES (%s, %s, %s, %s, TRUE)", (disc_item, disc_pct_input, disc_start, disc_end))
            if success:
                st.success(f"✅ {disc_pct_input}% discount added for {disc_item}!")
                st.cache_data.clear()
                st.rerun()

        discounts_df = get_discounts()
        if not discounts_df.empty:
            st.markdown("#### 🏷️ Active Discounts")
            st.dataframe(discounts_df, use_container_width=True)
            disc_to_remove = st.selectbox("Remove Discount", discounts_df['item_name'].tolist(), key="remove_disc_select")
            if st.button("🗑️ Remove Discount", key="remove_disc_btn"):
                run_query("UPDATE discounts SET is_active=FALSE WHERE item_name=%s", (disc_to_remove,))
                st.success("✅ Discount removed!")
                st.cache_data.clear()
                st.rerun()














               