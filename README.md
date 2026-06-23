# BMCView - Dashboard de Chamados

Sistema de dashboard analítico para monitoramento de chamados (Incidentes e Work Orders), com autenticação via Active Directory e integração com Banco de Dados.

---

## Índice

- [Sobre o Projeto](#-sobre-o-projeto)
- [Arquitetura](#-arquitetura)
- [Tecnologias](#-tecnologias)
- [Pré-requisitos](#-pré-requisitos)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Execução](#-execução)
- [Docker](#-docker)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Funcionalidades](#-funcionalidades)
- [Contribuição](#-contribuição)
- [Licença](#-licença)

---

##  Sobre o Projeto

**BMCView** é uma aplicação desenvolvida em Python com Streamlit que consolida dados de chamados do BMC (Incidentes e Work Orders) armazenados em um banco de dados, apresentando-os em um dashboard interativo com:

-  **KPIs em tempo real**
-  **Gráficos interativos** (Plotly)
-  **Filtros avançados** por data, status, categoria, fila, cliente e título
-  **Gerenciamento de usuários** com autenticação via Active Directory
-  **Autorização por filas** com permissões granulares
-  **Exportação de dados** para CSV com encoding corrigido
-  **Persistência de sessão** via cookie (24 horas)

---

##  Arquitetura

```text
[USUARIO] --> [BROWSER] --> [STREAMLIT SERVER:8501] --> [APP.PY]
                                                           |
                                                           v
                                              [AUTH_MANAGER.PY]
                                                           |
                                                           v
                                    +----------------------+----------------------+
                                    |                      |                      |
                                    v                      v                      v
                            [ORACLE DB]             [ACTIVE DIRECTORY]      [DOCKER]
                            (chamados)              (autenticacao)          (container)
                                    |                      |                      |
                                    +----------------------+----------------------+
                                                           |
                                                           v
                                              [DADOS PROCESSADOS]
                                                           |
                                                           v
                                                [DASHBOARD/GRAPHS]
                                                           |
                                                           v
                                                  [USUARIO FINAL]
```

---

### Fluxo de Dados

1. Usuário acessa `http://localhost:PORTA`
2. Autenticação via **Active Directory** (NTLM/SIMPLE)
3. Busca dados no **Oracle Database** (incidentes e work orders)
4. Processamento com **Pandas** e **Plotly**
5. Exibição do **Dashboard** interativo
6. **Cache** dos dados por 2 horas (arquivos `.pkl`)
7. **Logs** salvos em `logs/`

---

##  Tecnologias

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| **Python** | 3.11+ | Linguagem principal |
| **Streamlit** | 1.28+ | Framework do dashboard |
| **Pandas** | 2.0+ | Manipulação de dados |
| **Plotly** | 5.17+ | Gráficos interativos |
| **OracleDB** | 2.0+ | Conexão com Oracle |
| **LDAP3** | 2.9+ | Autenticação AD |
| **Python-dotenv** | 1.0+ | Variáveis de ambiente |
| **Docker** | 20.10+ | Containerização |

---

##  Pré-requisitos

- **Python 3.11** ou superior
- **Docker** (opcional, para containerização)
- **Oracle Instant Client** (para conexão com Oracle)
- **Acesso ao Active Directory** (para autenticação)
- **Acesso ao Oracle Database** (para dados)

---
```text
📁 Chamados_Dirtec/
├── 📄 app.py                      # Dashboard principal
├── 📄 auth_manager.py             # Gerenciamento de usuários e autenticação
├── 📄 bmcview_styles.py           # Estilos CSS do dashboard
├── 📄 error_messages.py           # Mensagens de erro padronizadas
├── 📄 requirements.txt            # Dependências do projeto
├── 📄 Dockerfile                  # Configuração da imagem Docker
├── 📄 docker-compose.yml          # Orquestração Docker
├── 📄 .env.example                # Exemplo de variáveis de ambiente
├── 📄 .gitignore                  # Arquivos ignorados no Git
├── 📁 pages/
│   ├── admin.py                   # Painel administrativo
│   └── dashboard.py               # Página de dashboard detalhada
├── 📁 services/
│   ├── ad_service.py              # Serviço de Active Directory
│   ├── oracle_service.py          # Serviço de Oracle Database
│   └── transform.py               # Transformação de dados
├── 📁 assets/                     # Imagens e logos
├── 📁 data/                       # Cache e arquivos de dados (não versionado)
└── 📁 logs/                       # Logs do sistema (não versionado)
```
