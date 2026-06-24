# auth_manager.py
import os
import json
import pickle
import hashlib
import secrets
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

class AuthManager:
    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.users_file = self.data_dir / "users.json"
        self.pending_file = self.data_dir / "pending_users.json"
        self.notifications_file = self.data_dir / "notifications.json"
        self._init_files()
        self._init_default_admin()

    def _init_files(self):
        if not self.users_file.exists():
            self._save_users({})
        if not self.pending_file.exists():
            self._save_pending_users({})
        if not self.notifications_file.exists():
            self._save_notifications([])

    def _init_default_admin(self):
        admin_user = self.get_admin_user()
        users = self.listar_usuarios()
        
        if admin_user not in users:
            users[admin_user] = {
                "username": admin_user,
                "nome": "Administrador",
                "email": "",
                "tipo": "admin",
                "ativo": True,
                "autorizado": True,
                "categoria_ad": "Servidor",
                "filas_autorizadas": ["*"],
                "criado_em": datetime.now().isoformat()
            }
            self._save_users(users)

    def _save_users(self, users):
        with open(self.users_file, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

    def _load_users(self):
        if self.users_file.exists():
            with open(self.users_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_pending_users(self, pending):
        with open(self.pending_file, "w", encoding="utf-8") as f:
            json.dump(pending, f, ensure_ascii=False, indent=2)

    def listar_usuarios_pendentes(self):
        if self.pending_file.exists():
            with open(self.pending_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_notifications(self, notifications):
        with open(self.notifications_file, "w", encoding="utf-8") as f:
            json.dump(notifications, f, ensure_ascii=False, indent=2)

    def _load_notifications(self):
        if self.notifications_file.exists():
            with open(self.notifications_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def login(self, username: str, password: str) -> Tuple[bool, str]:
        try:
            from services.ad_service import ADService
            ad = ADService()
            
            success, message = ad.authenticate(username, password)
            if not success:
                return False, message
            
            users = self.listar_usuarios()
            username = username.strip().lower()
            
            if username not in users:
                return False, "Usuario nao autorizado. Contate o administrador para liberar o acesso."
            
            user_data = users[username]
            if not user_data.get("ativo", True):
                return False, "Usuario inativo. Contate o administrador."
            
            if not user_data.get("autorizado", False):
                return False, "Usuario nao autorizado. Contate o administrador."
            
            users[username]["ultimo_acesso"] = datetime.now().isoformat()
            self._save_users(users)
            
            return True, "Login realizado com sucesso!"
            
        except Exception as e:
            return False, f"Erro na autenticacao: {str(e)}"

    def adicionar_usuario_manual(self, username: str, nome: str = None, email: str = None, 
                                  filas: list = None, categoria: str = "Servidor") -> Tuple[bool, str]:
        """
        Adiciona um usuario manualmente (apenas administrador).
        
        Args:
            username: Nome do usuario
            nome: Nome completo (opcional - busca no AD se nao informado)
            email: Email (opcional - busca no AD se nao informado)
            filas: Lista de filas autorizadas
            categoria: Categoria do usuario
        """
        try:
            from services.ad_service import ADService
            ad = ADService()
            
            username = username.strip().lower()
            users = self.listar_usuarios()
            
            if username in users:
                return False, "Usuario ja existe no sistema"
            
            # Busca informacoes no AD se nao foram fornecidas
            user_info = ad.get_user_info(username)
            
            if not nome and user_info:
                nome = user_info.get('nome_completo', username)
            elif not nome:
                nome = username
            
            if not email and user_info:
                email = user_info.get('email', '')
            elif not email:
                email = ''
            
            if not categoria and user_info:
                categoria = user_info.get('categoria_usuario', 'Servidor')
            
            users[username] = {
                "username": username,
                "nome": nome,
                "email": email,
                "tipo": "usuario",
                "ativo": True,
                "autorizado": True,
                "categoria_ad": categoria,
                "canonical_name": user_info.get('canonical_name', '') if user_info else '',
                "status_ad": user_info.get('status_ad', 'ATIVO') if user_info else 'ATIVO',
                "ativo_no_ad": user_info.get('ativo_no_ad', True) if user_info else True,
                "filas_autorizadas": filas or [],
                "criado_em": datetime.now().isoformat(),
                "criado_por": "admin"
            }
            
            self._save_users(users)
            self.add_notification("success", f"Usuario adicionado manualmente: {username} ({nome})")
            return True, f"Usuario {username} adicionado com sucesso"
            
        except Exception as e:
            return False, f"Erro ao adicionar usuario: {str(e)}"

    def autorizar_usuario(self, username: str) -> Tuple[bool, str]:
        """
        Metodo mantido para compatibilidade, mas nao usado mais.
        Usuarios so sao adicionados manualmente.
        """
        return False, "Metodo descontinuado. Use adicionar_usuario_manual para adicionar usuarios."

    def listar_usuarios(self) -> Dict:
        return self._load_users()

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        users = self.listar_usuarios()
        return users.get(username.strip().lower())

    def is_admin(self, username: str) -> bool:
        user = self.get_user_by_username(username)
        if not user:
            return False
        return user.get("tipo") == "admin"

    def get_admin_user(self) -> str:
        admin = os.getenv("ADMIN_USER", "gabriel.alves")
        return admin.strip().lower()

    def get_user_filas(self, username: str) -> list:
        user = self.get_user_by_username(username)
        if not user:
            return []
        if self.is_admin(username):
            return ["*"]
        return user.get("filas_autorizadas", [])

    def update_user_filas(self, username: str, filas: list) -> Tuple[bool, str]:
        users = self.listar_usuarios()
        username = username.strip().lower()
        
        if username not in users:
            return False, "Usuario nao encontrado"
        
        if self.is_admin(username):
            return False, "Administradores tem acesso a todas as filas"
        
        users[username]["filas_autorizadas"] = filas
        self._save_users(users)
        return True, f"Filas atualizadas para {username}"

    def inativar_usuario(self, username: str) -> Tuple[bool, str]:
        users = self.listar_usuarios()
        username = username.strip().lower()
        
        if username not in users:
            return False, "Usuario nao encontrado"
        
        if self.is_admin(username):
            return False, "Nao e possivel inativar o administrador"
        
        users[username]["ativo"] = False
        users[username]["inativado_em"] = datetime.now().isoformat()
        self._save_users(users)
        
        self.add_notification("warning", f"Usuario inativado: {username}")
        return True, "Usuario inativado com sucesso"

    def ativar_usuario(self, username: str) -> Tuple[bool, str]:
        users = self.listar_usuarios()
        username = username.strip().lower()
        
        if username not in users:
            return False, "Usuario nao encontrado"
        
        users[username]["ativo"] = True
        users[username].pop("inativado_em", None)
        self._save_users(users)
        
        self.add_notification("success", f"Usuario reativado: {username}")
        return True, "Usuario reativado com sucesso"

    def excluir_usuario(self, username: str) -> Tuple[bool, str]:
        users = self.listar_usuarios()
        username = username.strip().lower()
        
        if username not in users:
            return False, "Usuario nao encontrado"
        
        if self.is_admin(username):
            return False, "Nao e possivel excluir o administrador"
        
        del users[username]
        self._save_users(users)
        
        self.add_notification("info", f"Usuario excluido: {username}")
        return True, "Usuario excluido com sucesso"

    def alterar_tipo_usuario(self, username: str, tipo: str) -> Tuple[bool, str]:
        users = self.listar_usuarios()
        username = username.strip().lower()
        
        if username not in users:
            return False, "Usuario nao encontrado"
        
        if tipo not in ["usuario", "admin"]:
            return False, "Tipo invalido. Use 'usuario' ou 'admin'"
        
        users[username]["tipo"] = tipo
        self._save_users(users)
        
        self.add_notification("info", f"Tipo do usuario alterado: {username} -> {tipo}")
        return True, f"Tipo alterado para {tipo}"

    def add_notification(self, tipo: str, mensagem: str):
        notifications = self._load_notifications()
        notifications.append({
            "id": str(secrets.token_hex(8)),
            "type": tipo,
            "message": mensagem,
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "read": False
        })
        self._save_notifications(notifications)

    def get_notifications(self, unread_only: bool = False):
        notifications = self._load_notifications()
        if unread_only:
            return [n for n in notifications if not n.get("read", False)]
        return notifications

    def get_unread_count(self):
        return len(self.get_notifications(unread_only=True))

    def mark_notification_read(self, notification_id: str):
        notifications = self._load_notifications()
        for n in notifications:
            if n.get("id") == notification_id:
                n["read"] = True
                break
        self._save_notifications(notifications)

    def mark_all_notifications_read(self):
        notifications = self._load_notifications()
        for n in notifications:
            n["read"] = True
        self._save_notifications(notifications)

    def sync_user_category_from_ad(self, username: str) -> Tuple[bool, str]:
        """
        Sincroniza a categoria do usuario com o AD.
        """
        try:
            from services.ad_service import ADService
            ad = ADService()
            user_info = ad.get_user_info(username)
            
            if not user_info:
                return False, "Usuario nao encontrado no AD"
            
            users = self.listar_usuarios()
            username = username.strip().lower()
            
            if username not in users:
                return False, "Usuario nao encontrado no sistema"
            
            users[username]['categoria_ad'] = user_info.get('categoria_usuario', 'Servidor')
            users[username]['canonical_name'] = user_info.get('canonical_name', '')
            users[username]['status_ad'] = user_info.get('status_ad', 'ATIVO')
            users[username]['ativo_no_ad'] = user_info.get('ativo_no_ad', True)
            
            self._save_users(users)
            return True, f"Categoria atualizada: {user_info.get('categoria_usuario', 'Servidor')}"
            
        except Exception as e:
            return False, f"Erro ao sincronizar: {str(e)}"

    def debug_user_difference(self, search_term: str) -> Dict:
        """
        Compara usuarios encontrados no AD versus sistema.
        """
        from services.ad_service import ADService
        ad = ADService()
        
        print("=" * 70)
        print("DEBUG: COMPARACAO DE USUARIOS AD vs SISTEMA")
        print("=" * 70)
        
        # Busca no AD
        df_ad = ad.search_users(search_term)
        print(f"\n[AD] Total de usuarios encontrados com o termo '{search_term}': {len(df_ad)}")
        
        # Busca no sistema
        users = self.listar_usuarios()
        users_filtered = {k: v for k, v in users.items() if search_term.lower() in k.lower()}
        print(f"[SISTEMA] Total de usuarios encontrados com o termo '{search_term}': {len(users_filtered)}")
        
        # Lista os usuarios do AD com detalhes
        print("\n" + "-" * 70)
        print("USUARIOS DO AD:")
        print("-" * 70)
        for idx, row in df_ad.iterrows():
            print(f"  {idx+1}. {row['username']} - {row['nome_completo']} ({row['categoria_usuario']}) - {row['status_ad']}")
        
        # Lista os usuarios do sistema
        print("\n" + "-" * 70)
        print("USUARIOS DO SISTEMA:")
        print("-" * 70)
        for idx, (username, data) in enumerate(users_filtered.items()):
            status = "ATIVO" if data.get('ativo', True) else "INATIVO"
            autorizado = "SIM" if data.get('autorizado', False) else "NAO"
            print(f"  {idx+1}. {username} - {data.get('nome', username)} (Status: {status}, Autorizado: {autorizado})")
        
        # Comparacao
        ad_usernames = set(df_ad['username'].tolist())
        system_usernames = set(users_filtered.keys())
        
        missing = ad_usernames - system_usernames
        extra = system_usernames - ad_usernames
        
        print("\n" + "=" * 70)
        print("RESULTADO DA COMPARACAO:")
        print("=" * 70)
        
        print(f"\nTotal no AD: {len(ad_usernames)}")
        print(f"Total no Sistema: {len(system_usernames)}")
        print(f"Diferenca: {len(ad_usernames) - len(system_usernames)}")
        
        if missing:
            print(f"\n[FALTANDO NO SISTEMA] Usuarios no AD que nao estao no sistema ({len(missing)}):")
            print("-" * 70)
            print("  (Para adicionar, use o painel admin ou o comando adicionar_usuario_manual)")
            for username in sorted(missing):
                user_data = df_ad[df_ad['username'] == username].iloc[0]
                print(f"  - {username}: {user_data['nome_completo']} ({user_data['categoria_usuario']}) - {user_data['status_ad']}")
        else:
            print("\n[TUDO OK] Todos os usuarios do AD estao no sistema")
        
        if extra:
            print(f"\n[EXTRA NO SISTEMA] Usuarios no sistema que nao estao no AD ({len(extra)}):")
            print("-" * 70)
            for username in sorted(extra):
                user_data = users_filtered.get(username, {})
                print(f"  - {username}: {user_data.get('nome', username)}")
        else:
            print("\n[TUDO OK] Nenhum usuario extra no sistema")
        
        print("\n" + "=" * 70)
        
        return {
            'total_ad': len(df_ad),
            'total_system': len(users_filtered),
            'missing': list(missing),
            'extra': list(extra),
            'df_ad': df_ad,
            'users_filtered': users_filtered
        }

    def sync_ad_status_for_user(self, username: str) -> bool:
        try:
            from services.ad_service import ADService
            ad = ADService()
            user_info = ad.get_user_info(username)
            
            if user_info:
                users = self.listar_usuarios()
                if username in users:
                    users[username]["ativo_no_ad"] = user_info.get("ativo_no_ad", True)
                    users[username]["status_ad"] = user_info.get("status_ad", "ATIVO")
                    users[username]["categoria_ad"] = user_info.get("categoria_usuario", "Servidor")
                    users[username]["canonical_name"] = user_info.get("canonical_name", "")
                    self._save_users(users)
                    return True
            return False
        except Exception:
            return False

    def check_ad_status(self, username: str) -> Dict:
        try:
            from services.ad_service import ADService
            ad = ADService()
            return ad.get_user_info(username) or {"ativo_no_ad": False, "status_ad": "INDISPONIVEL"}
        except Exception:
            return {"ativo_no_ad": False, "status_ad": "ERRO"}
    
    def buscar_usuarios_ad_para_adicionar(self, search_term: str) -> pd.DataFrame:
        """
        Busca usuarios no AD para o administrador adicionar.
        """
        from services.ad_service import ADService
        ad = ADService()
        
        df = ad.search_users(search_term)
        
        if df.empty:
            return df
        
        users = self.listar_usuarios()
        pending = self.listar_usuarios_pendentes()
        
        # Marca quais usuarios ja estao no sistema
        df['no_sistema'] = df['username'].apply(lambda x: x in users)
        df['pendente'] = df['username'].apply(lambda x: x in pending)
        
        return df