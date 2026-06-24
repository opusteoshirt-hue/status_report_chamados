import os

caminho = r"C:\Users\Gabriel\Documents\PROJETOS\Chamados_Dirtec\database\queries.py"

print("Verificando arquivo:", caminho)
print("Arquivo existe?", os.path.exists(caminho))
print()

if os.path.exists(caminho):
    with open(caminho, 'r', encoding='utf-8') as f:
        linhas = f.readlines()
    
    print(f"Total de linhas: {len(linhas)}")
    print("\nConteudo completo do arquivo:")
    print("-" * 50)
    for i, linha in enumerate(linhas, 1):
        print(f"{i:3d}: {linha.rstrip()}")
    print("-" * 50)
    
    # Verifica se tem INCIDENTES_SQL
    conteudo = ''.join(linhas)
    if 'INCIDENTES_SQL' in conteudo:
        print("\nVariavel INCIDENTES_SQL encontrada no arquivo")
    else:
        print("\nVariavel INCIDENTES_SQL NAO encontrada no arquivo")