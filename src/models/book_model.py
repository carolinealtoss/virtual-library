import sqlite3
from contextlib import closing
from os import PathLike
from pathlib import Path

from flask import current_app, g

# Maior identificador suportado pelo INTEGER do SQLite.
MAX_BOOK_ID = 2**63 - 1


# Reutiliza a conexão SQLite durante toda a requisição atual.
def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


# Fecha a conexão SQLite ao terminar a requisição.
def close_db(_error: BaseException | None = None) -> None:
    database = g.pop("db", None)
    if database is not None:
        database.close()


# Cria o banco e a tabela de livros antes de atender requisições.
def initialize_database(database_path: str | PathLike[str]) -> None:
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as database:
        database.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                publication_date TEXT NOT NULL,
                summary TEXT NOT NULL
            )
            """
        )
        database.commit()


# Escapa os curingas do LIKE para que a busca trate % e _ como texto comum.
def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Indica se o identificador cabe no INTEGER de 64 bits do SQLite.
def is_valid_id(book_id: int) -> bool:
    return 0 < book_id <= MAX_BOOK_ID


# Busca livros, filtrando opcionalmente por título e autor (parcial, sem diferenciar maiúsculas).
def find_books(title: str = "", author: str = "") -> list[sqlite3.Row]:
    conditions: list[str] = []
    values: list[str] = []

    if title:
        conditions.append("title LIKE ? ESCAPE '\\' COLLATE NOCASE")
        values.append(f"%{escape_like(title)}%")
    if author:
        conditions.append("author LIKE ? ESCAPE '\\' COLLATE NOCASE")
        values.append(f"%{escape_like(author)}%")

    query = "SELECT * FROM books"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id"

    return get_db().execute(query, values).fetchall()


# Busca um livro pelo identificador; retorna None se não existir.
def find_book_by_id(book_id: int) -> sqlite3.Row | None:
    if not is_valid_id(book_id):
        return None
    return get_db().execute(
        "SELECT * FROM books WHERE id = ?", (book_id,)
    ).fetchone()


# Insere um livro e retorna o registro salvo.
def insert_book(book: dict[str, str]) -> sqlite3.Row | None:
    database = get_db()
    cursor = database.execute(
        """
        INSERT INTO books (title, author, publication_date, summary)
        VALUES (?, ?, ?, ?)
        """,
        (
            book["title"],
            book["author"],
            book["publication_date"],
            book["summary"],
        ),
    )
    database.commit()
    if cursor.lastrowid is None:
        return None
    return find_book_by_id(cursor.lastrowid)


# Atualiza todos os campos de um livro; retorna None se ele não existir.
def update_book_by_id(book_id: int, book: dict[str, str]) -> sqlite3.Row | None:
    if not is_valid_id(book_id):
        return None
    database = get_db()
    cursor = database.execute(
        """
        UPDATE books
        SET title = ?, author = ?, publication_date = ?, summary = ?
        WHERE id = ?
        """,
        (
            book["title"],
            book["author"],
            book["publication_date"],
            book["summary"],
            book_id,
        ),
    )
    database.commit()
    if cursor.rowcount == 0:
        return None
    return find_book_by_id(book_id)


# Exclui um livro; retorna False se ele não existir.
def delete_book_by_id(book_id: int) -> bool:
    if not is_valid_id(book_id):
        return False
    database = get_db()
    cursor = database.execute("DELETE FROM books WHERE id = ?", (book_id,))
    database.commit()
    return cursor.rowcount > 0
