from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_migrate import Migrate
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import os

# Modelos
from models import Cliente, LogPedido, Pedido, db, Item, Imagem, CategoriaDestaque, Reserva, Usuario

# App e configurações
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'sua_chave_secreta_aqui'

# Upload de imagens
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path,'static', 'images')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Inicializa banco e migração
db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    db.create_all()

# Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))


# Função auxiliar
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'jpg', 'jpeg', 'png', 'gif'}

# 🏠 Página inicial
@app.route('/')
def index():
    categorias = CategoriaDestaque.query.all()
    destaques = {
        cat.nome: {
            'imagens': cat.imagens,
            'quantidade': cat.quantidade
        } for cat in categorias
    }
    return render_template('index.html', destaques=destaques)


@app.route('/painel')
#@login_required
def painel():
    categorias = db.session.query(Item.categoria, db.func.count(Item.id)).group_by(Item.categoria).all()
    disponibilidade = {
        'disponíveis': Item.query.filter_by(disponivel=True).count(),
        'indisponíveis': Item.query.filter_by(disponivel=False).count()
    }
    reservas_por_mes = db.session.query(
        db.func.strftime('%m/%Y', Reserva.data_evento),
        db.func.count(Reserva.id)
    ).group_by(db.func.strftime('%m/%Y', Reserva.data_evento)).all()

    return render_template('painel.html',
        categorias=categorias,
        disponibilidade=disponibilidade,
        reservas_por_mes=reservas_por_mes
    )

@app.route('/cadastrar-usuario', methods=['GET', 'POST'])
#@login_required
def cadastrar_usuario():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = generate_password_hash(request.form['senha'])

        novo_usuario = Usuario(nome=nome, email=email, senha=senha)
        db.session.add(novo_usuario)
        db.session.commit()
        flash('Usuário cadastrado com sucesso!', 'success')
        return redirect(url_for('painel'))

    return render_template('cadastrar_usuario.html')

@app.route('/usuarios')
@login_required
def usuarios():
    todos = Usuario.query.order_by(Usuario.nome).all()
    return render_template('usuarios.html', usuarios=todos)

