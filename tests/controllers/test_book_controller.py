import os
import tempfile
import unittest

from flask import Flask
from flask.testing import FlaskClient

from src.controllers.book_controller import _validate_book as validate_book, book_bp


# Testa os endpoints do Blueprint de livros (sucesso e falhas).
class BookControllerTestCase(unittest.TestCase):
    # Prepara um app Flask com banco temporário isolado para cada teste.
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.temporary_directory.name, "test.sqlite3")
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, DATABASE=database_path)
        self.app.register_blueprint(book_bp, url_prefix="/api")
        self.client: FlaskClient = self.app.test_client()

    # Remove o banco temporário após cada teste.
    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    # Fornece um livro válido, permitindo sobrescrever campos.
    def valid_book(self, **overrides: str) -> dict[str, str]:
        book = {
            "title": "O Pequeno Príncipe",
            "author": "Antoine de Saint-Exupéry",
            "publication_date": "1943-04-06",
            "summary": "Uma história sobre amizade e imaginação.",
        }
        book.update(overrides)
        return book

    # Cadastra um livro via API e retorna o JSON criado.
    def create(self, **overrides: str) -> dict[str, object]:
        response = self.client.post("/api/books", json=self.valid_book(**overrides))
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    # POST: cadastro válido retorna 201 com o livro e o id.
    def test_create_book_success(self) -> None:
        response = self.client.post("/api/books", json=self.valid_book())

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json(), {"id": 1, **self.valid_book()})

    # POST: espaços ao redor dos campos são removidos.
    def test_create_book_trims_fields(self) -> None:
        book = self.create(title="  Dom Casmurro  ", author=" Machado de Assis ")

        self.assertEqual(book["title"], "Dom Casmurro")
        self.assertEqual(book["author"], "Machado de Assis")

    # POST: Content-Type diferente de JSON retorna 415.
    def test_create_book_rejects_non_json(self) -> None:
        response = self.client.post(
            "/api/books", data="texto", content_type="text/plain"
        )

        self.assertEqual(response.status_code, 415)
        self.assertIn("error", response.get_json())

    # POST: JSON malformado retorna 400.
    def test_create_book_rejects_malformed_json(self) -> None:
        response = self.client.post(
            "/api/books", data="{invalido", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # POST: JSON que não é um objeto retorna 400.
    def test_create_book_rejects_non_object_json(self) -> None:
        response = self.client.post("/api/books", json=["a", "b"])

        self.assertEqual(response.status_code, 400)

    # POST: campo ausente retorna 400 informando o campo.
    def test_create_book_rejects_missing_field(self) -> None:
        book = self.valid_book()
        del book["summary"]

        response = self.client.post("/api/books", json=book)

        self.assertEqual(response.status_code, 400)
        self.assertIn("summary", response.get_json()["error"])

    # POST: campo não textual retorna 400.
    def test_create_book_rejects_non_string_field(self) -> None:
        response = self.client.post("/api/books", json={**self.valid_book(), "title": 123})

        self.assertEqual(response.status_code, 400)

    # POST: título ou autor vazios retornam 400.
    def test_create_book_rejects_blank_title_or_author(self) -> None:
        for field in ("title", "author"):
            with self.subTest(field=field):
                response = self.client.post(
                    "/api/books", json=self.valid_book(**{field: "   "})
                )
                self.assertEqual(response.status_code, 400)

    # POST: datas fora do formato AAAA-MM-DD ou inexistentes retornam 400.
    def test_create_book_rejects_invalid_dates(self) -> None:
        for value in ("06/04/1943", "1943-13-01", "1943-02-30", "19430406", "1943-4-6"):
            with self.subTest(value=value):
                response = self.client.post(
                    "/api/books", json=self.valid_book(publication_date=value)
                )
                self.assertEqual(response.status_code, 400)

    # GET: lista vazia quando não há livros.
    def test_list_books_empty(self) -> None:
        response = self.client.get("/api/books")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    # GET: lista todos os livros em ordem de cadastro.
    def test_list_books_returns_all(self) -> None:
        self.create(title="Livro A")
        self.create(title="Livro B")

        response = self.client.get("/api/books")

        self.assertEqual(
            [book["title"] for book in response.get_json()], ["Livro A", "Livro B"]
        )

    # GET: busca por título é parcial e ignora maiúsculas.
    def test_search_by_title(self) -> None:
        self.create(title="Dom Casmurro")
        self.create(title="Memórias Póstumas")

        response = self.client.get("/api/books?title=CASM")

        self.assertEqual([b["title"] for b in response.get_json()], ["Dom Casmurro"])

    # GET: busca por autor é parcial e ignora maiúsculas.
    def test_search_by_author(self) -> None:
        self.create(author="Machado de Assis")
        self.create(author="Clarice Lispector")

        response = self.client.get("/api/books?author=machado")

        self.assertEqual(
            [b["author"] for b in response.get_json()], ["Machado de Assis"]
        )

    # GET: filtros combinados exigem os dois critérios.
    def test_search_by_title_and_author(self) -> None:
        self.create(title="Livro", author="Autor A")
        self.create(title="Livro", author="Autor B")

        response = self.client.get("/api/books?title=livro&author=autor b")

        self.assertEqual(len(response.get_json()), 1)

    # GET: busca sem resultado retorna lista vazia.
    def test_search_without_results(self) -> None:
        self.create()

        response = self.client.get("/api/books?title=inexistente")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    # GET: curingas do SQL (% e _) são tratados como texto comum.
    def test_search_treats_wildcards_as_text(self) -> None:
        self.create(title="Livro 100% bom")
        self.create(title="Outro livro")

        for term, expected in (("%", 1), ("_", 0), ("100%", 1)):
            with self.subTest(term=term):
                response = self.client.get("/api/books", query_string={"title": term})
                self.assertEqual(len(response.get_json()), expected)

    # GET por id: retorna o livro existente.
    def test_get_book_success(self) -> None:
        created = self.create()

        response = self.client.get(f"/api/books/{created['id']}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), created)

    # GET por id: inexistente retorna 404.
    def test_get_book_not_found(self) -> None:
        response = self.client.get("/api/books/999")

        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.get_json())

    # GET por id: id gigante ou zero retorna 404 sem erro interno.
    def test_get_book_with_out_of_range_id(self) -> None:
        for book_id in ("0", "99999999999999999999"):
            with self.subTest(book_id=book_id):
                self.assertEqual(self.client.get(f"/api/books/{book_id}").status_code, 404)

    # GET por id: id não numérico não casa com a rota (404).
    def test_get_book_with_non_numeric_id(self) -> None:
        self.assertEqual(self.client.get("/api/books/abc").status_code, 404)

    # PUT: atualiza todos os campos e retorna o livro atualizado.
    def test_update_book_success(self) -> None:
        created = self.create()
        changes = self.valid_book(title="Novo título", summary="Novo resumo")

        response = self.client.put(f"/api/books/{created['id']}", json=changes)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"id": created["id"], **changes})
        self.assertEqual(
            self.client.get(f"/api/books/{created['id']}").get_json()["title"],
            "Novo título",
        )

    # PUT: livro inexistente retorna 404.
    def test_update_book_not_found(self) -> None:
        response = self.client.put("/api/books/999", json=self.valid_book())

        self.assertEqual(response.status_code, 404)

    # PUT: id gigante retorna 404 sem erro interno.
    def test_update_book_with_out_of_range_id(self) -> None:
        response = self.client.put(
            "/api/books/99999999999999999999", json=self.valid_book()
        )

        self.assertEqual(response.status_code, 404)

    # PUT: dados inválidos retornam 400 e não alteram o livro.
    def test_update_book_invalid_data(self) -> None:
        created = self.create()

        response = self.client.put(
            f"/api/books/{created['id']}", json=self.valid_book(publication_date="x")
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.get(f"/api/books/{created['id']}").get_json(), created
        )

    # PUT: Content-Type diferente de JSON retorna 415.
    def test_update_book_rejects_non_json(self) -> None:
        created = self.create()

        response = self.client.put(
            f"/api/books/{created['id']}", data="texto", content_type="text/plain"
        )

        self.assertEqual(response.status_code, 415)

    # DELETE: remove o livro e retorna 204 sem corpo.
    def test_delete_book_success(self) -> None:
        created = self.create()

        response = self.client.delete(f"/api/books/{created['id']}")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertEqual(self.client.get(f"/api/books/{created['id']}").status_code, 404)

    # DELETE: livro inexistente (ou já removido) retorna 404.
    def test_delete_book_not_found(self) -> None:
        created = self.create()
        self.client.delete(f"/api/books/{created['id']}")

        self.assertEqual(self.client.delete(f"/api/books/{created['id']}").status_code, 404)

    # DELETE: id gigante retorna 404 sem erro interno.
    def test_delete_book_with_out_of_range_id(self) -> None:
        response = self.client.delete("/api/books/99999999999999999999")

        self.assertEqual(response.status_code, 404)

    # Métodos não implementados retornam 405.
    def test_method_not_allowed(self) -> None:
        self.assertEqual(self.client.patch("/api/books/1").status_code, 405)
        self.assertEqual(self.client.delete("/api/books").status_code, 405)

    # Registrar o Blueprint em um novo app cria o banco e a tabela.
    def test_blueprint_registration_creates_database(self) -> None:
        self.assertTrue(os.path.exists(self.app.config["DATABASE"]))


# Testa a função de validação isoladamente.
class ValidateBookTestCase(unittest.TestCase):
    # Dados válidos retornam o livro normalizado e nenhum erro.
    def test_valid_data(self) -> None:
        data = {
            "title": " T ",
            "author": "A",
            "publication_date": "2020-02-29",
            "summary": "S",
        }

        book, error = validate_book(data)

        self.assertIsNone(error)
        self.assertEqual(book, {**data, "title": "T"})

    # Entradas que não são dicionário retornam erro.
    def test_non_dict_data(self) -> None:
        for data in (None, [], "texto", 1):
            with self.subTest(data=data):
                book, error = validate_book(data)
                self.assertIsNone(book)
                self.assertIsNotNone(error)

    # Ano não bissexto com 29 de fevereiro é rejeitado.
    def test_invalid_leap_day(self) -> None:
        book, error = validate_book(
            {"title": "T", "author": "A", "publication_date": "2023-02-29", "summary": "S"}
        )

        self.assertIsNone(book)
        self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
