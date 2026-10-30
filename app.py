from flask import Flask

from src.controllers.book_controller import book_bp


app = Flask(__name__)

app.config.from_mapping(DATABASE="instance/books.sqlite3")
app.register_blueprint(book_bp, url_prefix="/api")


if __name__ == "__main__":
    app.run(debug=True)
