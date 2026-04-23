"""
GincanaFAC — Backend Flask + PostgreSQL (Vercel + Neon)
Instalar: pip install flask flask-cors bcrypt psycopg2-binary
Rodar:    python app.py
"""

from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt, os, uuid
from datetime import datetime, timedelta
from functools import wraps

# Garante que os caminhos estáticos funcionem corretamente na Vercel
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=os.path.join(BASE_DIR, 'templates'))
app.secret_key = os.environ.get('SECRET_KEY', 'troque-por-uma-chave-secreta-aleatoria-longa')
app.permanent_session_lifetime = timedelta(hours=8)
CORS(app, supports_credentials=True)

# URL do banco de dados (pega da variável de ambiente da Vercel)
DATABASE_URL = os.environ.get('DATABASE_URL')

# ─── BANCO DE DADOS (POSTGRESQL) ──────────────────────────────────────────────
def get_db():
    # Retorna as linhas como dicionários (igual ao sqlite3.Row) e usa autocommit
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    conn.autocommit = True 
    return conn

def init_db():
    if not DATABASE_URL:
        print("Aviso: DATABASE_URL não configurada. Ignorando a criação das tabelas.")
        return

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id      TEXT PRIMARY KEY,
                "user"  TEXT UNIQUE NOT NULL,
                pass_h  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cursos (
                id    TEXT PRIMARY KEY,
                nome  TEXT NOT NULL,
                sigla TEXT NOT NULL,
                cor   TEXT NOT NULL DEFAULT '#5b7cfa'
            );
            CREATE TABLE IF NOT EXISTS turmas (
                id        TEXT PRIMARY KEY,
                nome      TEXT NOT NULL,
                curso_id  TEXT NOT NULL REFERENCES cursos(id),
                periodo   TEXT NOT NULL,
                alunos    INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS lancamentos (
                id        TEXT PRIMARY KEY,
                turma_id  TEXT NOT NULL REFERENCES turmas(id),
                qtde      INTEGER NOT NULL,
                tipo      TEXT NOT NULL,
                emoji     TEXT,
                pts_un    INTEGER NOT NULL,
                pontos    INTEGER NOT NULL,
                obs       TEXT,
                data      TEXT NOT NULL
            );
            """)
            
            # Cria usuários padrão se não existirem
            for user, pwd in [('admin', 'gincana2025'), ('organizador', 'fac@2025')]:
                cur.execute('SELECT id FROM usuarios WHERE "user"=%s', (user,))
                row = cur.fetchone()
                if not row:
                    h = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
                    cur.execute('INSERT INTO usuarios (id, "user", pass_h) VALUES (%s,%s,%s)', (str(uuid.uuid4()), user, h))

# Inicia o banco de dados na inicialização
init_db()

# ─── AUTH ─────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Não autorizado'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = (data.get('user') or '').strip().lower()
    pwd  = (data.get('pass') or '').encode()
    
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pass_h FROM usuarios WHERE lower("user")=%s', (user,))
            row = cur.fetchone()
            
    if row and bcrypt.checkpw(pwd, row['pass_h'].encode()):
        session.permanent = True
        session['logged_in'] = True
        session['user'] = user
        return jsonify({'ok': True, 'user': user})
    return jsonify({'error': 'Usuário ou senha inválidos'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/me')
def me():
    if session.get('logged_in'):
        return jsonify({'logged': True, 'user': session.get('user')})
    return jsonify({'logged': False})

# ─── CURSOS ───────────────────────────────────────────────────────────────────
@app.route('/api/cursos', methods=['GET'])
def get_cursos():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cursos ORDER BY nome")
            rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/cursos', methods=['POST'])
@login_required
def add_curso():
    d = request.get_json()
    nome  = (d.get('nome') or '').strip()
    sigla = (d.get('sigla') or '').strip().upper()
    cor   = d.get('cor', '#5b7cfa')
    
    if not nome or not sigla:
        return jsonify({'error': 'Nome e sigla são obrigatórios'}), 400
        
    nid = str(uuid.uuid4())[:8]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO cursos VALUES (%s,%s,%s,%s)", (nid, nome, sigla, cor))
            
    return jsonify({'id': nid, 'nome': nome, 'sigla': sigla, 'cor': cor}), 201

@app.route('/api/cursos/<cid>', methods=['DELETE'])
@login_required
def del_curso(cid):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as n FROM turmas WHERE curso_id=%s", (cid,))
            uso = cur.fetchone()['n']
            if uso > 0:
                return jsonify({'error': 'Curso possui turmas, exclua as turmas primeiro'}), 400
            cur.execute("DELETE FROM cursos WHERE id=%s", (cid,))
            
    return jsonify({'ok': True})

# ─── TURMAS ───────────────────────────────────────────────────────────────────
@app.route('/api/turmas', methods=['GET'])
def get_turmas():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT t.*, c.nome as curso_nome, c.sigla as curso_sigla, c.cor as curso_cor
                FROM turmas t JOIN cursos c ON t.curso_id=c.id
                ORDER BY t.nome
            """)
            rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/turmas', methods=['POST'])