@app.route('/cadastrar-cliente', methods=['GET', 'POST'])
@login_required
def cadastrar_cliente():
    if request.method == 'POST':
        nome = request.form['nome']
        telefone = request.form['telefone']
        cpf_cnpj = request.form['cpf_cnpj']
        endereco = request.form.get('endereco')
        cidade = request.form['cidade']

        # Verifica se já existe cliente com mesmo CPF/CNPJ ou telefone
        cliente_existente = Cliente.query.filter(
            (Cliente.cpf_cnpj == cpf_cnpj) | (Cliente.telefone == telefone)
        ).first()

        if cliente_existente:
            flash('Cliente já cadastrado com este CPF/CNPJ ou telefone.', 'danger')
            return redirect(url_for('cadastrar_cliente'))

        novo_cliente = Cliente(
            nome=nome,
            telefone=telefone,
            cpf_cnpj=cpf_cnpj,
            endereco=endereco,
            cidade=cidade
        )
        db.session.add(novo_cliente)
        db.session.commit()

        flash('Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('clientes'))  # ✅ Redireciona para a listagem de clientes

    return render_template('cadastrar_cliente.html')

@app.route('/clientes')
@login_required
def clientes():
    pagina = request.args.get('pagina', 1, type=int)
    busca = request.args.get('busca', '', type=str)

    query = Cliente.query
    if busca:
        query = query.filter(
            Cliente.nome.ilike(f'%{busca}%') |
            Cliente.telefone.ilike(f'%{busca}%')
        )

    paginacao = query.order_by(Cliente.nome).paginate(page=pagina, per_page=10)
    return render_template('clientes.html', clientes=paginacao.items, paginacao=paginacao, busca=busca)

@app.route('/cliente/<int:cliente_id>')
@login_required
def ver_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    status = request.args.get('status')

    pedidos_query = Pedido.query.filter_by(cliente_id=cliente.id)

    if status == 'confirmado':
        pedidos_query = pedidos_query.filter_by(confirmado=True, cancelado=False)
    elif status == 'pendente':
        pedidos_query = pedidos_query.filter_by(confirmado=False, cancelado=False)
    elif status == 'cancelado':
        pedidos_query = pedidos_query.filter_by(cancelado=True)

    pedidos = pedidos_query.order_by(Pedido.data_evento.asc()).all()
    return render_template('ver_cliente.html', cliente=cliente, pedidos=pedidos, status=status)

@app.route('/cliente/<int:cliente_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == 'POST':
        cliente.nome = request.form['nome']
        cliente.telefone = request.form['telefone']
        cliente.cpf_cnpj = request.form['cpf_cnpj']
        cliente.cidade = request.form['cidade']
        cliente.endereco = request.form['endereco']
        
        db.session.commit()
        flash('Cliente atualizado com sucesso!', 'success')
        return redirect(url_for('ver_cliente', cliente_id=cliente.id))

    return render_template('editar_cliente.html', cliente=cliente)

@app.route('/cliente/<int:cliente_id>/pedidos')
@login_required
def pedidos_do_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    pedidos = Pedido.query.filter_by(cliente_id=cliente.id).order_by(Pedido.data_evento.desc()).all()
    return render_template('pedidos_do_cliente.html', cliente=cliente, pedidos=pedidos)

# 🔐 Autenticação
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and check_password_hash(usuario.senha, senha):
            login_user(usuario)
            return redirect('/painel')
        else:
            flash('Credenciais inválidas')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# 📦 Cadastro de item
@app.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    agora = datetime.now()
    if request.method == 'POST':
        nome = request.form['nome']
        modelo = request.form['modelo']
        tipo = request.form['tipo']
        categoria = request.form['categoria']
        descricao = request.form['descricao']
        disponivel = 'disponivel' in request.form
        imagens = request.files.getlist('imagens')

        imagem_principal = 'default.jpg'
        nomes_salvos = []

        for i, imagem in enumerate(imagens):
            if imagem and imagem.filename != '' and allowed_file(imagem.filename):
                filename = secure_filename(imagem.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                caminho = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                imagem.save(caminho)
                nomes_salvos.append(filename)

                if i == 0:
                    imagem_principal = filename

        novo_item = Item(
            nome=nome,
            modelo=modelo,
            tipo=tipo,
            categoria=categoria,
            descricao=descricao,
            imagem_principal=imagem_principal,
            disponivel=disponivel
        )
        db.session.add(novo_item)
        db.session.flush()  # garante que novo_item.id esteja disponível

        for nome in nomes_salvos:
            nova_imagem = Imagem(caminho=nome, item_id=novo_item.id)
            db.session.add(nova_imagem)

        db.session.commit()
        flash('Item cadastrado com sucesso!', 'success')
        return redirect(url_for('index'))

    return render_template('cadastrar.html', agora=agora)

# 🛍️ Listagem de produtos
@app.route('/produtos')
@login_required
def produtos():
    tipo = request.args.get('tipo')
    modelo = request.args.get('modelo')
    disponivel = request.args.get('disponivel')

    query = Item.query
    if tipo:
        query = query.filter_by(tipo=tipo)
    if modelo:
        query = query.filter_by(modelo=modelo)
    if disponivel in ['0', '1']:
        query = query.filter_by(disponivel=bool(int(disponivel)))

    itens = query.order_by(Item.nome).all()
    agora = datetime.now()
    return render_template('produtos.html', itens=itens, agora=agora)

# ✏️ Edição de item
@app.route('/editar/<int:item_id>', methods=['GET', 'POST'])
def editar_item(item_id):
    item = Item.query.get_or_404(item_id)

    if request.method == 'POST':
        item.nome = request.form.get('nome')
        item.tipo = request.form.get('tipo')
        item.modelo = request.form.get('modelo')
        item.descricao = request.form.get('descricao')
        item.disponivel = 'disponivel' in request.form

        novas_imagens = request.files.getlist('imagens')
        for imagem in novas_imagens:
            if imagem and imagem.filename and allowed_file(imagem.filename):
                filename = secure_filename(imagem.filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                caminho = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                imagem.save(caminho)

                nova_imagem = Imagem(caminho=filename, item_id=item.id)
                db.session.add(nova_imagem)

        db.session.commit()
        flash('Item atualizado com sucesso!', 'success')
        return redirect(url_for('produtos'))

    return render_template('editar_item.html', item=item)

# 🗑️ Excluir imagem
@app.route('/excluir_imagem/<int:imagem_id>', methods=['POST'])
@login_required
def excluir_imagem(imagem_id):
    imagem = Imagem.query.get_or_404(imagem_id)
    item_id = imagem.item_id

    caminho = os.path.join(app.config['UPLOAD_FOLDER'], imagem.caminho)
    if os.path.exists(caminho):
        os.remove(caminho)

    db.session.delete(imagem)
    db.session.commit()
    flash('Imagem excluída com sucesso!', 'success')
    return redirect(url_for('editar_item', item_id=item_id))

# 🌟 Definir miniatura
@app.route('/definir_miniatura/<int:imagem_id>', methods=['POST'])
def definir_miniatura(imagem_id):
    imagem = Imagem.query.get_or_404(imagem_id)
    item = Item.query.get_or_404(imagem.item_id)

    item.imagem_principal = imagem.caminho
    db.session.commit()
    flash('Miniatura atualizada com sucesso!', 'success')
    return redirect(url_for('editar_item', item_id=item.id))

# 🧵 Catálogo
@app.route('/catalogo')
def catalogo():
    categorias = ['noiva', 'noivo', 'debutante', 'formatura', 'crianca']
    
    destaques = {}
    for categoria in categorias:
        item = Item.query.filter_by(categoria=categoria).first()
        if item:
            item.quantidade = Item.query.filter_by(categoria=categoria).count()
        destaques[categoria] = item

    agora = datetime.now()
    return render_template('catalogo.html', destaques=destaques, agora=agora)

# Página de categoria
@app.route('/categoria/<categoria>')
def categoria(categoria):
    categorias_validas = ['noiva', 'noivo', 'debutante', 'formatura', 'crianca']
    if categoria not in categorias_validas:
        flash('Categoria inválida.', 'danger')
        return redirect(url_for('catalogo'))

    itens = Item.query.filter_by(categoria=categoria).order_by(Item.nome).all()
    agora = datetime.now()
    return render_template('categoria.html', categoria=categoria, itens=itens, agora=agora)

# Página de detalhes do item
from flask import render_template, request
from datetime import date, datetime, timedelta
from models import Item, Imagem, Reserva
from flask import request, redirect, url_for, flash
from datetime import datetime
from models import Item, Reserva

@app.route('/item/<int:item_id>')
def item(item_id):
    item = Item.query.get_or_404(item_id)
    imagens = Imagem.query.filter_by(item_id=item.id).all()
    current_date = date.today().isoformat()
    agora = datetime.now()

    data_param = request.args.get('data_evento', current_date)

    reservas_por_turno = {
        'manhã': Reserva.query.filter_by(item_id=item.id, data_evento=data_param, turno='manhã', cancelada=False).count(),
        'tarde': Reserva.query.filter_by(item_id=item.id, data_evento=data_param, turno='tarde', cancelada=False).count()
    }

    datas_livres = []
    for i in range(0, 10):  # próximos 6 meses
        dia = date.today() + timedelta(days=i)
        dia_str = dia.isoformat()
        dia_semana = dia.weekday()  # 0 = segunda, 6 = domingo

        # Excluir domingos
        if dia_semana == 6:
            continue

        # Excluir sábado à tarde (opcional)
        if dia_semana == 5:
            reservas_tarde = Reserva.query.filter_by(item_id=item.id, data_evento=dia_str, turno='tarde', cancelada=False).count()
            if reservas_tarde >= 0:
                continue

        reservas_manha = Reserva.query.filter_by(item_id=item.id, data_evento=dia_str, turno='manhã', cancelada=False).count()
        reservas_tarde = Reserva.query.filter_by(item_id=item.id, data_evento=dia_str, turno='tarde', cancelada=False).count()

        if reservas_manha < 2 or reservas_tarde < 2:
            datas_livres.append(dia_str)

    return render_template(
        'item.html',
        item=item,
        imagens=imagens,
        current_date=current_date,
        agora=agora,
        reservas_por_turno=reservas_por_turno,
        data_param=data_param,
        datas_livres=datas_livres
    )

@app.route('/reservar/<int:item_id>', methods=['POST'])
def reservar(item_id):
    item = Item.query.get_or_404(item_id)

    nome = request.form.get('nome')
    telefone = request.form.get('telefone')
    data_evento_str = request.form.get('data_evento')
    turno = request.form.get('turno')

    if not nome or not telefone or not data_evento_str or not turno:
        flash('Todos os campos são obrigatórios.', 'danger')
        return redirect(url_for('item', item_id=item.id))

    try:
        data_evento = datetime.strptime(data_evento_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Data inválida. Use o formato correto (AAAA-MM-DD).', 'danger')
        return redirect(url_for('item', item_id=item.id))

    total_reservas = Reserva.query.filter_by(
        item_id=item.id,
        data_evento=data_evento,
        turno=turno,
        cancelada=False
    ).count()

    if total_reservas >= 2:
        flash(f'O turno da {turno} já está lotado para {data_evento.strftime("%d/%m/%Y")}. Escolha outro turno ou data.', 'warning')
        return redirect(url_for('item', item_id=item.id))

    nova_reserva = Reserva(
        nome=nome,
        telefone=telefone,
        item_id=item.id,
        data_evento=data_evento,
        turno=turno,
        confirmada=False,
        cancelada=False,
        data_criacao=datetime.now()
    )

    db.session.add(nova_reserva)
    db.session.commit()

    flash('Reserva registrada com sucesso! Aguarde confirmação.', 'success')
    return redirect(url_for('item', item_id=item.id))

@app.route('/reserva/<int:reserva_id>/confirmar', methods=['POST'])
@login_required
def confirmar_reserva(reserva_id):
    reserva = Reserva.query.get_or_404(reserva_id)
    reserva.confirmada = True
    db.session.commit()
    flash('Reserva marcada como confirmada.', 'success')
    return redirect(url_for('listar_reservas'))

@app.route('/reserva/<int:reserva_id>/cancelar', methods=['POST'])
@login_required
def cancelar_reserva(reserva_id):
    reserva = Reserva.query.get_or_404(reserva_id)

    if reserva.cancelada:
        flash('Reserva já está cancelada.', 'info')
        return redirect(url_for('listar_reservas'))

    reserva.cancelada = True
    db.session.commit()

    # Enviar mensagem via WhatsApp
    numero_formatado = reserva.telefone.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
    mensagem = (
        f"Olá {reserva.nome}! Sua reserva para o item \"{reserva.item.nome}\" no dia "
        f"{reserva.data_evento.strftime('%d/%m/%Y')} foi cancelada. Se precisar reagendar, estamos à disposição!"
    )
    link_whatsapp = f"https://wa.me/55{numero_formatado}?text={mensagem}"

    flash('Reserva cancelada com sucesso.', 'warning')
    return redirect(link_whatsapp)

@app.route('/ver_pedido_de_prova/<int:reserva_id>')
@login_required
def ver_pedido_de_prova(reserva_id):
    reserva = Reserva.query.get_or_404(reserva_id)
    return render_template('ver_pedido_de_prova.html', reserva=reserva)


from flask import render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime, timedelta
from flask_login import login_required
@app.route('/reservas')
@login_required
def listar_reservas():
    status = request.args.get('status', 'pendente')  # padrão: pendente
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = Reserva.query

    if status == 'confirmada':
        query = query.filter_by(confirmada=True, cancelada=False)
    elif status == 'cancelada':
        query = query.filter_by(cancelada=True)
    elif status == 'pendente':
        query = query.filter_by(confirmada=False, cancelada=False)
    else:
        query = query.filter_by(cancelada=False)  # todas ativas

    reservas_paginadas = query.order_by(Reserva.data_evento.desc()).paginate(page=page, per_page=per_page)
    return render_template('reservas.html', reservas=reservas_paginadas.items, pagination=reservas_paginadas, status=status)

@app.route('/fazer-pedido', methods=['GET', 'POST'])
@login_required
def fazer_pedido():
    clientes = Cliente.query.order_by(Cliente.nome).all()
    itens = Item.query.filter_by(disponivel=True).order_by(Item.nome).all()

    if request.method == 'POST':
        try:
            cliente_id = int(request.form['cliente_id'])
            item_id = int(request.form['item_id'])
            data_evento = datetime.strptime(request.form['data_evento'], '%Y-%m-%d').date()

            # Verifica se há conflito com margem de 2 dias antes e depois
            conflitos = Pedido.query.filter(
                Pedido.item_id == item_id,
                Pedido.data_evento >= data_evento - timedelta(days=2),
                Pedido.data_evento <= data_evento + timedelta(days=2)
            ).all()

            if conflitos:
                item = Item.query.get(item_id)
                flash(f'O item "{item.nome}" está indisponível entre {data_evento - timedelta(days=2):%d/%m/%Y} e {data_evento + timedelta(days=2):%d/%m/%Y}. Escolha outra data ou item.', 'warning')
                return redirect(url_for('fazer_pedido'))

            data_retirada = data_evento - timedelta(days=1)
            data_devolucao = data_evento + timedelta(days=1)

            data_prova_raw = request.form.get('data_prova')
            data_prova = datetime.strptime(data_prova_raw, '%Y-%m-%d').date() if data_prova_raw else None
            observacoes = request.form.get('observacoes')

            novo_pedido = Pedido(
                cliente_id=cliente_id,
                item_id=item_id,
                data_evento=data_evento,
                data_prova=data_prova,
                data_retirada=data_retirada,
                data_devolucao=data_devolucao,
                observacoes=observacoes
            )
            db.session.add(novo_pedido)
            db.session.commit()

            log = LogPedido(
                pedido_id=novo_pedido.id,
                usuario=current_user.nome,
                acao='criado',
                detalhes=f'Pedido criado para item {item_id} na data {data_evento.strftime("%d/%m/%Y")}'
            )
            db.session.add(log)
            db.session.commit()

            flash('Pedido realizado com sucesso!', 'success')
            return redirect(url_for('painel'))

        except Exception as e:
            flash(f'Ocorreu um erro ao processar o pedido: {str(e)}', 'danger')
            return redirect(url_for('fazer_pedido'))

    # Sempre renderiza o template no GET ou após erro no POST
    pedidos = Pedido.query.all()
    datas_bloqueadas = set()
    datas_livres = []

    hoje = date.today()
    for i in range(0, 180):
        dia = hoje + timedelta(days=i)
        dia_str = dia.isoformat()

        bloqueado = False
        for pedido in pedidos:
            for j in range(-2, 3):  # -2 a +2
                if (pedido.data_evento + timedelta(days=j)).isoformat() == dia_str:
                    bloqueado = True
                    datas_bloqueadas.add(dia_str)
                    break
            if bloqueado:
                break

        if not bloqueado:
            datas_livres.append(dia_str)

    return render_template(
        'fazer_pedido.html',
        clientes=clientes,
        itens=itens,
        datas_bloqueadas=list(datas_bloqueadas),
        datas_livres=datas_livres
    )

@app.route('/pedidos')
@login_required
def pedidos():
    mes = request.args.get('mes', type=int)
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)

    query = Pedido.query

    if mes:
        query = query.filter(db.extract('month', Pedido.data_evento) == mes)

    if status == 'pendente':
        query = query.filter(Pedido.confirmado == False, Pedido.cancelado == False)
    elif status == 'confirmado':
        query = query.filter(Pedido.confirmado == True)
    elif status == 'cancelado':
        query = query.filter(Pedido.cancelado == True)

    pedidos_paginados = query.order_by(Pedido.data_evento.asc()).paginate(page=page, per_page=10)
    return render_template('pedidos.html', pedidos=pedidos_paginados.items, pagination=pedidos_paginados)

@app.route('/pedido/<int:pedido_id>')
@login_required
def ver_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    cliente = Cliente.query.get(pedido.cliente_id)
    item = Item.query.get(pedido.item_id)
    return render_template('ver_pedido.html', pedido=pedido, cliente=cliente, item=item)


@app.route('/pedido/<int:pedido_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    clientes = Cliente.query.order_by(Cliente.nome).all()
    itens = Item.query.order_by(Item.nome).all()

    if request.method == 'POST':
        cliente_id = request.form['cliente_id']
        item_id = request.form['item_id']
        data_evento = datetime.strptime(request.form['data_evento'], '%Y-%m-%d').date()

        # Verifica conflito com margem de 2 dias
        conflito = Pedido.query.filter(
            Pedido.item_id == item_id,
            Pedido.id != pedido.id,
            Pedido.data_evento >= data_evento - timedelta(days=2),
            Pedido.data_evento <= data_evento + timedelta(days=2)
        ).first()

        if conflito:
            flash('Este item está reservado em datas próximas por outro pedido.', 'danger')
            return redirect(url_for('editar_pedido', pedido_id=pedido.id))

        # Atualiza os dados
        pedido.cliente_id = cliente_id
        pedido.item_id = item_id
        pedido.data_evento = data_evento
        pedido.data_prova = datetime.strptime(request.form['data_prova'], '%Y-%m-%d').date() if request.form['data_prova'] else None
        pedido.data_retirada = datetime.strptime(request.form['data_retirada'], '%Y-%m-%d').date() if request.form['data_retirada'] else None
        pedido.data_devolucao = datetime.strptime(request.form['data_devolucao'], '%Y-%m-%d').date() if request.form['data_devolucao'] else None
        pedido.observacoes = request.form.get('observacoes')

        db.session.commit()
        flash('Pedido atualizado com sucesso!', 'success')
        return redirect(url_for('ver_pedido', pedido_id=pedido.id))

    # Gera datas bloqueadas e livres
    pedidos = Pedido.query.filter(Pedido.id != pedido.id).all()
    datas_bloqueadas = set()
    datas_livres = []
    datas_livres_devolucao = []

    hoje = date.today()
    for i in range(0, 180):
        dia = hoje + timedelta(days=i)
        dia_str = dia.isoformat()

        bloqueado = False
        for p in pedidos:
            for j in range(-2, 3):
                if (p.data_evento + timedelta(days=j)).isoformat() == dia_str:
                    bloqueado = True
                    datas_bloqueadas.add(dia_str)
                    break
            if bloqueado:
                break

        if not bloqueado:
            datas_livres.append(dia_str)

    # Filtra datas livres para devolução (mínimo 3 dias antes de qualquer evento)
    for dia_str in datas_livres:
        try:
            dia = datetime.strptime(dia_str, '%Y-%m-%d').date()
        except ValueError:
            continue  # ignora datas inválidas

        livre = True
        for p in pedidos:
            if p.data_evento and 0 <= (p.data_evento - dia).days <= 3:
                livre = False
                break
        if livre:
            datas_livres_devolucao.append(dia_str)

    # Garante que todas as variáveis estão definidas
    return render_template(
        'editar_pedido.html',
        pedido=pedido,
        clientes=clientes,
        itens=itens,
        datas_bloqueadas=list(datas_bloqueadas or []),
        datas_livres=datas_livres or [],
        datas_livres_devolucao=datas_livres_devolucao or []
    )

@app.route('/datas-indisponiveis/<int:item_id>')
@login_required
def datas_indisponiveis(item_id):
    pedidos = Pedido.query.filter_by(item_id=item_id).all()
    datas = [pedido.data_evento.strftime('%Y-%m-%d') for pedido in pedidos]
    return jsonify(datas)


import qrcode
import os

@app.route('/pedido/<int:pedido_id>/imprimir')
def imprimir_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    cliente = Cliente.query.get(pedido.cliente_id)
    item = Item.query.get(pedido.item_id)

    # Gera QR Code
    url = url_for('ver_pedido', pedido_id=pedido.id, _external=True)
    qr = qrcode.make(url)
    qr_path = f'static/qrcodes/pedido_{pedido.id}.png'
    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
    qr.save(qr_path)

    return render_template('imprimir_pedido.html', pedido=pedido, cliente=cliente, item=item, qr_path=qr_path)

@app.context_processor
def inject_now():
    from datetime import datetime
    return {'now': datetime.now}

# Executa o app
if __name__ == '__main__':
    app.run(debug=True)
