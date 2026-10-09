from flask import Flask

app = Flask(__name__)

@app.route('/')
def main():
    return "Hello from rag-etat-civil!"

if __name__ == "__main__":
    app.run()