@login_required
def add_turma():
    d = request.get_json()
    nome     = (d.get('nome') or '').strip()
    curso_id = d.get('cursoId') or d.get('curso_id') or ''
    periodo  = d.get('periodo', 'Manhã')
    alunos   = int(d.get('alunos') or 0)
    
    if not nome or not curso_id:
        return jsonify({'error': 'Nome e curso são obrigatórios'}), 400
        
    nid = str(uuid.uuid4())[:8]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO turmas VALUES (%s,%s,%s,%s,%s)", (nid, nome, curso_id, periodo, alunos))
            
    return jsonify({'id': nid, 'nome': nome, 'cursoId': curso_id, 'periodo': periodo, 'alunos': alunos}), 201

@app.route('/api/turmas/<tid>', methods=['DELETE'])
@login_required
def del_turma(tid):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as n FROM lancamentos WHERE turma_id=%s", (tid,))
            uso = cur.fetchone()['n']
            if uso > 0:
                return jsonify({'error': 'Turma possui lançamentos, exclua-os primeiro'}), 400
            cur.execute("DELETE FROM turmas WHERE id=%s", (tid,))
            
    return jsonify({'ok': True})

# ─── LANÇAMENTOS ──────────────────────────────────────────────────────────────
@app.route('/api/lancamentos', methods=['GET'])
def get_lancs():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT l.*, t.nome as turma_nome, c.sigla as curso_sigla
                FROM lancamentos l
                JOIN turmas t ON l.turma_id=t.id
                JOIN cursos c ON t.curso_id=c.id
                ORDER BY l.data DESC
            """)
            rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/lancamentos', methods=['POST'])
@login_required
def add_lanc():
    d = request.get_json()
    turma_id = d.get('turmaId') or d.get('turma_id') or ''
    qtde     = int(d.get('qtde') or 0)
    tipo     = (d.get('tipo') or '').strip()
    emoji    = d.get('emoji', '📦')
    pts_un   = int(d.get('ptsUn') or d.get('pts_un') or 0)
    pontos   = int(d.get('pontos') or 0)
    obs      = d.get('obs', '')
    data     = d.get('data') or datetime.now().isoformat()
    
    if not turma_id or qtde <= 0 or pts_un <= 0:
        return jsonify({'error': 'Dados inválidos'}), 400
        
    nid = str(uuid.uuid4())[:8]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO lancamentos VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (nid, turma_id, qtde, tipo, emoji, pts_un, pontos, obs, data)
            )
            
    return jsonify({'id': nid}), 201

@app.route('/api/lancamentos/<lid>', methods=['DELETE'])
@login_required
def del_lanc(lid):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM lancamentos WHERE id=%s", (lid,))
            
    return jsonify({'ok': True})

# ─── TROCAR SENHA ─────────────────────────────────────────────────────────────
@app.route('/api/senha', methods=['POST'])
@login_required
def trocar_senha():
    d = request.get_json()
    atual = (d.get('atual') or '').encode()
    nova  = (d.get('nova')  or '').strip()
    
    if len(nova) < 6:
        return jsonify({'error': 'Nova senha deve ter ao menos 6 caracteres'}), 400
        
    user = session.get('user')
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT pass_h FROM usuarios WHERE lower("user")=%s', (user,))
            row = cur.fetchone()
            
            if not row or not bcrypt.checkpw(atual, row['pass_h'].encode()):
                return jsonify({'error': 'Senha atual incorreta'}), 401
                
            novo_h = bcrypt.hashpw(nova.encode(), bcrypt.gensalt()).decode()
            cur.execute('UPDATE usuarios SET pass_h=%s WHERE lower("user")=%s', (novo_h, user))
            
    return jsonify({'ok': True})

# ─── SERVE O FRONTEND ─────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(STATIC_DIR, path)

# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    print(f"🧥 GincanaFAC rodando em http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)