# Substitui a função card_kpi no app.py
# O ripple agora está 100% dentro do HTML do card — sem depender de JS externo

from turtle import st


def card_kpi(titulo, valor, cor):
    uid = titulo.replace(" ", "_").lower()
    st.markdown(
        f"""
        <style>
            @keyframes kpi-ripple-anim {{
                0%   {{ transform: translate(-50%, -50%) scale(0); opacity: 0.55; }}
                100% {{ transform: translate(-50%, -50%) scale(5); opacity: 0; }}
            }}
            #kpi_{uid} {{
                background-color: {cor};
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                color: white;
                position: relative;
                overflow: hidden;
                cursor: pointer;
                transition: transform 0.22s ease, box-shadow 0.22s ease, filter 0.22s ease;
                user-select: none;
            }}
            #kpi_{uid}:hover {{
                transform: translateY(-4px) scale(1.02);
                box-shadow: 0 8px 24px rgba(0,0,0,0.22);
                filter: brightness(1.1);
            }}
            #kpi_{uid} h2 {{
                margin: 0;
                font-size: 28px;
                position: relative;
                z-index: 1;
            }}
            #kpi_{uid} p {{
                margin: 5px 0 0 0;
                font-size: 14px;
                position: relative;
                z-index: 1;
            }}
            #kpi_{uid} .ripple {{
                position: absolute;
                width: 80px;
                height: 80px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.45);
                pointer-events: none;
                animation: kpi-ripple-anim 0.65s ease-out forwards;
            }}
        </style>

        <div id="kpi_{uid}" onclick="(function(e){{
            var card = document.getElementById('kpi_{uid}');
            var rect = card.getBoundingClientRect();
            var x = e.clientX - rect.left;
            var y = e.clientY - rect.top;
            var r = document.createElement('span');
            r.className = 'ripple';
            r.style.left = x + 'px';
            r.style.top  = y + 'px';
            card.appendChild(r);
            r.addEventListener('animationend', function(){{ r.remove(); }});
        }})(event)">
            <h2>{valor}</h2>
            <p>{titulo}</p>
        </div>
        """,
        unsafe_allow_html=True
    )