# dashboard_styles.py
DASHBOARD_CSS = """
<style>
    /* Garante que a sidebar seja visível */
    [data-testid="stSidebar"] {
        display: block !important;
        min-width: 300px !important;
    }
    
    .stApp {
        margin-top: 0 !important;
    }
    
    /* CARDS KPI */
    div[style*="background: linear-gradient(135deg, #6B3FA0"],
    div[style*="background: linear-gradient(135deg, #1B5E20"],
    div[style*="background: linear-gradient(135deg, #9B6BCC"] {
        position: relative !important;
        overflow: hidden !important;
        cursor: pointer;
        transition: transform 0.22s ease, box-shadow 0.22s ease, filter 0.22s ease !important;
        animation: countUp 0.5s ease both;
    }
    
    div[style*="background: linear-gradient(135deg, #6B3FA0"]:hover,
    div[style*="background: linear-gradient(135deg, #1B5E20"]:hover,
    div[style*="background: linear-gradient(135deg, #9B6BCC"]:hover {
        transform: translateY(-4px) scale(1.02) !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.2) !important;
        filter: brightness(1.08) !important;
    }
    
    /* RIPPLE EFFECT */
    .kpi-ripple {
        position: absolute;
        width: 80px;
        height: 80px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.45);
        pointer-events: none;
        animation: ripple-expand 0.65s ease-out forwards;
    }
    
    @keyframes ripple-expand {
        0%   { transform: translate(-50%, -50%) scale(0); opacity: 0.55; }
        100% { transform: translate(-50%, -50%) scale(4);  opacity: 0; }
    }
    
    @keyframes countUp {
        from { opacity: 0; transform: scale(0.85); }
        to   { opacity: 1; transform: scale(1); }
    }
    
    /* BOTÕES */
    .stButton > button {
        transition: all 0.2s ease !important;
        position: relative;
        overflow: hidden;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 5px 16px rgba(107, 63, 160, 0.3) !important;
    }
    
    /* INPUTS */
    input[type="text"]:focus, input[type="password"]:focus,
    input[type="email"]:focus, textarea:focus {
        border-color: #6B3FA0 !important;
        box-shadow: 0 0 0 3px rgba(107, 63, 160, 0.18) !important;
    }
    
    /* TABS */
    [aria-selected="true"][data-baseweb="tab"] {
        color: #6B3FA0 !important;
    }
    [data-baseweb="tab-highlight"] {
        background-color: #6B3FA0 !important;
    }
    
    /* PLOTLY CHARTS */
    [data-testid="stPlotlyChart"] {
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        border-radius: 10px;
    }
    [data-testid="stPlotlyChart"]:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.1);
    }
    
    /* DATAFRAME */
    [data-testid="stDataFrame"] {
        border-radius: 10px !important;
        overflow: hidden;
    }
    
    /* EXPANDERS */
    [data-testid="stExpander"] {
        border-radius: 8px !important;
    }
    
    /* SIDEBAR FILTERS */
    .stSidebar .stMarkdown, 
    .stSidebar .stButton,
    .stSidebar .stCheckbox,
    .stSidebar .stSelectbox,
    .stSidebar .stMultiselect,
    .stSidebar .stDateInput {
        display: block !important;
        visibility: visible !important;
    }
</style>
"""