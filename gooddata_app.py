import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import threading
from apigooddata import (
    test_dns_resolution, login_gooddata, get_workspace_name,
    export_partial_metadata, import_partial_metadata,
    extract_report_uri, wait_for_import_status_ok
)

# Configuração do tema
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("dark-blue")

class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, on_login_success):
        super().__init__(master)
        self.on_login_success = on_login_success
        self._is_destroyed = False  # Flag para controlar se o frame foi destruído
        self.create_widgets()


    def create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3), weight=1)
        
        self.label = ctk.CTkLabel(self, text="Autentição GoodData", font=ctk.CTkFont(size=20, weight="bold"))
        self.label.grid(row=0, column=0, pady=(40, 20))

         # Frame dos campos de login
        self.login_container = ctk.CTkFrame(self, fg_color="transparent")
        self.login_container.grid(row=1, column=0,pady=(5, 20) )
        
        # Label + Campo de Login
        self.login_label = ctk.CTkLabel(
            self.login_container,
            text="Email:",
            font=ctk.CTkFont(size=12)
        )
        self.login_label.grid(row=0, column=0, sticky="w", padx=10, pady=(0, 5)) 
        self.login_entry = ctk.CTkEntry(
            self.login_container,
            placeholder_text="seu@email.com",
            width=300
        )
        self.login_entry.grid(row=1, column=0, padx=10, pady=(0, 15))
        #self.login_entry.insert(0, "")
        
       
        # Label + Campo de Senha
        self.password_label = ctk.CTkLabel(
            self.login_container,
            text="Senha:",
            font=ctk.CTkFont(size=12)
        )
        self.password_label.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 5))
        
        self.password_entry = ctk.CTkEntry(
            self.login_container,
            placeholder_text="••••••••",
            show="•",
            width=300
        )
        self.password_entry.grid(row=3, column=0, padx=10, pady=(0, 20))
        
        #self.password_entry.insert(0, "")
        
        self.connect_btn = ctk.CTkButton(
            self.login_container, 
            text="Acessar", 
            command=self.try_login,
             width=200,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.connect_btn.grid(row=4, column=0, pady=(10, 0))

    def try_login(self):
        login = self.login_entry.get()
        senha = self.password_entry.get()
        
        if not login or not senha:
            messagebox.showerror("Erro", "Por favor, preencha login e senha")
            return
            
        self.connect_btn.configure(state=tk.DISABLED, text="Conectando...")
        
        def login_thread():
            try:
                if not test_dns_resolution("analytics.moveresoftware.com"):
                    self.safe_update(lambda: messagebox.showerror("Erro", "Falha ao resolver o nome do host"))
                    return
                
                cookies = login_gooddata(login, senha)
                self.safe_update(lambda: self.on_login_success(cookies))
            except Exception as e:
                self.safe_update(lambda: messagebox.showerror("Erro de Login", str(e)))
            finally:
                self.safe_update(lambda: self.reset_login_button())
                
        threading.Thread(target=login_thread, daemon=True).start()

    def reset_login_button(self):
        if not self._is_destroyed and self.connect_btn.winfo_exists():
            self.connect_btn.configure(state=tk.NORMAL, text="Conectar")

    def safe_update(self, callback):
        """Executa uma atualização na thread principal de forma segura"""
        if not self._is_destroyed and self.winfo_exists():
            self.after(0, callback)

    def destroy(self):
        self._is_destroyed = True
        super().destroy()

class ExportImportFrame(ctk.CTkFrame):
    def __init__(self, master, cookies):
        super().__init__(master)
        self.cookies = cookies
        self.running = False
        self.create_widgets()

    def create_widgets(self):
        # Configurar layout
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6, 7, 8), weight=1)
        
        # Título
        self.title_label = ctk.CTkLabel(
            self, 
            text="Migração de Metadados GoodData", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.title_label.grid(row=0, column=0, columnspan=2, pady=(10, 20))
        
            # Frame container para agrupar os workspaces
        self.workspace_container = ctk.CTkFrame(self, fg_color="transparent")
        self.workspace_container.grid(row=1, column=0, columnspan=2, pady=10, sticky="nsew")

        # Configuração das colunas (50% para cada workspace)
        self.workspace_container.grid_columnconfigure(0, weight=1)
        self.workspace_container.grid_columnconfigure(1, weight=1)

        # Workspace Origem (agora dentro do container)
        self.label_origem = ctk.CTkLabel(
            self.workspace_container, 
            text="Código Projeto Origem:",
            font=ctk.CTkFont(weight="bold")
        )
        self.label_origem.grid(row=0, column=0, padx=20, pady=(0, 5), sticky="w")

        self.origem_frame = ctk.CTkFrame(self.workspace_container, fg_color="transparent")
        self.origem_frame.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.origem_frame.grid_columnconfigure(0, weight=3)
        self.origem_frame.grid_columnconfigure(1, weight=1)

        self.workspace_id_entry = ctk.CTkEntry(self.origem_frame)
        self.workspace_id_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.workspace_id_entry.bind("<FocusOut>", self.update_nome_origem)

        self.workspace_nome_origem = ctk.CTkLabel(
            self.origem_frame, 
            text="",
            width=120,
            anchor="w"
        )
        self.workspace_nome_origem.grid(row=0, column=1, sticky="ew")

        # Workspace Destino (agora dentro do container)
        self.label_destino = ctk.CTkLabel(
            self.workspace_container,
            text="Código Projeto Destino:", 
            font=ctk.CTkFont(weight="bold")
        )
        self.label_destino.grid(row=0, column=1, padx=20, pady=(0, 5), sticky="w")

        self.destino_frame = ctk.CTkFrame(self.workspace_container, fg_color="transparent")
        self.destino_frame.grid(row=1, column=1, padx=20, pady=(0, 10), sticky="ew")
        self.destino_frame.grid_columnconfigure(0, weight=3)
        self.destino_frame.grid_columnconfigure(1, weight=1)

        self.workspace_id_destino_entry = ctk.CTkEntry(self.destino_frame)
        self.workspace_id_destino_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.workspace_id_destino_entry.bind("<FocusOut>", self.update_nome_destino)

        self.workspace_nome_destino = ctk.CTkLabel(
            self.destino_frame,
            text="",
            width=120,
            anchor="w"
        )
        self.workspace_nome_destino.grid(row=0, column=1, sticky="ew")
        
        # Link do objeto
        self.label_report = ctk.CTkLabel(self, text="Link do relatório para Exportar:")
        self.label_report.grid(row=3, column=0, columnspan=2, padx=20, pady=(10, 5), sticky="w")
        
        self.report_link_entry = ctk.CTkEntry(self, placeholder_text="Cole aqui o link")
        self.report_link_entry.grid(row=4, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="ew")
         
        # Opções de Exportação
        self.export_options_label = ctk.CTkLabel(self, text="Opções de Exportação:")
        self.export_options_label.grid(row=5, column=0, columnspan=2, padx=20, pady=(0, 5), sticky="w")
        
        # Frame para os checkboxes (isso ajuda no alinhamento)
        self.export_checkbox_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.export_checkbox_frame.grid(row=6, column=0, columnspan=2, pady=(0, 10), sticky="nsew")

        # Centraliza os elementos dentro do frame
        self.export_checkbox_frame.grid_columnconfigure(0, weight=1)
        self.export_checkbox_frame.grid_columnconfigure(1, weight=1)

        self.export_attr_var = tk.IntVar(value=0)
        self.export_attr_chk = ctk.CTkCheckBox(
            self.export_checkbox_frame,  # Note que agora está no frame
            text="Exportar propriedades de atributo",
            variable=self.export_attr_var
        )
        self.export_attr_chk.grid(row=0, column=0, padx=(20, 10), pady=5, sticky="ew")

        self.export_cross_var = tk.IntVar(value=0)
        self.export_cross_chk = ctk.CTkCheckBox(
            self.export_checkbox_frame,  # Note que agora está no frame
            text="Exportar cross data center",
            variable=self.export_cross_var
        )
        self.export_cross_chk.grid(row=0, column=1, padx=(10, 20), pady=5, sticky="ew")
        
        # Opções de Importação
        self.import_options_label = ctk.CTkLabel(self, text="Opções de Importação:")
        self.import_options_label.grid(row=7, column=0, columnspan=2, padx=20, pady=(10, 5), sticky="w")
        
        # Frame para agrupar os checkboxes de importação
        self.import_checkbox_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.import_checkbox_frame.grid(row=8, column=0, columnspan=2, pady=(0, 10), sticky="ew")

        # Configuração das colunas do frame para distribuição igual
        self.import_checkbox_frame.grid_columnconfigure(0, weight=1)
        self.import_checkbox_frame.grid_columnconfigure(1, weight=1)
        self.import_checkbox_frame.grid_columnconfigure(2, weight=1)

        # Checkbox 1 - Sobrescrever objetos
        self.overwrite_var = tk.IntVar(value=0)
        self.overwrite_chk = ctk.CTkCheckBox(
            self.import_checkbox_frame,  # Agora está dentro do frame
            text="Sobrescrever objetos",
            variable=self.overwrite_var
        )
        self.overwrite_chk.grid(row=0, column=0, padx=(20, 10), pady=5, sticky="ew")

        # Checkbox 2 - Atualizar LDM
        self.ldm_var = tk.IntVar(value=0)
        self.ldm_chk = ctk.CTkCheckBox(
            self.import_checkbox_frame,
            text="Atualizar LDM",
            variable=self.ldm_var
        )
        self.ldm_chk.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        # Checkbox 3 - Propriedades de atributo
        self.attr_prop_var = tk.IntVar(value=0)
        self.attr_prop_chk = ctk.CTkCheckBox(
            self.import_checkbox_frame,
            text="Importar propriedades",
            variable=self.attr_prop_var
        )
        self.attr_prop_chk.grid(row=0, column=2, padx=10, pady=5, sticky="w")
        
        # Botão de Execução
        self.start_btn = ctk.CTkButton(
            self, 
            text="Iniciar Processo",
            command=self.start_process,
            fg_color="#239B56",
            width=300
        )
        self.start_btn.grid(row=10, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")
        # Botão para iniciar a importação
 
        
        # Área de Log
        self.log_label = ctk.CTkLabel(self, text="Log de Operações:")
        self.log_label.grid(row=11, column=0, columnspan=2, padx=20, pady=(0, 5), sticky="w")
        
        self.log_text = tk.Text(
            self, 
            wrap=tk.WORD, 
            height=14,
            font=('Consolas', 10),
            bg='#f5f5f5',
            fg='#333333'
        )
        self.log_text.grid(row=12, column=0, columnspan=2, padx=20, pady=(0, 20), sticky="nsew")
        
        # Adicionar scrollbar
        scrollbar = ctk.CTkScrollbar(self, command=self.log_text.yview)
        scrollbar.grid(row=12, column=2, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def update_nome_origem(self, event=None):
        workspace_id = self.workspace_id_entry.get().strip()
        if workspace_id:
            try:
                nome = get_workspace_name(workspace_id, self.cookies)
                self.workspace_nome_origem.configure(text=nome)
            except Exception as e:
                self.workspace_nome_origem.configure(text="Erro ao buscar")
                self.log(f"Erro ao buscar workspace origem: {str(e)}")

    def update_nome_destino(self, event=None):
        workspace_id = self.workspace_id_destino_entry.get().strip()
        if workspace_id:
            try:
                nome = get_workspace_name(workspace_id, self.cookies)
                self.workspace_nome_destino.configure(text=nome)
            except Exception as e:
                self.workspace_nome_destino.configure(text="Erro ao buscar")
                self.log(f"Erro ao buscar workspace destino: {str(e)}")

    def log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.update()

    def start_process(self):
        if self.running:
            return
            
        workspace_id = self.workspace_id_entry.get().strip()
        workspace_id_destino = self.workspace_id_destino_entry.get().strip()
        report_link = self.report_link_entry.get().strip()
        
        if not workspace_id or not workspace_id_destino or not report_link:
            messagebox.showerror("Erro", "Preencha todos os campos obrigatórios")
            return
            
        self.running = True
        self.start_btn.configure(state=tk.DISABLED, text="Executando...")
        
        threading.Thread(target=self._process, args=(
            workspace_id,
            workspace_id_destino,
            report_link,
            self.export_attr_var.get(),
            self.export_cross_var.get(),
            self.overwrite_var.get(),
            self.ldm_var.get(),
            self.attr_prop_var.get()
        ), daemon=True).start()

    def _process(self, workspace_id, workspace_id_destino, report_link, 
                export_attr, export_cross, overwrite, ldm, attr_prop):
        try:
            self.log("\n=== INICIANDO PROCESSO ===")
            
            # Exportação
            self.log("\n[EXPORTAÇÃO] Extraindo URI do relatório...")
            report_url = extract_report_uri(report_link)
            self.log(f"URI extraído: {report_url}")
            
            self.log("\n[EXPORTAÇÃO] Exportando metadados...")
            token = export_partial_metadata(
                workspace_id, 
                report_url, 
                self.cookies,
                exportAttributeProperties=export_attr,
                crossDataCenterExport=export_cross
            )
            self.log(f"Token de exportação obtido: {token}")
            
            # Importação
            self.log("\n[IMPORTAÇÃO] Verificando workspace destino...")
            nome_destino = get_workspace_name(workspace_id_destino, self.cookies)
            self.log(f"Workspace destino: {nome_destino}")
            
            self.log("\n[IMPORTAÇÃO] Importando metadados...")
            status_uri = import_partial_metadata(
                workspace_id_destino,
                token,
                self.cookies,
                overwrite,
                ldm,
                attr_prop
            )
            self.log(f"URI de status da importação: {status_uri}")
            
            # Monitoramento
            self.log("\n[MONITORAMENTO] Aguardando conclusão...")
            status = wait_for_import_status_ok(workspace_id_destino, status_uri, self.cookies)
            self.log(f"\nStatus final: {status}")
            
            if status == "OK":
                self.log("\n✅ Processo concluído com sucesso!")
            else:
                self.log("\n⚠️ Processo concluído, mas o status não foi OK.")
                
        except Exception as e:
            self.log(f"\n❌ ERRO: {str(e)}")
        finally:
            self.after(0, lambda: self.start_btn.configure(state=tk.NORMAL, text="Iniciar Exportação/Importação"))
            self.running = False

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Migração de Metadados GoodData")	
        self.geometry("900x700")
        self.maxsize(width=800, height=700)
        self.resizable(width=True, height=False)
        
        self.cookies = None
        self.current_frame = None
        
        self.show_login()

    def show_login(self):
        if hasattr(self, 'current_frame') and self.current_frame:
            self.current_frame.destroy()
            
        self.current_frame = LoginFrame(self, self.on_login_success)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

    def on_login_success(self, cookies):
        self.cookies = cookies
        
        if hasattr(self, 'current_frame') and self.current_frame:
            self.current_frame.destroy()
            
        self.current_frame = ExportImportFrame(self, self.cookies)
        self.current_frame.pack(fill=tk.BOTH, expand=True)

if __name__ == "__main__":
    app = App()
    app.mainloop()