import os
import sqlite3
import tempfile
import unittest

from flask import Flask, g

from src.models.book_model import (
    MAX_BOOK_ID,
    close_db,
    delete_book_by_id,
    escape_like,
    find_book_by_id,
    find_books,
    get_db,
    initialize_database,
    insert_book,
    is_valid_id,
    update_book_by_id,
)


# Testa as funções de acesso ao banco SQLite (sucesso e falhas).
class BookModelTestCase(unittest.TestCase):
    # Cria um app com banco temporário e mantém um contexto de aplicação ativo.
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temporary_directory.name, "test.sqlite3")
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=self.database_path)
        initialize_database(self.database_path)
        self.context = self.app.app_context()
        self.context.push()

    # Fecha a conexão, encerra o contexto e remove o banco temporário.
    def tearDown(self) -> None:
        close_db()
        self.context.pop()
        self.temporary_directory.cleanup()

    # Fornece um livro válido, permitindo sobrescrever campos.
    def book(self, **overrides: str) -> dict[str, str]:
        book = {
            "title": "Dom Casmurro",
            "author": "Machado de Assis",
            "publication_date": "1899-01-01",
            "summary": "Resumo.",
        }
        book.update(overrides)
        return book

    # initialize_database cria a tabela books com as colunas esperadas.
    def test_initialize_database_creates_table(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(books)")]
        finally:
            connection.close()

        self.assertEqual(
            columns, ["id", "title", "author", "publication_date", "summary"]
        )

    # initialize_database cria diretórios ausentes e pode rodar várias vezes.
    def test_initialize_database_creates_directory_and_is_idempotent(self) -> None:
        nested_path = os.path.join(self.temporary_directory.name, "a", "b", "db.sqlite3")

        initialize_database(nested_path)
        initialize_database(nested_path)

        self.assertTrue(os.path.exists(nested_path))

    # initialize_database falha se o caminho for um diretório.
    def test_initialize_database_invalid_path(self) -> None:
        with self.assertRaises(sqlite3.OperationalError):
            initialize_database(self.temporary_directory.name)

    # get_db reutiliza a mesma conexão e usa sqlite3.Row.
    def test_get_db_reuses_connection(self) -> None:
        first = get_db()

        self.assertIs(get_db(), first)
        self.assertIs(first.row_factory, sqlite3.Row)

    # close_db fecha e remove a conexão; chamar sem conexão não falha.
    def test_close_db(self) -> None:
        connection = get_db()

        close_db()

        self.assertNotIn("db", g)
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")
        close_db()

    # close_db aceita o argumento de erro enviado pelo teardown do Flask.
    def test_close_db_accepts_teardown_error(self) -> None:
        get_db()

        close_db(RuntimeError("falha"))

        self.assertNotIn("db", g)

    # insert_book salva e retorna o registro com id.
    def test_insert_book(self) -> None:
        saved = insert_book(self.book())

        assert saved is not None
        self.assertEqual(saved["id"], 1)
        self.assertEqual(saved["title"], "Dom Casmurro")

    # insert_book falha com campos ausentes.
    def test_insert_book_missing_field(self) -> None:
        incomplete = self.book()
        del incomplete["summary"]

        with self.assertRaises(KeyError):
            insert_book(incomplete)

    # insert_book falha ao violar NOT NULL do banco.
    def test_insert_book_null_value(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            insert_book({**self.book(), "title": None})  # type: ignore[dict-item]

    # find_book_by_id retorna o livro existente.
    def test_find_book_by_id(self) -> None:
        saved = insert_book(self.book())
        assert saved is not None

        found = find_book_by_id(saved["id"])

        assert found is not None
        self.assertEqual(found["author"], "Machado de Assis")

    # find_book_by_id retorna None para ids inexistentes ou fora do intervalo.
    def test_find_book_by_id_not_found(self) -> None:
        for book_id in (1, 0, -1, MAX_BOOK_ID + 1):
            with self.subTest(book_id=book_id):
                self.assertIsNone(find_book_by_id(book_id))

    # find_books sem filtros retorna tudo em ordem de id.
    def test_find_books_all(self) -> None:
        insert_book(self.book(title="A"))
        insert_book(self.book(title="B"))

        self.assertEqual([b["title"] for b in find_books()], ["A", "B"])

    # find_books filtra por título e por autor, sem diferenciar maiúsculas.
    def test_find_books_filters(self) -> None:
        insert_book(self.book(title="Dom Casmurro", author="Machado"))
        insert_book(self.book(title="Iracema", author="José de Alencar"))

        self.assertEqual(len(find_books(title="CASMURRO")), 1)
        self.assertEqual(len(find_books(author="alencar")), 1)
        self.assertEqual(len(find_books(title="dom", author="alencar")), 0)

    # find_books sem correspondência retorna lista vazia.
    def test_find_books_no_match(self) -> None:
        insert_book(self.book())

        self.assertEqual(find_books(title="xyz"), [])

    # find_books não interpreta % e _ como curingas e nem permite injeção de SQL.
    def test_find_books_escapes_special_characters(self) -> None:
        insert_book(self.book(title="100% real"))
        insert_book(self.book(title="Outro"))

        self.assertEqual(len(find_books(title="%")), 1)
        self.assertEqual(find_books(title="_"), [])
        self.assertEqual(find_books(title="' OR '1'='1"), [])

    # update_book_by_id altera os campos e retorna o registro atualizado.
    def test_update_book(self) -> None:
        saved = insert_book(self.book())
        assert saved is not None

        updated = update_book_by_id(saved["id"], self.book(title="Novo"))

        assert updated is not None
        self.assertEqual(updated["title"], "Novo")

    # update_book_by_id retorna None quando o livro não existe ou o id é inválido.
    def test_update_book_not_found(self) -> None:
        for book_id in (1, 0, MAX_BOOK_ID + 1):
            with self.subTest(book_id=book_id):
                self.assertIsNone(update_book_by_id(book_id, self.book()))

    # delete_book_by_id remove o livro e retorna True.
    def test_delete_book(self) -> None:
        saved = insert_book(self.book())
        assert saved is not None

        self.assertTrue(delete_book_by_id(saved["id"]))
        self.assertIsNone(find_book_by_id(saved["id"]))

    # delete_book_by_id retorna False para livro inexistente ou id inválido.
    def test_delete_book_not_found(self) -> None:
        for book_id in (1, 0, MAX_BOOK_ID + 1):
            with self.subTest(book_id=book_id):
                self.assertFalse(delete_book_by_id(book_id))

    # Funções que usam o banco exigem um contexto de aplicação.
    def test_get_db_requires_app_context(self) -> None:
        close_db()
        self.context.pop()
        try:
            with self.assertRaises(RuntimeError):
                get_db()
        finally:
            self.context.push()


# Testa os utilitários puros do model.
class BookModelHelpersTestCase(unittest.TestCase):
    # escape_like protege barra, porcentagem e sublinhado.
    def test_escape_like(self) -> None:
        self.assertEqual(escape_like("a%b_c\\d"), "a\\%b\\_c\\\\d")
        self.assertEqual(escape_like("texto"), "texto")

    # is_valid_id aceita apenas inteiros positivos de 64 bits.
    def test_is_valid_id(self) -> None:
        self.assertTrue(is_valid_id(1))
        self.assertTrue(is_valid_id(MAX_BOOK_ID))
        self.assertFalse(is_valid_id(0))
        self.assertFalse(is_valid_id(-5))
        self.assertFalse(is_valid_id(MAX_BOOK_ID + 1))


if __name__ == "__main__":
    unittest.main()
