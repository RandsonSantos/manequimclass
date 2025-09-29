from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class CategoriaDestaque(db.Model):
    __tablename__ = 'categoria_destaque'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    quantidade = db.Column(db.Integer, default=0)

    imagens = db.relationship('Imagem', backref='categoria_destaque', lazy=True)

class Item(db.Model):
    __tablename__ = 'item'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    modelo = db.Column(db.String(50), nullable=False)        # vestido ou traje
    tipo = db.Column(db.String(50), nullable=False)          # aluguel ou venda
    categoria = db.Column(db.String(50), nullable=False)     # noiva, formatura, etc.
    descricao = db.Column(db.Text)
    imagem_principal = db.Column(db.String(100))             # primeira imagem
    disponivel = db.Column(db.Boolean, default=True)
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)
    data_evento = db.Column(db.Date)  # opcional

    imagens = db.relationship('Imagem', backref='item', lazy=True, cascade='all, delete-orphan')
    reservas = db.relationship('Reserva', backref='item', lazy=True)

    def pode_excluir(self):
        return len(self.reservas) == 0

class Imagem(db.Model):
    __tablename__ = 'imagem'

    id = db.Column(db.Integer, primary_key=True)
    caminho = db.Column(db.String(120), nullable=False)

    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria_destaque.id'), nullable=True)

from datetime import datetime

class Reserva(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    data_evento = db.Column(db.Date, nullable=False)
    turno = db.Column(db.String(10), nullable=False)
    confirmada = db.Column(db.Boolean, default=False)
    cancelada = db.Column(db.Boolean, default=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)  # ← novo campo

from flask_login import UserMixin

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuario'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(100), nullable=False)

class Cliente(db.Model):
    __tablename__ = 'cliente'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    cpf_cnpj = db.Column(db.String(20), nullable=False)
    endereco = db.Column(db.String(200), nullable=True)
    cidade = db.Column(db.String(100), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

class Pedido(db.Model):
    __tablename__ = 'pedido'

    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    data_evento = db.Column(db.Date, nullable=False)
    data_prova = db.Column(db.Date, nullable=True)
    data_retirada = db.Column(db.Date, nullable=True)
    data_devolucao = db.Column(db.Date, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    cliente = db.relationship('Cliente', backref='pedidos')
    item = db.relationship('Item', backref='pedidos')


class LogPedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'), nullable=False)
    usuario = db.Column(db.String(100))  # ou use relacionamento com User se tiver
    acao = db.Column(db.String(50))  # exemplo: 'criado', 'editado', 'excluído'
    detalhes = db.Column(db.Text)
    data = db.Column(db.DateTime, default=datetime.utcnow)
