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

def login_gooddata(login, senha):
    url = "https://analytics.moveresoftware.com/gdc/account/login"
    payload = {
        "postUserLogin": {
            "login": login,
            "password": senha,
            "remember": 1
        }
    }
    headers = {
        "User-Agent": "MyApp/1.0 (Python)",
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    response.raise_for_status()
    print("Login bem-sucedido!")
    return response.cookies 

def is_user_admin(cookies):
    """Verifica se o usuário tem permissões de administrador"""
    try:
        profile_url = "https://analytics.moveresoftware.com/gdc/account/profile/current"
        headers = {
            "User-Agent": "MyApp/1.0 (Python)",
            "Accept": "application/json"
        }
        response = requests.get(profile_url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()
        profile_data = response.json()
        permissions = profile_data.get('accountSetting', {}).get('permissions', [])
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
    
    # Headers essenciais
    headers = {
        "User-Agent": "MyApp/1.0 (Python)",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-GDC-TASK-PRIORITY": "high"
    }
    
    # Payload mínimo e correto conforme documentação
    payload = {
        "partialMDImport": {
            "token": token,
            "overwriteNewer": bool(overwriteNewer),
            "updateLDMObjects": bool(updateLDMObjects),
            "importAttributeProperties": bool(importAttributeProperties)
        }
    }
    
    try:
        # Debug do payload antes do envio
        print(f"\n[DEBUG] Payload final para importação:")
        print(json.dumps(payload, indent=2))
        
        response = requests.post(
            url,
            headers=headers,
            cookies=cookies,
            json=payload,
            timeout=30
        )

        # Debug da resposta
        print(f"\n[DEBUG] Resposta da API (status {response.status_code}): {response.text}")

        # Tratamento de respostas
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                return {"status": "success", "message": "Importação realizada mas resposta inválida"}
        
        if response.status_code == 400:
            error_msg = response.json().get("error", {}).get("message", "Erro na requisição")
            if "STRUCTURE INVALID" in error_msg:
                raise Exception("Estrutura do payload inválida - remova parâmetros redundantes")
            raise Exception(f"Erro na requisição: {error_msg}")
        
        response.raise_for_status()

    except Exception as e:
        error_msg = f"Erro na importação: {str(e)}"
        if hasattr(e, 'response') and e.response:
            error_msg += f"\nStatus: {e.response.status_code}\nResposta: {e.response.text[:500]}"
        raise Exception(error_msg)

def extract_json_from_html(html_text):
    try:
        match = re.search(r"<pre[^>]*>(.*?)</pre>", html_text, re.DOTALL)
        if match:
            json_str = match.group(1)
            json_str = re.sub(r'<[^>]+>', '', json_str)
            json_str = re.sub(r'&#x22;|&quot;', '"', json_str)
            json_str = re.sub(r'&#39;|&apos;', "'", json_str)
            return json.loads(json_str)
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

def export_and_import(workspace_origem, workspace_destino, report_url, cookies, export_opts, import_opts):
    try:
        print("[1/3] Exportando metadados...")
        token = export_partial_metadata(
            workspace_origem,
            report_url,
            cookies,
            **export_opts
        )
        print("[2/3] Importando (timeout 5s)...")
        result = import_partial_metadata(
            workspace_destino,
            token,
            cookies,
            **import_opts
        )
        return result
    except Exception as e:
        raise Exception(f"Falha no fluxo integrado: {str(e)}")