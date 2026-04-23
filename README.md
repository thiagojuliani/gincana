# 🧥 GincanaFAC — Sistema de Arrecadação de Agasalhos

Sistema web com backend Flask + banco de dados SQLite.

## Estrutura

```
gincana/
├── app.py              # Backend Flask (API REST)
├── requirements.txt    # Dependências Python
├── Procfile            # Para Railway/Render
├── gincana.db          # Banco SQLite (criado automaticamente)
└── static/
    └── index.html      # Frontend completo
```

## Rodando localmente

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Rodar o servidor
python app.py

# 3. Abrir no navegador
http://localhost:5000
```

## Hospedagem na nuvem (Railway — recomendado, gratuito)

1. Crie uma conta em https://railway.app
2. Crie um novo projeto → "Deploy from GitHub"
3. Suba esta pasta para um repositório GitHub
4. Railway detecta o `Procfile` automaticamente
5. Configure a variável de ambiente:
   - `SECRET_KEY` → uma string aleatória longa (ex: `openssl rand -hex 32`)
6. Deploy! O banco SQLite persiste no volume do Railway.

> **Alternativa:** Render.com funciona da mesma forma com o `Procfile`.

## Hospedagem em VPS (Ubuntu)

```bash
# Instalar dependências
sudo apt install python3 python3-pip nginx
pip3 install -r requirements.txt gunicorn

# Criar serviço systemd
sudo nano /etc/systemd/system/gincana.service
```

Conteúdo do serviço:
```ini
[Unit]
Description=GincanaFAC
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/gincana
Environment="SECRET_KEY=TROQUE_AQUI_POR_CHAVE_ALEATORIA"
Environment="DB_PATH=/var/www/gincana/gincana.db"
ExecStart=/usr/local/bin/gunicorn app:app --bind 127.0.0.1:5000 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable gincana
sudo systemctl start gincana
```

Nginx como proxy reverso (`/etc/nginx/sites-available/gincana`):
```nginx
server {
    listen 80;
    server_name seu-dominio.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Credenciais padrão

| Usuário      | Senha       |
|--------------|-------------|
| admin        | gincana2025 |
| organizador  | fac@2025    |

⚠️ **Troque as senhas após o primeiro acesso!**

## Segurança implementada

- ✅ Senhas com hash bcrypt (nunca armazena texto puro)
- ✅ Sessões server-side (cookie seguro)
- ✅ Endpoints de escrita exigem login
- ✅ SQL parametrizado (sem SQL injection)
- ✅ Foreign keys com integridade referencial
- ✅ `SECRET_KEY` via variável de ambiente

## API disponível

| Método | Endpoint                | Acesso  | Descrição              |
|--------|-------------------------|---------|------------------------|
| POST   | /api/login              | Público | Autenticar             |
| POST   | /api/logout             | Logado  | Encerrar sessão        |
| GET    | /api/me                 | Público | Verificar sessão       |
| GET    | /api/cursos             | Público | Listar cursos          |
| POST   | /api/cursos             | Admin   | Cadastrar curso        |
| DELETE | /api/cursos/:id         | Admin   | Remover curso          |
| GET    | /api/turmas             | Público | Listar turmas          |
| POST   | /api/turmas             | Admin   | Cadastrar turma        |
| DELETE | /api/turmas/:id         | Admin   | Remover turma          |
| GET    | /api/lancamentos        | Público | Listar lançamentos     |
| POST   | /api/lancamentos        | Admin   | Registrar lançamento   |
| DELETE | /api/lancamentos/:id    | Admin   | Remover lançamento     |
| POST   | /api/senha              | Admin   | Trocar senha           |
