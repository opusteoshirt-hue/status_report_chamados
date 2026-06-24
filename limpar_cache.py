import os
import shutil
from pathlib import Path

# Remove arquivo de cache
cache_file = Path("dados_cache.pkl")
if cache_file.exists():
    cache_file.unlink()
    print("Cache removido com sucesso!")
else:
    print("Nenhum cache encontrado")

# Remove cache do Streamlit
streamlit_cache = Path(".streamlit/cache")
if streamlit_cache.exists():
    shutil.rmtree(streamlit_cache)
    print("Cache do Streamlit removido!")
