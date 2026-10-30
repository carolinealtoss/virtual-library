# Biblioteca virtual

API REST em Python com Flask Blueprints e SQLite para gerenciar livros.

## Instalação e execução

Requer Python 3.10 ou superior.

```bash
python -m venv .venv
```

Ative o ambiente virtual e instale as dependências (Flask) dentro dele:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

No Linux/macOS, ative com `source .venv/bin/activate`.

No VS Code, selecione o interpretador do projeto em **Python: Select Interpreter**
(`.venv\Scripts\python.exe`). Se o editor exibir `Import "flask" could not be
resolved`, o Flask não está instalado no `.venv` selecionado: rode o
`pip install` acima com o ambiente ativo e recarregue a janela
(**Developer: Reload Window**).

Inicie a API:

```bash
python app.py
```

A aplicação cria o banco SQLite em `instance/books.sqlite3` automaticamente.

## Endpoints

Todos os endpoints usam o prefixo `/api`.

### `POST /api/books`

Cadastra um livro. Envie todos os campos como texto; `publication_date` deve
usar o formato `AAAA-MM-DD`.

```json
{
  "title": "O Pequeno Príncipe",
  "author": "Antoine de Saint-Exupéry",
  "publication_date": "1943-04-06",
  "summary": "Uma história sobre amizade e imaginação."
}
```

Retorna `201 Created` com o livro cadastrado e seu `id`. Campos ausentes,
inválidos, não textuais ou JSON malformado retornam `400 Bad Request` com uma
mensagem de erro. Um corpo enviado com `Content-Type` diferente de
`application/json` retorna `415 Unsupported Media Type`.

### `GET /api/books`

Lista todos os livros cadastrados. Aceita filtros opcionais por correspondência
parcial, sem distinção entre maiúsculas e minúsculas:

- `GET /api/books?title=pequeno` — busca pelo título.
- `GET /api/books?author=antoine` — busca pelo autor.
- `GET /api/books?title=pequeno&author=antoine` — combina os dois filtros.

Retorna `200 OK` com uma lista JSON; uma busca sem resultados retorna uma lista
vazia.

### `GET /api/books/<id>`

Retorna um livro pelo identificador (`200 OK`) ou `404 Not Found` se ele não
existir.

### `PUT /api/books/<id>`

Substitui todos os campos do livro. Envie o mesmo JSON usado no cadastro.
Retorna `200 OK` com o livro atualizado, `400 Bad Request` para dados inválidos,
`415 Unsupported Media Type` para um tipo de conteúdo não JSON, ou `404 Not Found`
se o livro não existir.

### `DELETE /api/books/<id>`

Exclui o livro e retorna `204 No Content`. Se ele não existir, retorna
`404 Not Found`.

Rotas inexistentes retornam `404 Not Found`, e métodos HTTP não implementados
para a rota retornam `405 Method Not Allowed`.

## Testando com o Postman

A collection [postman/virtual-library.postman_collection.json](postman/virtual-library.postman_collection.json)
contém uma requisição para cada endpoint, com exemplos de resposta em JSON
(sucesso e erro).

1. Inicie a API com `python app.py`.
2. No Postman, clique em **Import** e selecione o arquivo da collection.
3. Confira a variável `base_url` da collection (padrão: `http://127.0.0.1:5000/api`).
4. Execute as requisições individualmente ou use **Run collection**.

## Testes

Execute os testes unitários (controller e model) com:

```bash
python -m unittest discover -s tests -t . -v
```
