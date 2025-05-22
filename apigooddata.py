import requests
from requests.exceptions import ConnectionError, RequestException
import socket
import re
import json
import time

def test_dns_resolution(hostname):
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        return False

def login_gooddata(login, password):
    url = "https://analytics.moveresoftware.com/gdc/account/login"
    
    # Primeiro verifica a resolução DNS
    if not test_dns_resolution("analytics.moveresoftware.com"):
        raise Exception("Falha ao resolver o nome do host. Verifique sua conexão com a internet.")
    
    payload = {
        "postUserLogin": {
            "login": login,
            "password": password,
            "remember": 1
        }
    }
    
    headers = {
        "User-Agent": "MyApp/1.0 (Python)",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.cookies
    except ConnectionError as e:
        raise Exception(f"Erro de conexão: {str(e)}")
    except RequestException as e:
        raise Exception(f"Erro na requisição: {str(e)}")

def is_user_admin(cookies):
    """Verifica se o usuário tem permissões de administrador"""
    try:
        # Endpoint que retorna informações do usuário logado
        profile_url = "https://analytics.moveresoftware.com/gdc/account/profile/current"
        headers = {
            "User-Agent": "MyApp/1.0 (Python)",
            "Accept": "application/json"
        }
        
        response = requests.get(profile_url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()
        
        profile_data = response.json()
        permissions = profile_data.get('accountSetting', {}).get('permissions', [])
        
        # Verifica se tem permissão de admin (ajuste conforme a API do GoodData)
        return 'admin' in permissions or 'manage' in permissions
        
    except Exception as e:
        print(f"Erro ao verificar permissões: {str(e)}")
        return False

def get_workspace_name(workspace_id, cookies):
    url = f"https://analytics.moveresoftware.com/gdc/projects/{workspace_id}"
    headers = {
        "User-Agent": "MyApp/1.0 (Python)",
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data['project']['meta']['title']
    except RequestException as e:
        raise Exception(f"Erro ao buscar workspace: {str(e)}")

def export_partial_metadata(workspace_id, report_url, cookies, exportAttributeProperties=0, crossDataCenterExport=0):
    url = f"https://analytics.moveresoftware.com/gdc/md/{workspace_id}/maintenance/partialmdexport"
    headers = {
        "User-Agent": "MyApp/1.0 (Python)",
        "Content-Type": "application/json"
    }
    payload = {
        "partialMDExport": {
            "uris": [report_url],
            "exportAttributeProperties": int(exportAttributeProperties),
            "crossDataCenterExport": int(crossDataCenterExport)
        }
    }
    try:
        response = requests.post(url, headers=headers, cookies=cookies, json=payload, timeout=15)
        response.raise_for_status()
        
        # Extrai o JSON da resposta HTML
        match = re.search(r"<pre>(.*?)</pre>", response.text, re.DOTALL)
        if not match:
            raise Exception("Não foi possível extrair o JSON da resposta.")
            
        json_str = match.group(1)
        json_str = re.sub(r'<.*?>', '', json_str)
        json_str = json_str.replace('&#x22;', '"')
        
        data = json.loads(json_str)
        token = data.get('partialMDArtifact', {}).get('token')
        if not token:
            raise Exception("Token de exportação não encontrado.")
            
        return token
    except RequestException as e:
        if e.response is not None:
            print("Resposta da API:", e.response.text)
        raise Exception(f"Erro ao exportar metadados: {str(e)}")

def import_partial_metadata(workspace_id_destino, token, cookies, overwriteNewer=0, updateLDMObjects=0, importAttributeProperties=0):
    url = f"https://analytics.moveresoftware.com/gdc/md/{workspace_id_destino}/maintenance/partialmdimport"
    headers = {
        "User-Agent": "MyApp/1.0 (Python)",
        "Content-Type": "application/json",
        "Accept": "application/json, text/html"  # Aceita ambos os formatos
    }
    payload = {
        "partialMDImport": {
            "token": token,
            "overwriteNewer": int(overwriteNewer),
            "updateLDMObjects": int(updateLDMObjects),
            "importAttributeProperties": int(importAttributeProperties)
        }
    }

    try:
        # 1. Verifica se o workspace existe
        test_url = f"https://analytics.moveresoftware.com/gdc/projects/{workspace_id_destino}"
        test_response = requests.get(test_url, cookies=cookies, timeout=10)
        if test_response.status_code == 404:
            raise Exception(f"Workspace {workspace_id_destino} não encontrado")

        # 2. Envia a requisição de importação
        response = requests.post(url, headers=headers, cookies=cookies, json=payload, timeout=30)
        
        # 3. Tratamento especial para quando a API retorna 404
        if response.status_code == 404:
            print("AVISO: Endpoint retornou 404, mas a importação pode ter sido iniciada")
            return f"/gdc/md/{workspace_id_destino}/tasks/unknown_status"

        # 4. Processa a resposta (JSON ou HTML)
        try:
            data = response.json()  # Tenta como JSON puro primeiro
        except ValueError:
            data = extract_json_from_html(response.text)  # Fallback para HTML

        # 5. Extrai a URI de status
        uri_status = data.get('uri')
        if not uri_status:
            print("AVISO: URI de status não encontrada, mas a importação pode ter sido iniciada")
            return f"/gdc/md/{workspace_id_destino}/tasks/unknown_status"

        return uri_status

    except Exception as e:
        error_msg = f"Erro durante a importação: {str(e)}"
        if 'response' in locals():
            error_msg += f"\nStatus Code: {response.status_code}"
            error_msg += f"\nResposta: {response.text[:500]}"
        raise Exception(error_msg)

def extract_json_from_html(html_text):
    """Extrai JSON de respostas HTML de forma resiliente"""
    try:
        # Tenta encontrar o JSON dentro de <pre>
        match = re.search(r"<pre[^>]*>(.*?)</pre>", html_text, re.DOTALL)
        if match:
            json_str = match.group(1)
            # Limpeza do conteúdo JSON
            json_str = re.sub(r'<[^>]+>', '', json_str)  # Remove tags
            json_str = re.sub(r'&#x22;|&quot;', '"', json_str)  # Aspas
            json_str = re.sub(r'&#39;|&apos;', "'", json_str)  # Apóstrofos
            return json.loads(json_str)
        
        # Se não encontrou <pre>, tenta extrair JSON direto do HTML
        json_match = re.search(r'({.*})', html_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
            
        raise Exception("Nenhum JSON encontrado no HTML")
    except Exception as e:
        raise Exception(f"Falha ao extrair JSON do HTML: {str(e)}")
def get_import_status(workspace_id, status_uri, cookies):
    url = f"https://analytics.moveresoftware.com{status_uri}"
    headers = {
        "User-Agent": "MyApp/1.0 (Python)",
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get('wTaskStatus', {}).get('status')
    except RequestException as e:
        raise Exception(f"Erro ao verificar status: {str(e)}")

def extract_report_uri(report_link):
    match = re.search(r"(/gdc/md/[\w\d]+/obj/\d+)", report_link)
    if match:
        return match.group(1)
    raise ValueError("Não foi possível extrair o caminho do relatório.")

def wait_for_import_status_ok(workspace_id, status_uri, cookies, interval=5, max_attempts=60):
    attempts = 0
    while attempts < max_attempts:
        try:
            status = get_import_status(workspace_id, status_uri, cookies)
            if status != "RUNNING":
                return status
            time.sleep(interval)
            attempts += 1
        except Exception as e:
            print(f"Erro ao verificar status: {str(e)}")
            time.sleep(interval)
            attempts += 1
            
            
    raise Exception("Tempo máximo de espera atingido.")