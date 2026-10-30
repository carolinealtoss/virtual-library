import sqlite3
from datetime import date

from flask import Blueprint, Response, jsonify, request
from flask.blueprints import BlueprintSetupState

from src.models.book_model import (
    close_db,
    delete_book_by_id,
    find_book_by_id,
    find_books,
    initialize_database,
    insert_book,
    update_book_by_id,
)


book_bp = Blueprint("book_bp", __name__)


# Lista ou pesquisa livros por título e autor.
@book_bp.route("/books", methods=["GET"])
def list_books() -> tuple[Response, int]:
    title = request.args.get("title", "").strip()
    author = request.args.get("author", "").strip()
    books = find_books(title, author)
    return jsonify([_serialize_book(book) for book in books]), 200


# Valida e cadastra um livro enviado em JSON.
@book_bp.route("/books", methods=["POST"])
def create_book() -> tuple[Response, int]:
    if not request.is_json:
        return jsonify({"error": "O Content-Type deve ser application/json."}), 415

    data = request.get_json(silent=True)
    book, error = _validate_book(data)
    if book is None or error is not None:
        return jsonify({"error": error or "Dados do livro inválidos."}), 400

    saved_book = insert_book(book)
    if saved_book is None:
        return jsonify({"error": "Não foi possível recuperar o livro cadastrado."}), 500
    return jsonify(_serialize_book(saved_book)), 201


# Consulta um livro pelo identificador ou retorna 404.
@book_bp.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id: int) -> tuple[Response, int]:
    book = find_book_by_id(book_id)
    if book is None:
        return jsonify({"error": "Livro não encontrado."}), 404
    return jsonify(_serialize_book(book)), 200


# Atualiza todos os campos de um livro existente.
@book_bp.route("/books/<int:book_id>", methods=["PUT"])
def update_book(book_id: int) -> tuple[Response, int]:
    if not request.is_json:
        return jsonify({"error": "O Content-Type deve ser application/json."}), 415

    data = request.get_json(silent=True)
    book, error = _validate_book(data)
    if book is None or error is not None:
        return jsonify({"error": error or "Dados do livro inválidos."}), 400

    updated_book = update_book_by_id(book_id, book)
    if updated_book is None:
        return jsonify({"error": "Livro não encontrado."}), 404
    return jsonify(_serialize_book(updated_book)), 200


# Exclui um livro existente ou retorna 404.
@book_bp.route("/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id: int) -> Response | tuple[Response, int]:
    if not delete_book_by_id(book_id):
        return jsonify({"error": "Livro não encontrado."}), 404
    return Response(status=204)

# Prepara o banco e o fechamento das conexões ao registrar o Blueprint.
@book_bp.record
def setup_book_controller(state: BlueprintSetupState) -> None:
    app = state.app
    initialize_database(app.config["DATABASE"])
    app.teardown_appcontext(close_db)


# Converte uma linha SQLite no formato JSON público da API.
def _serialize_book(book: sqlite3.Row) -> dict[str, int | str]:
    return {
        "id": book["id"],
        "title": book["title"],
        "author": book["author"],
        "publication_date": book["publication_date"],
        "summary": book["summary"],
    }


# Valida os campos obrigatórios e o formato ISO da data.
def _validate_book(
    data: object,
) -> tuple[dict[str, str] | None, str | None]:
    if not isinstance(data, dict):
        return None, "O corpo da requisição deve ser um objeto JSON."

    fields = ("title", "author", "publication_date", "summary")
    missing_fields = [field for field in fields if field not in data]
    if missing_fields:
        return None, f"Campos obrigatórios ausentes: {', '.join(missing_fields)}."

    if any(not isinstance(data[field], str) for field in fields):
        return None, "Todos os campos devem ser enviados como texto."

    book = {field: data[field].strip() for field in fields}
    if not book["title"] or not book["author"]:
        return None, "Título e autor não podem ficar vazios."

    try:
        publication_date = date.fromisoformat(book["publication_date"])
    except ValueError:
        return None, "A data de publicação deve usar o formato AAAA-MM-DD."
    if publication_date.isoformat() != book["publication_date"]:
        return None, "A data de publicação deve usar o formato AAAA-MM-DD."

    return book, None
