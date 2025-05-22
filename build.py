import PyInstaller.__main__
import shutil
import os

# Configurações
app_name = "ReportTransfer"
main_script = "gooddata_app.py"
icon_path = "icone.ico"  # Crie ou converta um ícone para .ico
additional_files = [('config.ini', '.'), ('assets', 'assets')]

# Limpa builds anteriores
if os.path.exists('dist'):
    shutil.rmtree('dist')
if os.path.exists('build'):
    shutil.rmtree('build')

# Configura os argumentos do PyInstaller
args = [
    '--name=%s' % app_name,
    '--onefile',
    '--windowed',  # Não mostra console
    '--icon=%s' % icon_path,
    '--add-data=%s' % ';'.join([f'{src}{os.pathsep}{dst}' for src, dst in additional_files]),
    '--noconfirm',
    '--clean',
    '--log-level=WARN',
    main_script
]

# Executa o PyInstaller
PyInstaller.__main__.run(args)

print("\nBuild completo! O executável está em: dist/" + app_name + ".exe")